/* Mixer Mode M3b: the Effect Chain screen (stock screen 3), shared by
 * chain_keys.c (model, keys, hooks) and chain_draw.c (pixels).
 * Design: docs/mixer-ui-mockup.html v20, docs/v2.0-brief.md "Effect Chain screen".
 * Build: TI cl6x, C6740 EABI, far data, no RTS (scripts/build_mixer_ui.py). */
#ifndef CHAIN_H
#define CHAIN_H

#define PRE 0                   /* bus codes, as LAYOUT (mixer.S) */
#define BUS_A 1
#define BUS_B 2
#define POST 3

/* Cursor items: a slot 0-5, or one of these. */
#define IT_ROUTE 0x10
#define IT_MIX 0x11
#define IT_IN 0x12
#define IT_OUT 0x13

/* Mixer data (mixer.S, BASE 0xC00F6000). */
#define MIXER_BASE 0xC00F6000u
#define LIVE ((volatile unsigned char *)(MIXER_BASE + 144))   /* [12] settings */
#define LAYOUT ((volatile unsigned char *)(MIXER_BASE + 156)) /* [6] bus of each slot */
#define SHOWN (*(volatile unsigned char *)(MIXER_BASE + 78))  /* LIMIT tag shown */
#define S_MODE 0                /* LIVE[S_MODE]: 0 Serial, 1 Parallel (M3c: 2 Split, 3 Mono Serial) */

/* UI state: the 8 bytes at +136 (were the routing probe's MAIL). */
#define UI ((volatile unsigned char *)(MIXER_BASE + 136))
#define UI_CUR 0                /* cursor item */
#define UI_SEL 1                /* 1: the item is selected (CHO look) */
#define UI_BUSROW 2             /* BUS_A or BUS_B: the bus row browsing walks */
#define UI_DELP 3               /* 1: DELETE? waits for a knob 2 press */
#define UI_ADDBUS 4             /* 0xFF, or the bus mv_add gives the next added effect */
#define UI_FROMCHAIN 5          /* 1: knob pages / MIXER pages opened from here, EXIT returns */
#define UI_PFIRST 6             /* MIXER screen page range when opened from a node / jack */
#define UI_PLAST 7

/* The chain as the screen shows it, built from the live patch. Slots stay
 * sorted by zone (PRE..., A..., B..., POST...), so each list is in slot
 * order; signal order = slot order = right to left on screen. */
typedef struct {
    int n;                      /* effects in the patch, 0-6 */
    int mode;                   /* LIVE[S_MODE] */
    int nz[4];                  /* effects per zone, indexed by bus code */
    unsigned char z[4][6];      /* slots per zone, in slot order */
    const char *name[6];        /* per slot: 10 chars, 2 lines of 5 (stock cover text) */
    unsigned char on[6];        /* per slot: 0 = drawn dotted (OFF or DSP-off) */
    int cur, sel, busrow, delp; /* UI state, as above */
    int limit;                  /* 1: LIMIT tag over OUT */
} Chain;

void chain_build(Chain *c);     /* chain_keys.c */

/* chain_draw.c: the whole 128 x 64 screen into fb, 1 bit per pixel,
 * row-major, bit 7 of byte 0 = pixel (0,0), 1 = ink. chain_keys.c sends it
 * to the LCD. */
void chain_draw(const Chain *c, unsigned char fb[64][16]);

#endif
