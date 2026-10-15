# Mixer Mode M0: chain runner, DSP budget, patch room (MS-70CDR 2.10 OS)

Status 2026-10-15. Static analysis only: disassembly of the stock MS-70CDR 2.10 OS
(`tic6x-elf-objdump`) and the 137 stock ZDLs from the same updater. Nothing was built or flashed.
Plan: `docs/mixer-mode-plan.md`. Labels: **[C]** = confirmed in the disassembly, **[I]** = inferred.
All addresses are MS-70CDR 2.10. B14 = `0xC00EF748`.

**Verdict: GO.** The chain is a plain loop over 6 slots that all work in place on one shared
stereo buffer. Bus B fits in a DDR routine that copies that buffer between slot calls, with one
32-byte hook in L2. The DSP check is a sum of per-effect costs against a constant, so it keeps
working unchanged. Two limits shape M2: the patch record has only **51 spare bits**, and the
real CPU headroom is unknown until a probe measures it.

## 1. Chain runner

**Audio block** (L2 call list at `0x1181BDE0`, once per DMA half-buffer = **8 frames**:
RX ACNT 8, BCNT 16, 4 words per frame, and the `to_float` loop runs 8 times) **[C]**. At 44.1 kHz
and 456 MHz that is about 82 700 cycles per block **[I: clock from `docs/ms70cdr-port.md`]**.

| order | address | what | label |
|---|---|---|---|
| 1 | `0x1181BF60` -> `0xC00E14C0` | save registers | C |
| 2-3 | `0x1181BBC0`, `0x1181BCE0` | input housekeeping | I |
| 4-6 | `0x1181BB0C`, `0x1181B680`, `0x1181B8C0` | rx_deint, in_combine, to_float | C |
| 7 | `0x1181AFA0` | pre-chain: zero the accumulator `0x11F03778`, copy the chain input to `0x11F037F8` (snapshot), interrupts off | C (stores), I (purpose of the snapshot) |
| 8 | `0x1181B340` | reads the dry buffer; input analysis (tuner/level) | I |
| 9 | `0x1181BE00`-`0x1181BE47` | **slot loop** (below) | C |
| 10 | `0x1181B090` | post mix: `F = ((F + Acc) * g1 + Snap * g2) * g3`, gains at `0x11F03B64/68/6C`; also the per-sample shuttle `*(*0x11F03B08) = 0x11F03AE8[i]` | C (arithmetic), I (meaning of g1-g3) |
| 11 | `0x1181B974` | out_to_int: clamp F to +-1.0, x 2^31, to `0x11F036F8` (L) / `0x11F03718` (R) | C |
| 12-13 | `0x1181AB80`, `0x1181BA80` | output stage, TX interleave | I / C |
| 14 | `0x1181BF40` -> `0xC00E14A0` | restore registers, return | C |

**Slot loop [C]:** `B14+576` (`0xC00EF988`) = slot, 0 to 5, in index order. For each slot:
`A4 = 0x11F03000 + 212 x slot` (getter `0xC00C8E6C` via the far stub `0x1181BF50`), then a call
through the audio-function table **`0xC009E930`** (6 words). Which screen position is slot 0 is
**[I]** (slot 0 runs first; the screen probably shows it rightmost, next to the input).

**Per-slot buffers.** The template writer `0xC00C8AC0` fills all six 212-byte state blocks
with the **same** pointers **[C]**. No other code builds these constants **[C, const scan]**.

