/* Perform mode storage: one PerfPatch (PT_SIZE bytes) per patch after the
 * mixer table in record 50 (R50, chain.h): stock 24 B, 50 mixer entries of
 * 16 B, a magic word, then 50 x PT_SIZE. Perform entries have no hash of
 * their own: entry n belongs to the patch whose hash is in mixer entry n
 * (pages.c), and is valid only when STORE wrote it (pad == PT_OK). An older,
 * 824-byte record 50 reads garbage after the mixer table: no magic, cleared. */
#include "perform.h"
#include "chain.h"
#include "stock.h"

#define PT_MAGIC 0x50524631u    /* "PRF1" */
#define PT_OK 0xA5
#define MAGIC_W (*(volatile unsigned *)(R50 + 824))
#define PT(n) ((volatile unsigned char *)R50 + 828 + PT_SIZE * (n))
#define ENT(n) ((volatile unsigned char *)R50 + 24 + 16 * (n))

extern unsigned r50_live_hash;  /* pages.c mix_get */
extern int perf_defaults;       /* perform_engine.c */
extern __cregister volatile unsigned int CSR;

static void check(void)
{
    int i;
    if (MAGIC_W == PT_MAGIC) return;
    for (i = 0; i < 50 * PT_SIZE; i++) PT(0)[i] = 0;
    MAGIC_W = PT_MAGIC;
}

static int find(int n)
{
    int i;
    check();
    if ((unsigned)n < 50 && *(volatile unsigned *)ENT(n) == r50_live_hash && PT(n)[15] == PT_OK)
        return n;
    for (i = 0; i < 50; i++)    /* a copy finds its original's entry, as the mixer table */
        if (*(volatile unsigned *)ENT(i) == r50_live_hash && PT(i)[15] == PT_OK) return i;
    return -1;
}

void perf_load(int patch)
{
    unsigned char *d = (unsigned char *)&perf_patch;
    int n = find(patch), i;
    unsigned c = CSR;
    CSR = c & ~1u;
    if (n >= 0) {
        for (i = 0; i < PT_SIZE; i++) d[i] = PT(n)[i];
        perf_defaults = 0;
    } else {                    /* none: the footswitch plays the GRDLOOP (aimed by the poll) */
        for (i = 0; i < PT_SIZE; i++) d[i] = 0;
        for (i = 0; i < NCTL; i++) perf_patch.target[i] = T_NONE;
        for (i = 0; i < NLOOP; i++) perf_patch.loop_target[i] = T_NONE;
        for (i = 0; i < NCTL * NMOVE_CTL; i++) perf_patch.move[0][i] = MV_UNUSED;
        for (i = 0; i < NLOOP; i++) perf_patch.loop_move[i] = MV_UNUSED;
        perf_patch.loop_target[L_REC_END] = 86;           /* MIX XFade B100 over 1 BAR */
        perf_patch.loop_move[L_REC_END] = MV(127, NX_NOW, 10);
        perf_patch.loop_target[L_DELETE] = 86;            /* MIX XFade A100, MICRO */
        perf_patch.loop_move[L_DELETE] = MV(0, NX_NOW, LG_MICRO);
        perf_defaults = 8;
    }
    CSR = c;
}

/* STORE (pages.c mix_put, after the mixer entry): the patch's Perform entry.
 * 1 when record 50 changed; rec_save then saves it. ponytail: the autosave of a
 * patch you leave (mix_put from PREV) keeps its old Perform entry. */
int perf_save(int patch)
{
    const unsigned char *s = (const unsigned char *)&perf_patch;
    volatile unsigned char *e;
    int i, changed = 0;
    unsigned char b;
    if ((unsigned)patch >= 50) return 0;
    check();
    e = PT(patch);
    for (i = 0; i < PT_SIZE; i++) {
        b = i == 15 ? PT_OK : s[i];
        changed |= e[i] != b;
        e[i] = b;
    }
    perf_defaults = 0;
    return changed;
}
