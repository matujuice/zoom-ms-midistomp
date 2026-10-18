/* Mixer Mode M3b: draws the Effect Chain screen (stock screen 3) into a 128 x 64 frame
 * buffer. A line-for-line port of drawChain() in docs/mixer-ui-mockup.html (v20), cut to
 * what M3b ships: mono input, Output Mode Stereo, Serial / Parallel, no Mute / Solo, no
 * Smart Warning, no popup (M3c). Pure: reads Chain, writes only fb. No libc, no floats.
 * fb: row-major, bit 7 of byte 0 = pixel (0,0), 1 = ink. */
#include "chain.h"

#define CW 38                   /* cover width / height, and the rows of the three line sets */
#define CH 19
#define YC 32                   /* the single line; YA / YB: the Bus A / Bus B rows */
#define YA 21
#define YB 43

#define K_IN 0                  /* column kinds, signal order IN ... OUT (right to left on screen) */
#define K_OUT 1
#define K_EFF 2
#define K_NODE 3
#define K_BUS 4

typedef struct { int kind, e, a, b; } Col;      /* e: slot or IT_*; a / b: the Bus A / Bus B slot or -1 */
typedef struct { unsigned char (*fb)[16]; const Chain *c; int cur; } D;

/* Stock fonts from the mockup: 5x7 (bit 4 = left column) for covers and titles, 3x5 (bit 2) for softkeys, hints, tags. */
static const char K5[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 []-.!/";
static const unsigned char G5[][7] = {
    {14,17,17,31,17,17,17},{30,17,17,30,17,17,30},{14,17,16,16,16,17,14},{28,18,17,17,17,18,28},{31,16,16,30,16,16,31},{31,16,16,30,16,16,16},
    {14,17,16,23,17,17,15},{17,17,17,31,17,17,17},{14,4,4,4,4,4,14},{7,2,2,2,2,18,12},{17,18,20,24,20,18,17},{16,16,16,16,16,16,31},
    {17,27,21,21,17,17,17},{17,17,25,21,19,17,17},{14,17,17,17,17,17,14},{30,17,17,30,16,16,16},{14,17,17,17,21,18,13},{30,17,17,30,20,18,17},
    {15,16,16,14,1,1,30},{31,4,4,4,4,4,4},{17,17,17,17,17,17,14},{17,17,17,17,17,10,4},{17,17,17,21,21,21,10},{17,17,10,4,10,17,17},
    {17,17,10,4,4,4,4},{31,1,2,4,8,16,31},{0,0,14,1,15,17,15},{16,16,22,25,17,17,30},{0,0,14,16,16,17,14},{1,1,13,19,17,17,15},
    {0,0,14,17,31,16,14},{6,9,8,28,8,8,8},{0,15,17,17,15,1,14},{16,16,22,25,17,17,17},{4,0,12,4,4,4,14},{2,0,6,2,2,18,12},
    {16,16,18,20,24,20,18},{12,4,4,4,4,4,14},{0,0,26,21,21,17,17},{0,0,22,25,17,17,17},{0,0,14,17,17,17,14},{0,0,30,17,30,16,16},
    {0,0,13,19,15,1,1},{0,0,22,25,16,16,16},{0,0,14,16,14,1,30},{8,8,28,8,8,9,6},{0,0,17,17,17,19,13},{0,0,17,17,17,10,4},
    {0,0,17,17,21,21,10},{0,0,17,10,4,10,17},{0,0,17,17,15,1,14},{0,0,31,2,4,8,31},{14,17,19,21,25,17,14},{4,12,4,4,4,4,14},
    {14,17,1,2,4,8,31},{31,2,4,2,1,17,14},{2,6,10,18,31,2,2},{31,16,30,1,1,17,14},{6,8,16,30,17,17,14},{31,1,2,4,8,8,8},
    {14,17,17,14,17,17,14},{14,17,17,15,1,2,12},{0,0,0,0,0,0,0},{14,8,8,8,8,8,14},{14,2,2,2,2,2,14},{0,0,0,31,0,0,0},
    {0,0,0,0,0,12,12},{4,4,4,4,4,0,4},{0,1,2,4,8,16,0},
};
static const char K3[] = "ABCDEGILMNOPRSTUX/F? !H{}^v<>";
static const unsigned char G3[][5] = {
    {2,5,7,5,5},{6,5,6,5,6},{3,4,4,4,3},{6,5,5,5,6},{7,4,6,4,7},{3,4,5,5,3},
    {7,2,2,2,7},{4,4,4,4,7},{5,7,7,5,5},{6,5,5,5,5},{2,5,5,5,2},{6,5,6,4,4},
    {6,5,6,5,5},{3,4,2,1,6},{7,2,2,2,2},{5,5,5,5,7},{5,5,2,5,5},{1,1,2,4,4},
    {7,4,6,4,4},{6,1,2,0,2},{0,0,0,0,0},{2,2,2,0,2},{5,5,7,5,5},{1,3,7,3,1},
    {4,6,7,6,4},{0,2,7,0,0},{0,7,2,0,0},{0,1,3,1,0},{0,4,6,4,0},
};

/* ---- pixels --------------------------------------------------------------------------- */
static void fill(const D *d, int x, int y, int w, int h, int ink)
{
    int i, j;
    for (j = y; j < y + h; j++) {
        if (j < 0 || j > 63) continue;
        for (i = x; i < x + w; i++) {
            if (i < 0 || i > 127) continue;
            if (ink) d->fb[j][i >> 3] |= (unsigned char)(0x80 >> (i & 7));
            else d->fb[j][i >> 3] &= (unsigned char)~(0x80 >> (i & 7));
        }
    }
}

static void invert(const D *d, int x, int y, int w, int h)
{
    int i, j;
    for (j = y; j < y + h; j++) {
        if (j < 0 || j > 63) continue;
        for (i = x; i < x + w; i++)
            if (i >= 0 && i < 128) d->fb[j][i >> 3] ^= (unsigned char)(0x80 >> (i & 7));
    }
}

static void sq(const D *d, int x, int y, int w, int h)  /* square 1-px frame */
{
    fill(d, x, y, w, 1, 1); fill(d, x, y + h - 1, w, 1, 1);
    fill(d, x, y + 1, 1, h - 2, 1); fill(d, x + w - 1, y + 1, 1, h - 2, 1);
}

static void hspan(const D *d, int a, int b, int y)      /* 1-px horizontal wire from a to b */
{
    if (a > b) { int t = a; a = b; b = t; }
    fill(d, a, y, b - a + 1, 1, 1);
}

static int slen(const char *s) { int n = 0; while (s[n]) n++; return n; }

static void text(const D *d, const char *keys, const unsigned char *g, int rows, int bits,
                 const char *s, int x, int y, int ink, int bold)
{
    int n, k, r, i;
    for (; *s; s++) {
        for (k = 0, n = -1; keys[k]; k++) if (keys[k] == *s) { n = k; break; }
        if (n < 0) for (k = 0; keys[k]; k++) if (keys[k] == ' ') { n = k; break; }
        for (r = 0; r < rows; r++)
            for (i = 0; i < bits; i++)
                if (g[n * rows + r] >> (bits - 1 - i) & 1) fill(d, x + i, y + r, bold ? 2 : 1, 1, ink);
        x += bits + 1 + (bold ? 1 : 0);
    }
}

static void t5(const D *d, const char *s, int x, int y, int ink, int bold) { text(d, K5, &G5[0][0], 7, 5, s, x, y, ink, bold); }
static void t3(const D *d, const char *s, int x, int y, int ink) { text(d, K3, &G3[0][0], 5, 3, s, x, y, ink, 0); }
static void t7(const D *d, const char *s, int x, int y) { t5(d, s, x, y, 1, 1); }   /* the stock cover font: 6 x 7 */
static int w5(const char *s, int bold) { return slen(s) * (bold ? 7 : 6) - 1; }
static int w3(const char *s) { return slen(s) * 4 - 1; }

/* Stock CHO: the item inverted inside a box 2 px larger; the cursor is only that box's outline.
 * clear() before drawing the item, mark() after. */
static void clear(const D *d, int x, int y, int w, int h, int cur)
{
    if (cur) fill(d, x - 2, y - 2, w + 4, h + 4, 0); else fill(d, x, y, w, h, 0);
}

static void mark(const D *d, int x, int y, int w, int h, int sel)
{
    if (sel) invert(d, x - 2, y - 2, w + 4, h + 4); else sq(d, x - 2, y - 2, w + 4, h + 4);
}

/* ---- covers --------------------------------------------------------------------------- */
/* The stock cover: top and bottom edges 2 rows (outer row 1 px shorter each end), 1-px sides, a dot
 * inside each corner. t = 1 for a selected cover (inverted: its outline becomes the 1-px gap). */
static void prect(const D *d, int l, int y, int dot, int x, int yy, int w, int h)
{
    int i, j;
    for (i = 0; i < w; i++)
        for (j = 0; j < h; j++)
            if (!dot || ((x + i + yy + j) & 1) == 0) fill(d, l + x + i, y + yy + j, 1, 1, 1);
}

static void pill(const D *d, int l, int y, int dot, int t)
{
    prect(d, l, y, dot, 1, 0, CW - 2, 1);
    prect(d, l, y, dot, 0, 1, CW, t - 1);
    prect(d, l, y, dot, 0, CH - t, CW, t - 1);
    prect(d, l, y, dot, 1, CH - 1, CW - 2, 1);
    prect(d, l, y, dot, 0, t, 1, CH - 2 * t);
    prect(d, l, y, dot, CW - 1, t, 1, CH - 2 * t);
    prect(d, l, y, dot, 1, t, 1, 1);
    prect(d, l, y, dot, CW - 2, t, 1, 1);
    prect(d, l, y, dot, 1, CH - 1 - t, 1, 1);
    prect(d, l, y, dot, CW - 2, CH - 1 - t, 1, 1);
}

static void part(const char *s, int off, char *o)       /* 5 chars of the name from off, NUL-safe */
{
    int i;
    for (i = 0; i < off; i++) if (!s[i]) { o[0] = 0; return; }
    for (i = 0; i < 5 && s[off + i]; i++) o[i] = s[off + i];
    o[i] = 0;
}

static void cover(const D *d, int slot, int l, int cy)
{
    int y = cy - 9, cur = d->cur == slot;
    char a[6], z[6];
    const char *nm = d->c->name[slot] ? d->c->name[slot] : "";
    clear(d, l, y, CW, CH, cur);
    pill(d, l, y, !d->c->on[slot], cur && d->c->sel ? 1 : 2);
    part(nm, 0, a); part(nm, 5, z);
    t7(d, a, l + 1 + (CW - 2 - w5(a, 1)) / 2, y + 2);
    t7(d, z, l + 1 + (CW - 2 - w5(z, 1)) / 2, y + 10);
    if (cur) mark(d, l, y, CW, CH, d->c->sel);
}

/* ---- [ROUTE] / [MIX] nodes -------------------------------------------------------------- */
/* Mode icons: lines of [knot count, then x y per knot] x 0 (output) to 29 (input), rows 0-13; 0 ends. */
static const unsigned char IC_SERIAL[] = { 2, 0, 6, 29, 6, 0 };
static const unsigned char IC_PARAL[] = { 4, 0, 2, 11, 2, 19, 6, 29, 6,  4, 0, 10, 11, 10, 19, 6, 29, 6, 0 };
static const unsigned char IC_STEREO[] = { 6, 0, 2, 5, 2, 13, 6, 16, 6, 24, 2, 29, 2,
                                           6, 0, 10, 5, 10, 13, 6, 16, 6, 24, 10, 29, 10, 0 };

static void icon(const D *d, const unsigned char *p, int x, int y)
{
    int n, i, cx, x0, y0, x1, y1, dx, t;
    while (*p) {
        n = *p++;
        for (i = 1; i < n; i++) {
            x0 = p[2 * i - 2]; y0 = p[2 * i - 1]; x1 = p[2 * i]; y1 = p[2 * i + 1];
            dx = x1 - x0;
            for (cx = x0; cx <= x1; cx++)   /* y0 + (y1 - y0) * (cx - x0) / dx, rounded half up */
                fill(d, x + cx, y + (2 * (y0 * dx + (y1 - y0) * (cx - x0)) + dx) / (2 * dx), 1, 2, 1);
        }
        t = p[1];
        fill(d, x + 1, y + t - 1, 2, 4, 1); fill(d, x + 3, y + t - 2, 2, 6, 1);   /* arrowhead pointing left */
        p += 2 * n;
    }
}

static void node(const D *d, int n, int l)      /* stock EXIT box as wide as a cover, as tall as both bus rows */
{
    int top = YA - 9, h = YB - YA + CH, cur = d->cur == n;
    const char *name = n == IT_ROUTE ? "ROUTE" : "MIX";
    clear(d, l, top, CW, h, cur);
    sq(d, l, top, CW, h);
    t7(d, name, l + 1 + (CW - 2 - w5(name, 1)) / 2, top + 2);
    icon(d, n == IT_MIX ? IC_STEREO : d->c->mode ? IC_PARAL : IC_SERIAL, l + 4, YC - 6);
    if (cur) mark(d, l, top, CW, h, d->c->sel);
}

/* ---- IN / OUT plugs -------------------------------------------------------------------- */
/* The stock IN plug, pixel for pixel (OUT is its mirror): x from the stub's left end, y from the top. */
static const unsigned char PLUG[15][4] = {
    {0,3,4,4}, {3,7,1,1}, {4,1,1,2}, {4,7,1,2},
    {5,0,13,1}, {5,9,13,1}, {18,0,1,10},
    {19,2,5,1}, {19,7,5,1}, {21,3,2,4},
    {24,3,1,1}, {24,6,1,1}, {25,2,2,1}, {25,7,2,1}, {27,3,1,4} };

static int px(int out, int l, int x, int w) { return out ? l + CW - 1 - (x - l) - (w - 1) : x; }

/* Output Mode Stereo: OUT always has both plugs, IN one. straight: a node sits next to the plug, so the
 * cables run straight in at the plug rows; otherwise one cable at YC with a riser to each plug. */
static void jack(const D *d, int out, int l, int straight)
{
    int ys[2], ln, n = out ? 2 : 1, i, r, k, x, x0 = l + 5, top;
    ys[0] = out ? YA : YC; ys[1] = YB;
    for (i = 0; i < n; i++) {
        top = ys[i] - 4;
        for (k = 0; k < 15; k++)
            fill(d, px(out, l, x0 + PLUG[k][0], PLUG[k][2]), top + PLUG[k][1], PLUG[k][2], PLUG[k][3], 1);
        for (r = 1; r <= 8; r++) {      /* the ridges */
            fill(d, px(out, l, x0 + 7 + (r % 2 ? 0 : 1), 1), top + r, 1, 1, 1);
            fill(d, px(out, l, x0 + 14 + (r % 2 ? 0 : 1), 1), top + r, 1, 1, 1);
        }
        x = px(out, l, l + 2, 1);       /* the risers share one vertical line */
        ln = out && straight ? ys[i] : YC;
        hspan(d, x, px(out, l, x0, 1), ys[i]);
        hspan(d, px(out, l, l, 1), x, ln);
        fill(d, x, ys[i] < ln ? ys[i] : ln, 1, (ys[i] < ln ? ln - ys[i] : ys[i] - ln) + 1, 1);
    }
    if (d->cur == (out ? IT_OUT : IT_IN)) mark(d, l, ys[0] - 4, CW, ys[n - 1] - ys[0] + 10, 0);
    if (out && d->c->limit) {           /* LIMIT tag between the two plugs */
        fill(d, l + 9, YC - 3, w3("LIMIT") + 2, 7, 1);
        t3(d, "LIMIT", l + 10, YC - 2, 0);
    }
}

/* ---- the screen ----------------------------------------------------------------------- */
static int zone_of(const Chain *c, int slot)
{
    int b, i;
    for (b = 0; b < 4; b++)
        for (i = 0; i < c->nz[b]; i++) if (c->z[b][i] == slot) return b;
    return -1;
}

/* The fan in the gap between column j (right) and j + 1 (left): 1 split (before [ROUTE]), 2 join (after [MIX]). */
static int fan_of(const Col *cols, int nc, int par, int j)
{
    if (!par || j < 0 || j + 1 >= nc) return 0;
    if (cols[j + 1].kind == K_NODE && cols[j + 1].e == IT_ROUTE) return 1;
    return cols[j].kind == K_NODE && cols[j].e == IT_MIX ? 2 : 0;
}

static void softkeys(const D *d, const char *lab[3], const char *hint[3])
{
    static const unsigned char XW[3][2] = { {0, 41}, {43, 41}, {86, 42} };
    int i, w, x, h;
    for (i = 0; i < 3; i++) {
        x = XW[i][0]; w = XW[i][1];
        fill(d, x, 56, w, 8, 1);
        h = hint[i][0] ? w3(hint[i]) + 3 : 0;      /* a hint sits at the key's left end, the label centred in the rest */
        if (h) t3(d, hint[i], x + 1, 57, 0);
        t3(d, lab[i], x + h + (w - h - w3(lab[i])) / 2, 57, 0);
    }
}

void chain_draw(const Chain *c, unsigned char fb[64][16])
{
    D d;
    Col cols[16];
    int X[16], nc = 0, k, i, j, n, par = c->mode == 1, cur = c->cur;
    int sel = c->sel, del = c->delp, onbus, fx, nm, ab, zn;
    const char *lab[3], *hint[3];

    for (j = 0; j < 64; j++) for (i = 0; i < 16; i++) fb[j][i] = 0;
    if (!par && cur == IT_MIX) cur = IT_ROUTE;      /* Serial has no [MIX] */
    d.fb = fb; d.c = c; d.cur = cur;

    cols[nc].kind = K_IN; cols[nc].e = IT_IN; cols[nc].a = cols[nc].b = -1; nc++;
    for (i = 0; i < c->nz[PRE]; i++) { cols[nc].kind = K_EFF; cols[nc].e = c->z[PRE][i]; cols[nc].a = cols[nc].b = -1; nc++; }
    cols[nc].kind = K_NODE; cols[nc].e = IT_ROUTE; cols[nc].a = cols[nc].b = -1; nc++;
    if (par) {
        n = c->nz[BUS_A] > c->nz[BUS_B] ? c->nz[BUS_A] : c->nz[BUS_B];
        if (n < 1) n = 1;
        for (i = 0; i < n; i++) {
            cols[nc].kind = K_BUS; cols[nc].e = -1;
            cols[nc].a = i < c->nz[BUS_A] ? c->z[BUS_A][i] : -1;
            cols[nc].b = i < c->nz[BUS_B] ? c->z[BUS_B][i] : -1;
            nc++;
        }
        cols[nc].kind = K_NODE; cols[nc].e = IT_MIX; cols[nc].a = cols[nc].b = -1; nc++;
    } else {                                        /* zones A then B in a row */
        for (j = BUS_A; j <= BUS_B; j++)
            for (i = 0; i < c->nz[j]; i++) { cols[nc].kind = K_EFF; cols[nc].e = c->z[j][i]; cols[nc].a = cols[nc].b = -1; nc++; }
    }
    for (i = 0; i < c->nz[POST]; i++) { cols[nc].kind = K_EFF; cols[nc].e = c->z[POST][i]; cols[nc].a = cols[nc].b = -1; nc++; }
    cols[nc].kind = K_OUT; cols[nc].e = IT_OUT; cols[nc].a = cols[nc].b = -1; nc++;

    for (k = 0, i = 0; i < nc; i++)
        if (cols[i].e == cur || cols[i].a == cur || cols[i].b == cur) { k = i; break; }

    X[k] = 45;                                      /* 3 columns at 3 / 45 / 87, the cursor's in the middle */
    for (i = k - 1; i >= 0 && i >= k - 2; i--) X[i] = X[i + 1] + CW + (fan_of(cols, nc, par, i) ? 7 : 4);
    for (i = k + 1; i < nc && i <= k + 2; i++) X[i] = X[i - 1] - CW - (fan_of(cols, nc, par, i - 1) ? 7 : 4);

    for (j = k - 2; j <= k + 1; j++) {              /* lines in the gap between column j and j + 1, out to the edges */
        int g, w, f, s = -1;
        if (j < 0 || j + 1 >= nc) continue;
        g = X[j + 1] + CW; w = X[j] - g; f = fan_of(cols, nc, par, j);
        if (cols[j].kind <= K_OUT && cols[j + 1].kind == K_NODE) s = j;          /* a jack next to a node */
        else if (cols[j + 1].kind <= K_OUT && cols[j].kind == K_NODE) s = j + 1;
        if (s >= 0) {
            if (cols[s].kind == K_IN) fill(&d, g, YC, w, 1, 1);
            else { fill(&d, g, YA, w, 1, 1); fill(&d, g, YB, w, 1, 1); }          /* OUT: both plug rows */
        } else if (f) {                             /* one riser; 3 cols clear of a cursor frame */
            int x = f == 1 ? g + 3 : g + w - 4;
            hspan(&d, f == 1 ? g + w - 1 : g, x, YC);
            hspan(&d, f == 1 ? g : g + w - 1, x, YA);
            hspan(&d, f == 1 ? g : g + w - 1, x, YB);
            fill(&d, x, YA, 1, YB - YA + 1, 1);
        } else if (cols[j].kind == K_BUS || (cols[j].kind == K_NODE && par)) {
            fill(&d, g, YA, w, 1, 1); fill(&d, g, YB, w, 1, 1);
        } else if (cols[j].kind != K_OUT) {
            fill(&d, g, YC, w, 1, 1);
        }
    }
    for (i = k - 1; i <= k + 1; i++) {
        int l;
        if (i < 0 || i >= nc) continue;
        l = X[i];
        if (cols[i].kind == K_IN) jack(&d, 0, l, 0);
        else if (cols[i].kind == K_OUT) jack(&d, 1, l, cols[i - 1].kind == K_NODE);
        else if (cols[i].kind == K_NODE) node(&d, cols[i].e, l);
        else if (cols[i].kind == K_EFF) cover(&d, cols[i].e, l, YC);
        else {
            if (cols[i].a >= 0) cover(&d, cols[i].a, l, YA); else fill(&d, l, YA, CW, 1, 1);
            if (cols[i].b >= 0) cover(&d, cols[i].b, l, YB); else fill(&d, l, YB, CW, 1, 1);
        }
    }

    /* title bar with the scroll arrows, then the softkeys with the knob hints */
    fill(&d, 0, 0, 128, 9, 1);
    t5(&d, "EFFECT CHAIN", 64 - w5("EFFECT CHAIN", 1) / 2, 1, 0, 1);
    if (k + 2 < nc) t3(&d, "<", 1, 2, 0);
    if (k - 2 >= 0) t3(&d, ">", 124, 2, 0);

    zn = cur >= 0 && cur < 6 ? zone_of(c, cur) : -1;
    onbus = zn == BUS_A || zn == BUS_B;
    fx = sel && cur >= 0 && cur < 6;
    nm = sel && (cur == IT_ROUTE || cur == IT_MIX);
    ab = (fx || (!sel && par && onbus && c->nz[zn == BUS_A ? BUS_B : BUS_A] > 0)) && !del && onbus && par;
    if (del) { lab[0] = ""; lab[1] = "DELETE?"; lab[2] = ""; }
    else if (sel) {
        lab[0] = "DROP"; lab[1] = fx ? "DELETE" : "";
        lab[2] = nm ? (cur == IT_MIX ? "STEREO" : par ? "PARAL" : "SERIAL") : ab ? "A/B" : "";
    } else { lab[0] = cur == IT_IN || cur == IT_OUT ? "" : "SELECT"; lab[1] = "EXIT"; lab[2] = "OPEN"; }
    hint[0] = "{}"; hint[1] = fx && !del ? "HOLD" : ""; hint[2] = nm ? "{}" : ab ? "^v" : "";
    softkeys(&d, lab, hint);
}