| ctx word | value (every slot) | content |
|---|---|---|
| `ctx[0]` | slot index | |
| `ctx[1]` | `*(0xC009E8E8 + 4 x slot)` | params |
| `ctx[3]` | `0xC009E430 + 12 x slot` | per-slot record (ctx[3] buffer descriptor) |
| `ctx[4]` Dry | `0x11F03838` | L half = pedal input (or the louder side), written by to_float; R half `0x11F03858` = in_combine peaks [C]. The DryPrb tag lives there |
| `ctx[5]` Fx | **`0x11F03738`** | the chain signal, L `0x11F03738`, R `0x11F03758`, 8 floats each. Every effect works **in place** here |
| `ctx[6]` Acc | `0x11F03778` | zeroed before the chain, added to F after it: a **direct-to-output** path that skips the later effects (LineSel uses it) [C sum, I use] |
| `ctx[11]`, `ctx[12]` | `0x11F03B08`, `0x11F03AE8` | the "magic shuttle" |

So the answer to "one shared stereo buffer pair?" is **yes [C]**: Fx `0x11F03738` (L then R,
`LLLLLLLL RRRRRRRR`, float32), the same for all six slots. After the loop, `0x1181B090` writes the
chain result back into `0x11F03738`, and `out_to_int` reads it from there.

**Audio-function table `0xC009E930` [C]:**

| value | set by | meaning |
|---|---|---|
| `0xC00E0780` | `0xC00D7AA0` (reset of all 6), `0xC00C3F2C` | empty slot (`bnop b3`) |
| `0xC00E0784` | `0xC00D7B4C(slot)`, during effect change / patch load | **clears `0x11F03738` (hard-coded)**: mutes the chain |
| desc(slot,1)+0x20 | `0xC00D7B20(slot)` | the effect's own audio function |
| `0x1181BEC0` | `0xC00D7A80` | OS gain stage, multiplies **`0x11F03738` (hard-coded)** by params[4] | C code, I use |

Two OS functions ignore `ctx[5]` and hard-code `0x11F03738`. That is why Bus B must
**swap buffer contents, not redirect pointers**.

**Bus B: feasible [C for the mechanism, I until heard].** Proposed engine (M1), all in DDR:

1. run the Pre slots on F (`0x11F03738`), as the stock loop does;
2. copy F -> S (split point; Send gains go here);
3. run the Bus A slots on F, copy F -> A;
4. copy S -> F, run the Bus B slots on F (F is now B);
5. F = gA x A + gB x F (MIX), then run the Post slots on F;
6. call `0x1181B090` ourselves, apply the safety limiter to F, return to `0x1181BE4C`.

- Keep `B14+576` = slot and `A4` = state(slot) for every call, as the stock loop does.
- Cost: 4 copies of 64 B plus a 16-sample mix and limiter: a few hundred cycles, under 1 % of a
  block. The hidden cost is the DDR code fetch (L1P misses each block) **[I]**.
- Acc (`ctx[6]`) stays shared: whatever an effect sends there skips MIX and Post, as it skips
  the later effects in stock. Dry (`ctx[4]`) stays the pedal input for every bus.
- Buffers S and A (128 B) go in free L1D `0x11F03B80`-`0x11F03FFF`. No OS constant points above
  `0x11F03B78` **[C, const scan; I for pointer arithmetic]**.

## 2. DSP budget ("DSP Full")

| what | address | label |
|---|---|---|
| cost of an effect | float at **+0x28 of the name entry** (descriptor entry 1) of the ZDL, read via `FX_PARAM_DESC(slot, 1)` = `0xC00B056C` | C |
| check | `0xC00BB4E0(mask)`: sums the cost of every slot whose bit is set in `mask`, returns 1 if the sum is **>= 225.0** | C |
| limit constant | `mvkh 0x4361` (225.0f) at `0xC00BB52C` (`mvk 0` at `0xC00BB52A`) | C |
| fit | `0xC00BB544`: clears slot bits until the sum fits | C |
| caller | patch validate `0xC00C0848`: mask = `~tail[0] & 63`, on overflow the fit result goes back into `tail[0]` (`0xC009C060`) | C; tail[0] = "slots bypassed by DSP Full" is I |

- The budget is a **static estimate**. The OS never measures cycles. Stock costs range 11.6-127.7
  (mean 37.2, effects pack `build/linker.py`).
