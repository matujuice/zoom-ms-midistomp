/* Chain screen states for the README and guide shots: asm/mixer/chain_draw.c with two filled buses, ROUTE and MIX on screen. Writes <dir>/<name>.fb (row format, 16 bytes per row). */
#include <stdio.h>
#include <string.h>
#include "chain.h"
static void add(Chain *c, int bus, const char *name, int on)    /* call in zone order PRE, A, B, POST */
{
    int s = c->n++;
    c->z[bus][c->nz[bus]++] = (unsigned char)s;
    c->name[s] = name;
    c->on[s] = (unsigned char)on;
}
static void out(const char *dir, const char *name, const Chain *c)
{
    unsigned char fb[64][16];
    char path[512];
    FILE *f;
    chain_draw(c, fb);
    sprintf(path, "%s/%s.fb", dir, name);
    f = fopen(path, "wb");
    if (!f) { perror(path); return; }
    fwrite(fb, 1, sizeof fb, f);
    fclose(f);
}
static void two(Chain *c, int stereo, int cur, const char *a, const char *b)
{
    memset(c, 0, sizeof *c); c->mode = 1; c->busrow = BUS_A; c->stereo = stereo;
    add(c, BUS_A, a, 1); add(c, BUS_B, b, 1); c->cur = cur;
}
int main(int argc, char **argv)
{
    Chain c; const char *d = argv[1];
    two(&c, 0, 0, "GridDly", "Breather"); out(d, "rm_a0", &c);
    two(&c, 0, 1, "GridDly", "Breather"); out(d, "rm_a1", &c);
    two(&c, 0, IT_ROUTE, "GridDly", "Breather"); out(d, "rm_route", &c);
    two(&c, 0, IT_MIX, "GridDly", "Breather"); out(d, "rm_mix", &c);
    two(&c, 0, 0, "DirtBox", "GridDly"); out(d, "rm_b0", &c);
    return 0;
}
