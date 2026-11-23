# Records 50 and 51: MIXER, PERFORM and MIDI settings (MS-70CDR 2.10, MIDISTOMP V2.0.3)

Records 50 and 51 are entries in the pedal's own flash record store (the store that also holds
patches 0-49, read with `REC_LOAD 0xC00B4AAC` and written with `REC_SAVE 0xC00B49F4`). They are
not files. Over MIDI they are reached with the MIDISTOMP SysEx commands 03 (MIXER entry write)
and 04/05 (PERFORM entry read and write), described in `modwerk-research.md`. All multi-byte
values are little-endian. Sources: `asm/mixer/pages.c`, `asm/mixer/mixer.S`, `asm/mixer/chain.h`,
`asm/perform/perform.h`, `asm/perform/perform_store.c`, `asm/midi_settings/settings.S`.

## Record 50 (11228 bytes; stock: 24)

| offset | size | what |
|---|---|---|
| 0 | 24 | stock globals. Byte 23: bit 0 stock, bits 1-3 IDLE KALEIDO (0 off, 1-4 = 10 s .. 2 min), bit 5 TEMPO LOCK, bit 6 HOLD FOR MOMENTARY, bit 7 PEDAL INPUT STEREO |
| 24 + 16n | 16 | MIXER entry of patch n (n = 0..49), below |
| 824 | 4 | PERFORM magic `0x50524633` ("PRF3"). Anything else: all PERFORM entries are cleared to 0 on first use |
| 828 + 208n | 208 | PERFORM entry of patch n (n = 0..49), below |

A record 50 of 824 bytes (v2.0 before PERFORM) has no magic: the PERFORM entries start empty.
A stock record (24 bytes) gives an empty table: every patch loads the defaults.

### MIXER entry (16 bytes)

| byte | what | max | default |
|---|---|---|---|
| 0-3 | key: FNV-1a (32-bit) over the patch record, see below | | |
| 4 | Mode: 0 Serial, 1 Parallel, 2 Split, 3 Mono Serial | 3 | 0 |
| 5 | ROUTE crossfade (Send) | 100 | 50 |
| 6 | Input Level (Split: Input L) | 150 | 100 |
| 7 | ROUTE Bus A level | 150 | 100 |
| 8 | ROUTE Bus B level | 150 | 100 |
| 9 | MIX crossfade | 100 | 50 |
| 10 | Master (Output Split: Master L) | 150 | 100 |
| 11 | Curve: 0 Smooth, 1 DJ, 2 Cut | 2 | 1 |
| 12 | MIX Bus A level | 150 | 100 |
| 13 | MIX Bus B level | 150 | 100 |
| 14 | Bus B phase: 0 Normal, 1 Invert | 1 | 0 |
| 15 | pad, 0 | | |

Levels: 100 = unity. A value over its max loads as the default. The key is computed over the
122-byte packed patch record (the one SysEx patch dumps carry):

```c
unsigned h = 2166136261u;                       /* FNV-1a, prime 16777619 */
for (i = 0; i < 6; i++) {                       /* the 6 effect blocks, 18 bytes each */
    const unsigned char *b = rec + 18 * i;      /* effect id = bits 1-28 of the block */
    h = (h ^ (b[0] & 0xFE)) * 16777619u;
    h = (h ^ b[1]) * 16777619u;
    h = (h ^ b[2]) * 16777619u;
    h = (h ^ (b[3] & 0x1F)) * 16777619u;
}
for (i = 111; i < 122; i++) h = (h ^ rec[i]) * 16777619u;   /* the name */
```

Loading patch n: entry n if its key matches, otherwise the first entry with the same key (a
copied patch keeps its original's settings), otherwise the defaults. So two patches with the
same 6 effects and the same name share settings until one is stored. A store writes entry n.

Not in record 50: Input R, Master R, Output Mode, Mute A/B and Solo ride in byte 17 of the six
effect blocks of the patch record itself (`mix_put` in `pages.c`; bit 6 of block 5's byte 17
marks the current packing).

### PERFORM entry (208 bytes, `PerfPatch` in `perform.h`)

No key of its own: entry n belongs to the patch whose key is in MIXER entry n, and is valid only
when byte 15 is `0xA5` (STORE writes it). Lookup: entry n if MIXER entry n has the patch's key
and byte 15 is `0xA5`, otherwise the first entry that has both, otherwise empty (all targets
`0xFF`, all moves unused).

| offset | size | what |
|---|---|---|
| 0 | 1 | CYCLE in bars 1-32, 0 = none |
| 1 | 7 | target per control: knob 1, knob 2, knob 3, ◄, ▼, ►, footswitch |
| 8 | 6 | LOOPER target per event: rec start, rec end, play, stop, delete, loop start |
| 14 | 1 | LOOPER events on (1) |
| 15 | 1 | `0xA5` = valid |
| 16 | 168 | moves, 7 controls x 6 moves x 4 bytes: turn-follow, press-action, press-follow, hold-action, hold-release, hold-follow. Buttons and the footswitch leave turn-follow unused |
| 184 | 24 | LOOPER moves, 6 x 4 bytes, same order as the targets |

Target byte: 0-127 = that MIDI CC as the pedal's own CC chart reads it (mixer CCs 85-101
included); `0x80 + s` = the footswitch of the looper in slot s (0-5); `0xFF` = none.

Move word (4 bytes):

| bits | what |
|---|---|
| 0-15 | value in the target's own units (an effect knob's steps, a mixer level) |
| 16-20 | NEXT: 0 now, 1-4 = 1/2/4/8 beats, 5-10 = 1/2/4/8/16/32 bars, 31 = move unused |
| 21-24 | LAG: 0 off, 1 micro, 2-4 = 50/100/500 ms, 5 = 1 s, 6-9 = 1/2/4/8 beats, 10-15 = 1/2/4/8/16/32 bars |
| 25 | EVEN: 1 = equal time per step through the lag |
| 26-31 | 0 |

## Record 51 (4 bytes; stock: 4)

One 32-bit word. Stock uses bits 0-7 only (the last patch, 0-49). A stock record has 0 in the
rest, which means all defaults.

| bits | what |
|---|---|
| 0-7 | last patch played (stock) |
| 8-11 | receive off for MIDI clock, transport, Program Change, Control Change (bit 8 = clock) |
| 12 | PROG CH START NO.: 0 = PC 1 loads patch 1 (the default), 1 = stock numbering |
| 13-17 | MIDI channel, 0 = OMNI, 1-16 |
| 18-31 | 0 |