- Routing does not change which effects run, so the same check stays valid. The engine itself
  is not counted. To keep a margin, lower the constant: `0x435F` = 223.0, a one-halfword patch.
  How much margin is needed, the probe P1 will tell.
- The "DSP Full" text is not an OS string. It is probably a bitmap. Not located, and not needed **[I]**.

## 3. Patch storage

**RAM, current patch `0xC009BF58`, 292 B [C]** (IS_DIRTY `0xC00B8534` compares 292 B against
the last-saved copy at `0xC009C07C`).

| offset | content | bits saved | label |
|---|---|---|---|
| `+44 x s` | slot s: 11 words. w0 on/off (1), w1 effect id (28), w2-w4 params (13 each), w5-w8 params (8 each), w9 (28), w10 (8) | 136 | widths C, word meaning I |
| `+264` `0xC009C060` | DSP-off mask | 6 | C width, I meaning |
| `+268` `0xC009C064` | 0-5, clamped against `+272` | 4 | I |
| `+272` `0xC009C068` | 1-6 | 3 | I |
| `+276` `0xC009C06C` | TEMPO 40-250 | 8 | C |
| `+280` `0xC009C070` | name, 10 chars + NUL | 11 B raw | C |
| `+291` | pad | not saved | C |

**Flash record: 122 B per patch, records 0-49 [C]** (size table `0xC00EA8E0`: 122 x 50, then 24, 4).

| bytes | content |
|---|---|
| 0-107 | 6 x 18 B, one per slot: the 11 words packed LSB first, widths `0xC00EC2F8` = 1,28,13,13,13,8,8,8,8,28,8 = **136 of 144 bits** |
| 108-110 | tail, widths `0xC00ECB38` = 6,4,3,8 = **21 of 24 bits** |
| 111-121 | name (11 B copied raw) |

