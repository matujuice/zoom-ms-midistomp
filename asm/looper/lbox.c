/* GRDLOOP status bar (MS-70CDR 2.10 OS), drawn like Perform mode's top bar
 * (docs/perform-ui-mockup.html statusBar / drawPlay): fill over the cycle, the left text,
 * bar.beat/cycle on the right, a gap in the edge and a dotted line at each bar line.
 * Replaces looper.S draw_pre at the callp 0xC00BB0EC (patches/looper.yaml); the poll's
 * redraw check stays in looper.S (S_PROG's bar/beat bits change every beat).
 * Cover: the GRDLOOP cover's bar (make_cover.py) x 0-127, y 17-34, pixel for pixel.
 * Knob pages: none (Luca, PERFORM11: it clashed with the page title).
 * Data: docs/looper-services.md (S_TEXT, S_PROG, S_LEFT). Built by scripts/build_looper_ui.py. */

#define FN(addr, ret, args) ((ret (*) args)(addr))
#define SV(off) (*(volatile unsigned *)(0xC00F3000u + (off)))
#define S_MINE 48
#define S_TEXT 68
#define S_PROG 76
#define S_LEFT 120
#define MODE (*(volatile int *)(0xC00EF748u + 320))      /* 0 play; S_MINE lags it by one poll */
#define PENDING (*(volatile int *)(0xC00EF748u + 340))   /* a prompt over the Effect View */
#define VIEW_KNOBS (*(volatile int *)0xC009D398)          /* 1 knob pages, 0 cover */
#define FB ((volatile unsigned char *)0x11816800)         /* page format: 128 bytes per 8 rows */
#define FB_DIRTY (*(volatile unsigned char *)0xC00EEBB0)  /* bit = 8-row page to send */
#define FONT7 ((const unsigned char *)0xC00E87D8)         /* 7 column bytes per character */
#define OVL_GET FN(0xC00CCD6C, int, (int))                /* -1 = no overlay */
#define LCD_GATE FN(0xC00D5720, int, (int))               /* the stock call we sit in front of */

static void px(int x, int y, int op)                      /* 0 clear, 1 set, 2 invert */
{
    volatile unsigned char *p = FB + ((y >> 3) << 7) + x;
    unsigned char b = (unsigned char)(1u << (y & 7));
    if (op == 0) *p &= (unsigned char)~b;
    else if (op == 1) *p |= b;
    else *p ^= b;
}

static int put(char *t, int k, const char *s) { while (*s) t[k++] = *s++; return k; }

static int put_n(char *t, int k, int n)                   /* 0..99, no division */
{
    int d = 0;
    while (n >= 10) { n -= 10; d++; }
    if (d) t[k++] = (char)('0' + d);
    t[k++] = (char)('0' + n);
    return k;
}

/* the left text from S_LEFT: kind 0-3, n 4-9, m 10-15, beats 16, mono 17 */
static int left_text(char *t)
{
    unsigned c = SV(S_LEFT), kind = c & 15, n = c >> 4 & 63, m = c >> 10 & 63;
    int k = 0;
    if (kind == 0) {                                      /* an older ZDL: its 8 characters */
        for (; k < 8; k++) t[k] = ((volatile char *)(0xC00F3000u + S_TEXT))[k];
        while (k > 0 && (t[k - 1] == ' ' || t[k - 1] == 0)) k--;
        return k;
    }
    if (kind == 1) return put(t, 0, "EMPTY");
    if (kind == 8) return put(t, 0, "STOPPED");
    if (kind <= 4) {                                      /* REC / STOP / PLAY IN n BARS */
        k = put(t, 0, kind == 2 ? "REC IN " : kind == 3 ? "STOP IN " : "PLAY IN ");
        k = put_n(t, k, n);
        k = put(t, k, c >> 16 & 1 ? " BEAT" : " BAR");
        if (n > 1) t[k++] = 'S';
        return k;
    }
    if (kind == 7) {
        k = put_n(t, put(t, 0, "PLAY "), n);
        k = put(t, k, " BAR");
        if (n > 1) t[k++] = 'S';
        return k;
    }
    k = put_n(t, put(t, 0, "REC "), n);                   /* 5 "REC 3", 6 "REC 3/8" */
    if (kind == 6) { t[k++] = '/'; k = put_n(t, k, m); }
    if (c >> 17 & 1) k = put(t, k, " MONO");
    return k;
}

