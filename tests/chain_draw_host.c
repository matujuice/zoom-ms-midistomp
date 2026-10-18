/* Host driver for asm/mixer/chain_draw.c: draws the six preview states and writes each
 * framebuffer (64 rows x 16 bytes) to <outdir>/<name>.fb. Run by scripts/chain_draw_preview.py. */
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

/* (a) layout: Parallel, PRE 1 / A 1 / B 2 (one OFF) / POST 1; slots 0 DirtBox, 1 GridDly, 2 Breather, 3 Sweep, 4 EuGate */
static void patch(Chain *c, int mode)
{
    memset(c, 0, sizeof *c);
    c->mode = mode; c->busrow = BUS_A;
    add(c, PRE, "DirtBox", 1); add(c, BUS_A, "GridDly", 1);
    add(c, BUS_B, "Breather", 1); add(c, BUS_B, "Sweep", 0); add(c, POST, "EuGate", 1);
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

int main(int argc, char **argv)
{
    Chain c;
    const char *dir = argc > 1 ? argv[1] : ".";

    patch(&c, 1); c.cur = 1;                    /* a: cursor on the A effect */
    out(dir, "a_parallel", &c);

    patch(&c, 0); c.n = 0; memset(c.nz, 0, sizeof c.nz);        /* b: Serial with 3 effects */
    add(&c, PRE, "DirtBox", 1); add(&c, BUS_A, "GridDly", 1); add(&c, POST, "EuGate", 1);
    c.cur = 1;
    out(dir, "b_serial", &c);

    patch(&c, 1); c.n = 0; memset(c.nz, 0, sizeof c.nz);        /* c: empty buses, [ROUTE] selected */
    add(&c, PRE, "DirtBox", 1); add(&c, POST, "EuGate", 1);
    c.cur = IT_ROUTE; c.sel = 1;
    out(dir, "c_empty_route", &c);

    patch(&c, 1); c.n = 0; memset(c.nz, 0, sizeof c.nz);        /* d: 6 effects, cursor in the middle */
    add(&c, PRE, "DirtBox", 1); add(&c, BUS_A, "GridDly", 1); add(&c, BUS_A, "Choral", 1);
    add(&c, BUS_B, "Breather", 1); add(&c, BUS_B, "Sweep", 1); add(&c, POST, "EuGate", 1);
    c.cur = 2;
    out(dir, "d_scroll", &c);

    patch(&c, 1); c.cur = 2; c.sel = 1; c.busrow = BUS_B;       /* e: a selected bus effect */
    out(dir, "e_selected_bus", &c);

    patch(&c, 1); c.cur = 4; c.sel = 1; c.delp = 1; c.limit = 1;  /* f: DELETE? and LIMIT on */
    out(dir, "f_delete_limit", &c);
    return 0;
}
