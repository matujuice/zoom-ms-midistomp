/* MS-70CDR 2.10 OS addresses chain_keys.c uses (docs/mixer-mode-m3-research.md
 * "M3b"). Stock functions are plain C ABI (args A4, B4, A6, B6, A8, B8). */
#ifndef STOCK_H
#define STOCK_H

/* B14 is the OS's constant data pointer: its variables as absolute addresses,
 * so our far-data C never needs (or writes) B14. */
#define B14 0xC00EF748u
#define BV(off) (*(volatile int *)(B14 + (off)))
#define MODE BV(320)                /* 11 = menu screens, 0 = play */
#define SCREEN BV(352)              /* 3 = Effect Chain */
#define ROW BV(356)                 /* screen row; -2 marks "the chain screen is ours" */
#define ANCHOR BV(128)              /* add: the slot the new effect goes next to */
#define SIDE BV(132)                /* 1: on its left (slot + 1) */
#define MAILBOX BV(656)

#define COUNT (*(volatile int *)0xC009C068)          /* effects in the patch */
#define FX_REC(s) ((volatile int *)(0xC009BF58 + 44 * (s)))   /* [0] on, [1] effect id */
#define DSP_OFF (*(volatile int *)0xC009C060)        /* bit slot: bypassed, DSP full */
#define CURSOR (*(volatile signed char *)0xC009C064) /* play-mode cursor */
#define VIEW_KNOBS (*(volatile int *)0xC009D398)     /* play mode: 1 = knob pages */
#define SW_STATE (*(volatile int *)0xC009DF90)       /* switches, bit clear = down */
#define SW_KNOB2 1                                   /* medium confidence */

#define FN(addr, ret, args) ((ret (*) args)(addr))
#define SET_SCREEN FN(0xC00A75E0, void, (int screen, int row))
#define EVENT_POST FN(0xC00CBF40, void, (int mailbox, int event))
#define TIMER6 FN(0xC00C7D60, void, (int on))       /* cursor left hold -> event 230 */
#define TIMER7 FN(0xC00C7D50, void, (int on))       /* cursor right hold -> event 231 */
#define POPUP FN(0xC00CCB00, void, (int, unsigned, unsigned, int))
#define MAX_FX_TEXT 0xC00EBD5F, 0xC00EBD5E           /* "MAX EFFECT UNIT!" */
#define FX_NAME FN(0xC00B056C, const char *, (int slot, int one))
#define SLOT_AT FN(0xC00BA2D8, int, (int cursor))   /* play cursor -> slot, -1 */
#define TYPE_NEXT FN(0xC00CA670, int, (int id, int dir))
#define TYPE_SET FN(0xC00ABACC, int, (int slot, int id))
#define KNOBS_EXIT FN(0xC00CCD18, void, (int))      /* the callp kp_exit replaces */
#define S33_KEYS FN(0xC00A7A6C, int, (long long ev)) /* screens 32/33, the event pair in A5:A4 */
#define BLIT FN(0xC009F9B0, void, (int frame, int x, int y, int w, int h, const unsigned char *src))

/* mixer.S vectors */
#define MV_SWAP FN(0xC00F6000 + 96, void, (int row_a, int row_b))
#define MV_DELETE FN(0xC00F6000 + 112, void, (void))
#define HOLD (*(volatile int *)(0xC00F6000 + 80))    /* polls left to show LIMIT */
#define PAGE (*(volatile int *)(0xC00F6000 + 128))   /* MIXER screen page */

#endif
