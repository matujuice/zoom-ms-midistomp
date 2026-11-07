# MIDISTOMP feature dependencies (MS-70CDR 2.10)

Which release patches need which, for anyone (Modwerk) who wants to offer them as separate
mods. Taken from the patch files on 2026-11-06 (V2.0.1): a patch "needs" another when one of
its `write` entries expects bytes the other one writes, or its code calls into the other's
sections. Every patch has its own fixed addresses, so none overlap; only the order matters.

## Table

| Patch | Needs | Why |
|-------|-------|-----|
| version-2.0.1 | - | |
| boot-logo | - | BIN/133 only |
| midi-cc | - | owns the CC handler (0xC00F2800) and its step (0xC00F2020) |
| midi-clock | - | owns the transport block (0x1181FF00, `transport.inc`) and the poll hook (0x1181E800) |
| midi-settings | midi-cc, midi-clock | patches midi-cc's handler; reads the transport block |
| tempo-hold | - | stands alone; its hold vars sit next to midi-settings' (0x1181EA00 area), no bytes expected |
| scroll | - | |
| dsp-limit | - | one write |
| fx-category | - | |
| identity-tag | - | one write; the tag follows the release version |
| looper | midi-cc, midi-clock, tempo-hold | takes over midi-clock's poll trampoline, calls the CC handler and tempo-hold's hold/toggle hooks, uses transport word 6 |
| mixer-m2 (Mixer + Perform mode) | midi-cc, midi-clock, midi-settings; looper optional | poll trampoline at 0xC00C82D0 accepts midi-clock's or looper's bytes; relinks midi-cc's step; adds to the midi-settings menu |
| diag | midi-clock, midi-settings | reads clock vars; its page sits in the settings menu |

Apply order: the order of `PATCHES` in `scripts/midistomp_builder.py` (BASE first, then
looper, mixer-m2, diag, ...). looper must come before mixer-m2.

## Suggested split

- **Base (always on):** midi-cc, midi-clock, midi-settings. Almost everything else hooks into
  them; the transport block is how effects see MIDI clock and transport, so it belongs here.
- **Free-standing extras:** boot-logo, version string, identity-tag, tempo-hold, scroll,
  dsp-limit, fx-category. Any subset works on top of stock or the base.
- **Needs the base:** diag; looper (also tempo-hold); mixer-m2, which is Mixer and Perform mode in one patch (looper optional).

Not checked here: whether every free-standing patch also builds without the base (each one's
`expect` is stock bytes, so it should). The release test in Modwerk only covers the full set.