/* FONT7 proportional: each character's inked columns and a gap, a space 2 columns.
 * Draws at (x, y) inverted, notes the ink in ink[] (bit = row - y0); returns the width. */
static int text(const char *t, int n, int x, int y, int y0, int xmax, unsigned *ink, int draw)
{
    int i, j, r, w = 0;
    for (i = 0; i < n; i++) {
        const unsigned char *f = FONT7 + 7 * (unsigned char)t[i];
        int any = 0;
        for (j = 0; j < 7; j++) {
            if (!f[j]) continue;
            any = 1;
            if (draw && x + w <= xmax)
                for (r = 0; r < 7; r++)
                    if (f[j] >> r & 1) { px(x + w, y + r, 2); ink[x + w] |= 1u << (y + r - y0); }
            w++;
        }
        w += any ? 1 : 2;
    }
    return w - 1;                                         /* the last gap is not part of it */
}

static void bar(int x0, int y0, int x1, int y1, int s, int margin)
{
    unsigned prog = SV(S_PROG), ink[128];
    int xi0 = x0 + s, xi1 = x1 - s, yi0 = y0 + s, yi1 = y1 - s, wi = xi1 - xi0 + 1;
    int fill = (int)((unsigned)wi * (prog & 0xFFFF) >> 8), cyc = prog >> 16 & 63;
    int ty = yi0 + ((yi1 - yi0 + 1 - 7) >> 1), x, y, i, q, r, n, w;
    char t[24];
    if (fill > wi) fill = wi;
    for (x = x0; x <= x1; x++) {
        ink[x] = 0;
        for (y = y0; y <= y1; y++)
            px(x, y, x < x0 + s || x > x1 - s || y < y0 + s || y > y1 - s || x - xi0 < fill);
    }
    n = left_text(t);
    text(t, n, xi0 + margin, ty, y0, xi1, ink, 1);
    if (cyc) {                                  /* bar.beat/cycle, or NO CLK */
        if (prog >> 30 & 1) n = put(t, 0, "NO CLK");
        else {
            n = put_n(t, 0, prog >> 22 & 63);
            t[n++] = '.';
            n = put_n(t, n, (prog >> 28 & 3) + 1);
            t[n++] = '/';
            n = put_n(t, n, cyc);
        }
        w = text(t, n, 0, 0, 0, 0, ink, 0);
        text(t, n, xi1 - margin + 1 - w, ty, y0, xi1, ink, 1);
    }
    if (cyc > 1 && wi >= 3 * cyc)                         /* bar lines, not denser than 3 px */
        for (i = 1, q = 0, r = 0; i < cyc; i++) {
            r += wi;                                      /* q = wi * i / cyc */
            while (r >= cyc) { r -= cyc; q++; }
            x = xi0 + q;
            for (y = y0; y < yi0; y++) { px(x, y, 0); px(x, y1 - (y - y0), 0); }   /* a gap in the edge */
            for (y = yi0 + (s == 1); y < yi1; y += 2) {  /* dotted, inverted, off the text and 1 px round it */
                unsigned nb = (ink[x - 1] | ink[x] | ink[x + 1]) >> (y - y0 - 1) & 7;
                if (!nb) px(x, y, 2);
            }
        }
    {                                                     /* the cover's radius-2 corners */
        static const signed char c[6] = { 0, 0, 1, 0, 0, 1 };
        for (i = 0; i < 6; i += 2) {
            px(x0 + c[i], y0 + c[i + 1], 0); px(x1 - c[i], y0 + c[i + 1], 0);
            px(x0 + c[i], y1 - c[i + 1], 0); px(x1 - c[i], y1 - c[i + 1], 0);
        }
        px(x0 + 1, y0 + 1, 1); px(x1 - 1, y0 + 1, 1); px(x0 + 1, y1 - 1, 1); px(x1 - 1, y1 - 1, 1);
    }
    for (y = y0 >> 3; y <= y1 >> 3; y++) FB_DIRTY |= (unsigned char)(1u << y);
}

/* the callp at 0xC00BB0EC: A4 = the stock call's argument */
int lbox_draw(int a4)
{
    if (SV(S_MINE) && !MODE && !PENDING && !VIEW_KNOBS && OVL_GET(0) == -1)
        bar(0, 17, 127, 34, 2, 4);                        /* the cover only */
    return LCD_GATE(a4);
}