**Spare: 51 bits [C]:** byte 17 of each slot block (offsets 17, 35, 53, 71, 89, 107 = 48 bits)
and bits 5-7 of byte 110. The pack routine `0xC00D382C` clears its output first (memset
`0xC00DBAE0`), and the unpack routine `0xC00D3740` reads only the declared fields. So the OS
**writes zeros there and ignores them**. Old patches therefore read as all-zero, which can be
defined as "Serial, everything in Pre" (the plan's rule for old patches).

**Save and load paths [C]:**

| | address |
|---|---|
| save patch | `0xC00B84D0(patch, ram)`: pack into temp `0xC009C2A8`, then REC_SAVE `0xC00B49F4(patch, buf)` |
| pack wrapper | `0xC00B8474(dst, ram)` = slot pack `0xC00B842C` x 6 + tail pack `0xC00C0964` + name copy. Callers: save `0xC00B84E4`, SysEx dump `0xC00AE680` |
| unpack wrapper | `0xC00B8294(ram, src)` = slot unpack `0xC00B8248` + tail unpack `0xC00C0948` + name. Callers `0xC00AE2EC` (SysEx receive), `0xC00B82F0`, `0xC00B832C`, `0xC00B8964` |
| AUTO SAVE | dirty check call `0xC00ACBC4` -> IS_DIRTY `0xC00B8534` -> save |
| record store | log-structured, 24-byte headers, index `0xC009D700`, two banks (`0xC009EA80`), compaction `0xC00B4858` walks records 0-51 with the size table |
| SysEx | dump: `F0 52 00 <model> 28` + the 122 packed bytes (`0xC00AE640`); receive unpacks the same 122 bytes |

- **Do the spare bits survive?** Not without hooks: every OS save re-packs from RAM and writes
  zeros. With hooks on the pack and unpack wrappers they ride along in flash and in the SysEx
  dump. Editors keep them only if they pass the 122 bytes through as they are **[I]**.
- **Room vs need:** buses take 12 bits. That leaves 39 bits for the nodes. The full node
  set in the brief is about 63 bits (Send, Crossfade, Master and four bus levels at 7 bits each,
  plus Curve, Mode, Output Mode and Phase). It does not fit. Options for M2:
  (a) keep one pair of bus levels (on `[MIX]` only) and store the levels with 6 bits: about 37 bits, fits;
  (b) a new record 52 (size table entry 52 is 0 today). This needs changes to the record count in
  the compaction and the boot scan, which is a flash-format risk;
  (c) never grow record 0-49: the size table also drives the compaction, so a bigger patch
  record would misread every stored patch.
- MIDISTOMP already uses spare bits the same way: the MIDI word sits in record 51, bits 8-31.

## 4. No-go check

Nothing blocks. Risks, ranked:

1. **CPU headroom unknown.** The 225 budget is an estimate. A patch near DSP Full may already be
   close to 100 %. Measure it (P1) before M1 ships.
2. **L2 is full.** The engine goes in DDR (`0xC00F3100`+, region 1, confirmed free on the 70CDR
   by the RAM test). The hook leaves about 40 B of L2 dead (`0x1181BE20`-`0x1181BE4B`).
3. **Effects that read Dry (`ctx[4]`)** get the pedal input, not their bus input. A quick scan
   finds `*+a4(16)` loads in 16 of 137 stock ZDLs (gates, reverbs, LineSel, ...). The scan is
   noisy (A4 aliases), so check by ear in M1 **[I]**.
4. **Acc (`ctx[6]`) bypasses MIX/Post.** That matches stock behaviour, but a LineSel or a
   tail sent there is not crossfaded **[I]**.
5. **Patch room** (section 3): reduced node set or a new record.

## Proposed hook points for M1

| site | change | why |
|---|---|---|
| `0x1181BE00` (one 32-byte fetch packet, header at `0x1181BE1C`) | 8 plain words: `mvkl/mvkh engine,b31 ; b b31 ; nop 5 ; nop x4` | replaces the slot loop. The previous packet's `callp 0x1181B340` returns here [C] |
| DDR `0xC00F3100` | `mixer.S`: steps 1-6 above, fixed test layout as `.equ`, return to `0x1181BE4C` | no L2 needed |
| L1D `0x11F03B80` | S, A buffers (128 B) + limiter state | fast, free |
| `0xC00BB52A`/`0xC00BB52C` (optional) | 225.0 -> 223.0 | engine margin, size after P1 |

M2 adds: callers of the pack wrapper (`0xC00B84E4`, `0xC00AE680`) and the unpack wrapper (the 4
call sites above) retargeted to DDR wrappers that also handle the spare bits, and IS_DIRTY
`0xC00B8534` wrapped so that a routing change also triggers AUTO SAVE.

## Open questions: hardware probes

- **P1 CPU meter (debug build, no audio change).** At `0x1181BE00` jump to a DDR stub that
  reads TSCL, runs the stock loop, reads TSCL again and keeps the maximum (and the time from
  block start). Show it on the version screen, as the RAM test does. Run it with an empty
  patch, then with 6 heavy effects just under DSP Full. Answer: cycles per cost unit, and the
  real headroom for the engine.
- **P2 slot order.** In the same build, show `0xC009E930[0..5]` next to the screen order, or
  have a probe ZDL beep `ctx[0] + 1` times. Answer: which screen position is slot 0.
- **P3 Acc and Dry.** A probe ZDL like DryPrb: role SEND adds a tone to `ctx[6]` and role READ
  in a later slot looks for it in `ctx[5]`. Expected: heard at the output, not seen in later
  slots. Then a stock gate / reverb on Bus B after a drive in Pre, to hear whether it mixes in
  the dry pedal input.
- **P4 editor round trip.** Read a patch with SysEx (`zoomms`), set the 6 spare bytes, write it
  back through each editor Luca uses, read it again. Answer: whether editors keep the bits
  (the pedal itself needs the M2 hooks either way).
