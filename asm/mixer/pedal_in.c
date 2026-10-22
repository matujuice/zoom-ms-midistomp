/* Mixer Mode: PEDAL INPUT (MONO/STEREO, default MONO), a 9th row of the SETTINGS
 * list (screen 1, asm/midi_settings/settings.S, which has no room left in L2).
 * The row shows the value; ENTER flips it and saves record 50, where it is bit 7
 * of byte 23 (settings.S packs bits 0, 5 and 6 there). It lives in mixer.S data
 * (PEDAL, chain.h): STEREO draws double lines from IN and allows the Split and
 * Mono Serial modes; MONO plays them as Parallel and Serial. */
#include "chain.h"
#include "stock.h"

/* settings.S, fixed by patches/midi-settings.yaml */
#define SETTINGS_NAMES ((const char *const *)0x1181EB94)
#define SETTINGS_ICONS ((const unsigned char *)0x1181EC24)
#define SETTINGS_KEYS FN(0x1181F164, int, (long long ev))     /* the event pair in A5:A4 */
#define DRAW_LIST FN(0x1181ED20, void, (const char *title, const char *const *names, int rows, \
                                        const unsigned char *icons, int stride, const char *left))
#define PACK_HOOK FN(0x1181EA80, void, (unsigned char *rec, int *words))
#define UNPACK_HOOK FN(0x1181EA88, void, (int *words, unsigned char *rec))

#define LIST_INDEX FN(0xC00A7040, int, (void))                 /* -> row + top */
#define LIST_SCROLL FN(0xC00A72D4, void, (int delta, int rows))
#define SAVE_SETTINGS FN(0xC00BA3E4, void, (int *words))       /* writes record 50 */
#define SETTINGS_WORDS ((int *)0xC009D8F8)
#define STR_SETTINGS ((const char *)0xC00E9004)
#define STR_ENTER ((const char *)0xC00E90F6)
#define EV_ENTER 34
#define EV_TURN 160
#define ROW_PEDAL 8

static const char *names[ROW_PEDAL + 1];
static unsigned char icons[7 * (ROW_PEDAL + 1)];
static const unsigned char plug[7] = {0x08, 0x08, 0x1c, 0x3e, 0x3e, 0x3e, 0x08};

int settings_key(int ev, int steps)
{
    if (ev == EV_TURN) {
        LIST_SCROLL(steps, ROW_PEDAL + 1);
        return 1;
    }
    if (ev == EV_ENTER && LIST_INDEX() == ROW_PEDAL) {
        PEDAL ^= 1;
        if (!PEDAL && LIVE[S_MODE] > 1)     /* the patch played falls back, as the mockup */
            LIVE[S_MODE] = LIVE[S_MODE] == 2;
        SAVE_SETTINGS(SETTINGS_WORDS);
        return 1;
    }
    return SETTINGS_KEYS((long long)steps << 32 | (unsigned)ev);
}

void settings_draw(void)
{
    int i;
    for (i = 0; i < 7 * ROW_PEDAL; i++)
        icons[i] = SETTINGS_ICONS[i];
    for (i = 0; i < 7; i++)
        icons[7 * ROW_PEDAL + i] = plug[i];
    for (i = 0; i < ROW_PEDAL; i++)
        names[i] = SETTINGS_NAMES[i];
    names[ROW_PEDAL] = PEDAL ? "STEREO INPUT" : "MONO INPUT";
    DRAW_LIST(STR_SETTINGS, names, ROW_PEDAL + 1, icons, 7, STR_ENTER);
}

/* Called instead of settings.S pack_hook / unpack_hook (their DDR trampolines). */
void settings_pack(unsigned char *rec, int *words)
{
    PACK_HOOK(rec, words);
    rec[23] |= PEDAL << 7;
}

void settings_unpack(int *words, unsigned char *rec)
{
    UNPACK_HOOK(words, rec);
    PEDAL = rec[23] >> 7;
}
