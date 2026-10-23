/* Host checks for asm/master/master.c: tap, tuner, loudness and the pages against the mockup's framebuffers.
 *   master_host tap | tuner | loud | ref <audio.bin> <shots.txt> <dir> */
#include <stdio.h>
#include <stdlib.h>
#define MS_HOST 1
#include "ms_host.h"
#include "master.c"

static float hq[2];                 /* the input block sums (master_tap does them per block) */
static void reset_all(void)
{
    memset(host_fft, 0, sizeof host_fft); memset(host_sin, 0, sizeof host_sin); memset(host_bars, 0, sizeof host_bars);
    memset(host_rm, 0, sizeof host_rm); memset(host_rs, 0, sizeof host_rs); memset(host_hist, 0, sizeof host_hist);
    memset(host_st, 0, sizeof host_st); memset(host_lcd, 0, sizeof host_lcd);
    host_on = 0; host_glim = 1.0f; inited = 0; hq[0] = hq[1] = 0;
    master_draw();                                   /* first open: init */
}

static void put(float L, float R, float lim, float iL, float iR)   /* master_tap's packing and input stats, one frame */
{
    St *s = ST;
    unsigned w = s->w;
    if (ab(iL) > s->ipk[0]) s->ipk[0] = ab(iL);
    if (ab(iR) > s->ipk[1]) s->ipk[1] = ab(iR);
    if (ab(iL) >= 0.999f) s->over |= 4;
    if (ab(iR) >= 0.999f) s->over |= 8;
    hq[0] += iL * iL; hq[1] += iR * iR;
    if ((w & 7) == 7) { s->ims[0] += KI * (hq[0] * 0.125f - s->ims[0]); s->ims[1] += KI * (hq[1] * 0.125f - s->ims[1]); hq[0] = hq[1] = 0; }
    host_rm[w & 4095] = (short)_sat16(_spint((L + R) * 16384.0f));
    host_rs[w & 2047] = (short)_sat16(_spint((L - R) * 16384.0f));
    s->w = w + 1;
    if (lim < s->gmin) s->gmin = lim;
}

static int pix(int x, int y) { return ((unsigned char *)host_lcd)[(y >> 3) * 128 + x] >> (y & 7) & 1; }

static int tap(void)
{
    int i, bad = 0;
    reset_all();
    ST->w = 0;
    for (i = 0; i < 8; i++) { host_f[i] = 0.1f * (float)i - 0.3f; host_f[8 + i] = 0.5f - 0.07f * (float)i; }
    host_f[0] = 1.0f; host_f[8] = 1.0f;              /* (L + R) / 2 = 1.0: saturates to 32767 */
    host_glim = 0.8f;
    for (i = 0; i < 16; i++) host_snap[i] = 0;
    host_snap[3] = -1.0f; host_snap[10] = 0.5f;      /* input: L at full scale, R at half */
    master_tap();
    master_tap();
    for (i = 0; i < 8; i++) {
        float l = host_f[i], r = host_f[8 + i];
        int m = _sat16(_spint((l + r) * 16384.0f)), d = _sat16(_spint((l - r) * 16384.0f));
        if (host_rm[i] != m || host_rs[i] != d || host_rm[8 + i] != m || host_rs[8 + i] != d) bad++;
    }
    if (ST->w != 16 || ST->gmin != 0.8f) bad++;
    if (ST->ipk[0] != 1.0f || ST->ipk[1] != 0.5f || (ST->over & 12) != 4 || !(ST->ims[0] > 0) || !(ST->ims[1] > 0)) bad++;
    printf("tap: %s (m0=%d)\n", bad ? "FAILED" : "ok", host_rm[0]);
    return bad;
}

static void sine(double hz, double amp, int n)
{
    static double ph;
    int i;
    for (i = 0; i < n; i++) {
        float v = (float)(amp * sin(ph));
        ph += 6.283185307179586 * hz / 44100.0;
        put(v, v, 1.0f, 0, 0);
        if ((i % 700) == 699) consume();
    }
    consume();
}

static int tuner(double hz, int nn_want, int cents_lo, int cents_hi)
{
    St *s;
    reset_all();
    s = ST;
    s->page = 1;
    sine(hz, 0.5, 8000);
    advance();
    printf("tuner %.1f Hz: note %d cents %d f=%.2f\n", hz, s->scNN, s->scCents, s->scF);
    return !(s->scNN == nn_want && s->scCents >= cents_lo && s->scCents <= cents_hi);
}

