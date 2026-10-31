/* GRDLOOP patch-load hook (MS-70CDR 2.10 OS). Replaces looper.S draw_pre at the callp 0xC00BB0EC
 * (patches/looper.yaml). Until v2.0 it also drew GRDLOOP's status bar into the framebuffer when
 * S_MINE was set; S_MINE lags the screen by one poll, so the bar sometimes showed on other
 * effects' covers. GRDLOOP now draws the bar into its own cover (the pack's looper.c lp_bar), so
 * this only drops the old claim on a patch load. Perform mode's bar is asm/perform/perform_draw.c.
 * Data: docs/dev/looper-services.md. Built by scripts/build_looper_ui.py. */

#define FN(addr, ret, args) ((ret (*) args)(addr))
#define SV(off) (*(volatile unsigned *)(0xC00F3000u + (off)))
#define S_CLAIM 32
#define S_SLOT 40
#define S_MINE 48
#define CUR_PATCH (*(volatile int *)(0xC00EF748u + 324))  /* patch played, 0-49 */
#define LCD_GATE FN(0xC00D5720, int, (int))               /* the stock call we sit in front of */

/* the callp at 0xC00BB0EC: A4 = the stock call's argument */
int lbox_draw(int a4)
{
    static int seen = -1;
    if (CUR_PATCH != seen) {                              /* a patch load: drop the old claim (a new effect in the same slot can share its pointer); the ZDL re-claims */
        seen = CUR_PATCH;
        SV(S_CLAIM) = 0; SV(S_SLOT) = (unsigned)-1; SV(S_MINE) = 0;
    }
    return LCD_GATE(a4);
}
