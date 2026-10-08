# MIDI transport block (issue #24)

From MOD 0.4 the firmware publishes MIDI transport for custom effects in RAM.
Effects read it with plain loads; nothing calls into the firmware.
MS-50G 3.10 OS only (the build the MS-60B runs as MOD).

## Where

Address **`0x1181FF00`** (L2 RAM, 32 bytes, 8 words). It is loaded at boot,
so it is valid before any MIDI arrives.

| word | offset | meaning |
|---|---|---|
| 0 | 0 | magic + version **`0x5A4D5401`** ("ZMT", version 1). Anything else: no transport (stock or older firmware) |
| 1 | 4 | sequence: +1 before and +1 after each update (odd = mid-write) |
| 2 | 8 | running: 1 after Start (`0xFA`); 0 after Stop (`0xFC`) or 0.5 s with no clock |
| 3 | 12 | start counter: +1 on every Start |
| 4 | 16 | clocks (`0xF8`) received since the last Start, counted only while running. The first clock after Start (value 1) is the downbeat, so the position in 24ths of a quarter note is value - 1 |
| 5 | 20 | tempo, BPM x 100 (4000..25000). Always valid, see below |
| 6, 7 | 24 | reserved, 0 |

Continue (`0xFB`) and Song Position are ignored.

**Tempo:** while MIDI clock comes in, the clock tempo measured over up to 8
beats (0.1 BPM steps, updated every beat). Otherwise the patch TEMPO (tap
tempo, the TEMPO setting, patch load), copied within 16 ms of a change; 120.00
at power-on until the first copy. When the clock stops, the last clock tempo
stays until TEMPO is changed. The patch TEMPO keeps following the clock in
whole BPM for stock effects, as in MOD 0.3.

## Reading it

Updates are written with interrupts off, and the pedal has one CPU core, so
an effect never sees half an update. The sequence word is there anyway, so a
reader stays correct if that ever changes:

```c
#define ZMT ((volatile unsigned int *)0x1181FF00)
#define ZMT_MAGIC 0x5A4D5401u

/* 1 when the block is there and was read whole. */
static int zmt_read(unsigned int *run, unsigned int *starts,
                    unsigned int *clocks, unsigned int *bpm100)
{
    unsigned int s, tries;
    if (ZMT[0] != ZMT_MAGIC) return 0;
    for (tries = 0; tries < 4; tries++) {
        s = ZMT[1];
        if (s & 1) continue;
        *run = ZMT[2]; *starts = ZMT[3]; *clocks = ZMT[4]; *bpm100 = ZMT[5];
        if (ZMT[1] == s) return 1;
    }
    return 0;
}
```

An effect restarts when the start counter changes, places itself between
clocks with its own sample counter (44.1 kHz), and runs on at the tempo word
when not running.

## How (firmware side)

- `asm/midi_clock/clock.S` (Task_MIDI hook, every received byte): Start sets
  running, bumps the start counter and clears the clock count; Stop clears
  running; each clock adds 1 while running; each beat measurement writes the
  tempo.
- `asm/midi_clock/poll.S` (Task_SwitchNrmlSpdRead, every 16 ms, in place of
  its `Clock_getTicks` call at `0xC00CA630`): clears running after 0.5 s
  without a clock (and 0.5 s after Start), and copies a changed patch TEMPO
  when the clock is not live.
- Layout constants: `asm/midi_clock/transport.inc`.
- MIDI settings page (v0.5, issue #26): with SETTINGS > MIDI START/STOP set
  to OFF, Start, Stop and the clock count are ignored and turning it off
  clears running (like a Stop). MIDI CLOCK set to OFF only stops the clock
  setting the tempo. The block's address, magic and layout do not change.
