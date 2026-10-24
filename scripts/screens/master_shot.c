/* MASTER shots for the README and guide: asm/master/master.c fed a synthetic 120 BPM mix (kick, bass, chords, hats, pink noise), then each page's framebuffer to <dir>/master_<page>.fb (64x128 '0'/'1'). */
#include <stdio.h>
#include <stdlib.h>
#define MS_HOST 1
#include "ms_host.h"
#include "master.c"

static int pix(int x, int y) { return ((unsigned char *)host_lcd)[(y >> 3) * 128 + x] >> (y & 7) & 1; }
static void dump(const char *dir, const char *name)
{
    char path[512]; int x, y; FILE *f;
    sprintf(path, "%s/master_%s.fb", dir, name);
    f = fopen(path, "wb");
    for (y = 0; y < 64; y++) for (x = 0; x < 128; x++) fputc('0' + pix(x, y), f);
    fclose(f);
}
static double t, sph[8];
static float *pl0;
static float pink(float *b)                       /* Paul Kellet's pink filter on white noise */
{
    float w = (rand() & 32767) / 16384.0f - 1;
    b[0] = 0.99886f * b[0] + w * 0.0555179f; b[1] = 0.99332f * b[1] + w * 0.0750759f;
    b[2] = 0.96900f * b[2] + w * 0.1538520f; b[3] = 0.86650f * b[3] + w * 0.3104856f;
    b[4] = 0.55000f * b[4] + w * 0.5329522f; b[5] = -0.7616f * b[5] - w * 0.0168980f;
    { float p = b[0] + b[1] + b[2] + b[3] + b[4] + b[5] + b[6] + w * 0.5362f; b[6] = w * 0.115926f; static float lp[2]; int c = b == pl0 ? 0 : 1; lp[c] += 0.12f * (p - lp[c]); return lp[c] * 0.16f + p * 0.012f; }
}
static double saw(int i, double f) { sph[i] += f / 44100; sph[i] -= floor(sph[i]); return 2 * sph[i] - 1; }
static void play(int frames)                      /* a full 120 BPM mix: kick, bass, saw chord, hats, pink-noise bed */
{
    static float pl[7], pr[7]; pl0 = pl;
    static const double bassf[4] = { 55, 55, 65.4, 49 };
    int i; St *s = ST;
    for (i = 0; i < frames; i++, t += 1.0 / 44100) {
        double k = fmod(t, 0.5), h = fmod(t + 0.25, 0.5), bar = fmod(t, 8.0);
        double kick = 0.6 * exp(-k * 9) * sin(6.283 * (45 + 110 * exp(-k * 30)) * k);
        double hat = 0.05 * ((rand() & 1023) / 512.0 - 1) * exp(-h * 40);
        double bf = bassf[(int)(bar / 2)];
        double bass = 0.30 * saw(0, bf) * (0.6 + 0.4 * exp(-fmod(t, 0.25) * 8));
        double chL = 0.07 * (saw(1, bf * 4) + saw(2, bf * 4 * 1.26) + saw(3, bf * 6));
        double chR = 0.07 * (saw(4, bf * 4 * 1.003) + saw(5, bf * 4 * 1.26 * 0.998) + saw(6, bf * 8));
        float L = (float)(kick + bass + chL + hat + pink(pl)), R = (float)(kick + bass + chR + 0.9 * hat + pink(pr));
        unsigned w = s->w;
        if (ab(L) > s->ipk[0]) s->ipk[0] = ab(L);
        if (ab(R) > s->ipk[1]) s->ipk[1] = ab(R);
        host_rm[w & 4095] = (short)_sat16(_spint((L + R) * 0.5f * 32767.0f * 0.9f));
        host_rs[w & 2047] = (short)_sat16(_spint((L - R) * 0.5f * 32767.0f * 0.9f));
        s->w = w + 1;
        if (0.9f < s->gmin) s->gmin = 0.9f;
        if ((i % 735) == 734) { consume(); advance(); }
    }
}
int main(int argc, char **argv)
{
    static const char *nm[6] = {"spectrum", "scope", "stereo", "loudness", "input", "meters"};
    /* the README's KALEIDO grid: 6 knob sets (zoom, spin, mirrors 0 AUTO or 1..6 = 4 6 8 10 12 16), 5 frames each */
    static const int ks[6][3] = { {0,0,0}, {-6,2,0}, {5,-3,0}, {0,4,2}, {3,0,5}, {-3,-5,6} };
    St *s; int p;
    master_draw(); s = ST;
    if (argc > 2) {                               /* master.exe <dir> grid */
        char g[16]; int n = 0, k, f;
        host_entry = 6;
        host_zt[0] = 0x5A4D5401u; host_zt[2] = 0; host_zt[5] = 12000;
        for (p = 0; p < 80; p++) { play(706); master_poll(); if ((s->tick & 3) == 0) master_draw(); }
        for (k = 0; k < 6; k++) {
            s->kzs = ks[k][0]; s->krs = ks[k][1]; s->kmi = ks[k][2];
            for (f = 0; f < 5; f++) {
                for (p = 0; p < 37 + 23 * f; p++) { play(706); master_poll(); if ((s->tick & 3) == 0) master_draw(); }
                master_draw(); sprintf(g, "grid%02d", n++); dump(argv[1], g);
            }
        }
        return 0;
    }
    for (p = 0; p < 6; p++) {
        s->page = p;
        play(44100 * (p == 3 ? 12 : 3));
        master_draw(); dump(argv[1], nm[p]);
    }
    host_entry = 6;
    host_zt[0] = 0x5A4D5401u; host_zt[2] = 0; host_zt[5] = 12000;
    for (p = 0; p < 120; p++) { play(706); master_poll(); if ((s->tick & 3) == 0) master_draw(); }
    master_draw(); dump(argv[1], "kaleido");
    return 0;
}