static int loudness(void)
{
    int bad;
    reset_all();
    sine(997.0, 0.1, 44100 * 6);
    loud();
    printf("loud: momentary %.2f short %.2f integrated %.2f\n", lv[0], lv[1], lv[2]);
    bad = !(fabsf(lv[0] + 20.0f) < 0.3f && fabsf(lv[1] + 20.0f) < 0.3f && fabsf(lv[2] + 20.0f) < 0.3f);
    return bad;
}

static int ref(const char *audio, const char *shots, const char *dir)
{
    FILE *fa = fopen(audio, "rb"), *fs = fopen(shots, "r");
    char name[64], path[512];
    int frame, nframes = 0, hdr[3], i, k, want_frame[16], nshot = 0, bad = 0, x, y, diff;
    char names[16][64];
    static float buf[2205 * 5 + 16];
    St *s;
    if (!fa || !fs) { puts("cannot open inputs"); return 2; }
    while (fscanf(fs, "%63s %d", names[nshot], &want_frame[nshot]) == 2) nshot++;
    reset_all();
    s = ST;
    for (frame = 0; fread(hdr, 4, 3, fa) == 3; frame++) {
        int n = hdr[2];
        if (fread(buf, 20, n, fa) != (size_t)n) break;
        s->page = hdr[0]; s->opt[1] = hdr[1];
        for (i = 0; i < n; i++) {
            put(buf[5 * i], buf[5 * i + 1], buf[5 * i + 2], buf[5 * i + 3], buf[5 * i + 4]);
            if ((i % 735) == 734) consume();
        }
        consume();
        advance();
        master_draw();
        for (k = 0; k < nshot; k++) if (want_frame[k] == frame) {
            FILE *fr;
            static char ref[8200];
            diff = 0;
            sprintf(path, "%s/%s.fb", dir, names[k]);
            fr = fopen(path, "rb");
            if (!fr || fread(ref, 1, 8192, fr) != 8192) { puts("missing reference"); return 2; }
            fclose(fr);
            sprintf(path, "%s/%s.c.fb", dir, names[k]);
            fr = fopen(path, "wb");
            for (y = 0; y < 64; y++) for (x = 0; x < 128; x++) {
                int v = pix(x, y);
                fputc('0' + v, fr);
                if (v != ref[y * 128 + x] - '0') diff++;
            }
            fclose(fr);
            printf("shot %s: %d px differ\n", names[k], diff);
            if (!strcmp(names[k], "loudness")) { loud(); printf("  loudness values %.5f %.5f %.5f %.5f %.5f %.5f\n", lv[0], lv[1], lv[2], lv[3], lv[4], lv[5]); }
            bad += diff != 0;
        }
        nframes++;
    }
    printf("frames %d, shots with differences %d, St %d bytes\n", nframes, bad, (int)sizeof(St));
    return 0;
}

static int kaleido(void)            /* full screen, about half ink, the beat flash is the exact inverse */
{
    St *s;
    int i, ink = 0, bad = 0, fl[5];
    static unsigned a[256];
    reset_all();
    s = ST;
    host_entry = 6;
    sine(55.0, 0.3, 4000);
    host_zt[0] = 0x5A4D5401u; host_zt[1] = 2; host_zt[2] = 1; host_zt[5] = 12000;
    for (i = 0; i < 5; i++) { host_zt[4] = 2 + 24 * i; host_zt[2] = i < 4; master_poll(); master_poll(); master_poll(); master_poll(); fl[i] = s->kinv; }
    s->kinv = 0; master_draw(); memcpy(a, host_lcd, sizeof a);
    for (i = 0; i < 8192; i++) ink += pix(i & 127, i >> 7);
    s->kinv = 1; master_draw();
    for (i = 0; i < 256; i++) bad += host_lcd[i] != ~a[i];
    printf("kaleido: ink %d of 8192, beats %d %d %d %d stop %d, inverse %s\n", ink, fl[0], fl[1], fl[2], fl[3], fl[4], bad ? "FAILED" : "ok");
    host_entry = 5;
    return bad || ink < 2000 || ink > 6200 || fl[0] || !fl[1] || fl[2] || !fl[3] || fl[4];
}

int main(int argc, char **argv)
{
    int bad = 0;
    if (argc > 1 && !strcmp(argv[1], "ref")) return ref(argv[2], argv[3], argv[4]);
    bad += tap();
    bad += tuner(440.0, 69, 0, 0);
    bad += tuner(82.4, 40, -2, 2);
    bad += loudness();
    bad += kaleido();
    puts(bad ? "FAILED" : "all passed");
    return bad != 0;
}
