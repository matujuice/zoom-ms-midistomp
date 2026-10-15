# MS-70CDR: run the MS-50G OS with stereo in (A) or port to the 70CDR OS (B)?

Status 2026-10-15. This is static analysis only: no 70CDR was on hand and nothing was flashed.
Inputs: the stock MS-70CDR 2.10 updater and the MS-50G 3.10 pseudo-stock updater
(OS identical to stock), both unpacked with `zoomms updater-parts` and `zoomms ais` and
disassembled with `tic6x-elf-objdump`. Working files are in `/tmp/claude-0/cdr` (not committed).
Labels: **[C]** = confirmed from the disassembly, **[I]** = inferred.

## 1. How different the two OS images are

| | MS-50G 3.10 | MS-70CDR 2.10 |
|---|---|---|
| Loaded bytes / sections | 354 780 / 11 | 353 504 / 11 |
| Entry `_c_int00` | `0xC00DDCC0` | `0xC00DD800` |
| DP (B14) | `0xC00EFCC0` | `0xC00EF748` |
| Main DDR code | `0xC009DFC0` +`0x44680` | `0xC009DFC0` +`0x441E0` |
| L2 audio code | `0x1181AB80` +`0x1380` | `0x1181AB80` +`0x1400` |
| Bootloader (BIN/136) | identical (sha256 `32ba932c...`) | identical |
| BIN/133 | boot logo bitmap (`MS-50G`) | boot logo bitmap (`MS-70CDR`) |
| USB device descriptor | VID `0x1686` PID `0x01A1` | the same bytes |

- The memory map and the peripheral constants are the same. Every `mvkl/mvkh` peripheral
  address is the same in both OSes except one: the 70CDR also builds `0x01D02000`
  (the McASP0 DMA data port) **[C]**.
- Strings are about 99.9% the same. Only the MS-50G has `DLY/REV`, `MOD/SFX`, `OD/ DIST`,
  `Now Writing...`, `Please Restart` and `Complete!`. The task names are the same.
- Functions: 1271 of 1401 MS-50G `callp` targets (91%) begin with the same 10 instructions
  in the 70CDR OS, after masking addresses and large immediates. Most of the code is the same,
  but nearly every address has shifted (from -0x5A0 to +0x720 in DDR).
- L2 core `0x11817000`-`0x1181AB80`: matches at 0.94. The L2 audio section from `0x1181AB80`
  matches at only 0.54: the audio front end is model-specific (section 2).
- Patch sites, counting the release set plus looper (70 `write:` entries):
  - **47/70** can be found uniquely by their normalized code context.
  - The other 23 are of three kinds: SysEx handler-table words (`0xC00EF2xx`, midi-settings),
    zero-padding caves (new caves are needed), and call sites inside functions that changed.
  - Every `section:` blob also hard-codes OS addresses. `asm/` references **161** distinct
    `0xC0xxxxxx` addresses, plus B14 offsets. Those offsets shift as well: the model byte is
    at B14+220 on the 50G and B14+212 on the 70CDR.
  - Option B therefore means redoing every patch by hand, with the same amount of
    verification work as the original MS-50G work.

## 2. Audio I/O: why the MS-50G OS gives mono on a 70CDR

No I2C or SPI codec traffic appears in either OS: no I2C0/I2C1/SPI0 base is built or stored.
The codecs are most likely configured by hardware pins **[I]**. All the differences are in the
McASP setup, the EDMA setup and the L2 input stage.

**McASP init.** MS-50G `0xC00C31D8`, 70CDR `0xC00C3038`. The McASP base pointer is at
`0x1181DE0C` (50G) and `0x1181DE8C` (70CDR).

| reg (offset) | MS-50G | MS-70CDR |
|---|---|---|
| PFUNC (0x10) | `0x0300FF9F`: AXR4 is a GPIO | `0x0200FF8F`: AXR4 is McASP |
| PDIR (0x14) | `0x1600FFDF`: **AXR4 is an output** | `0x1600FFCF`: AXR4 is an input |
| RFMT (0x68) | `0x000180F8` (RBUSEL = 1, config bus) | `0x000180F0` (RBUSEL = 0, DMA port) |
| SRCTL4 (0x190) | not written | `0x0E` (receive) |
| SRCTL5 / SRCTL6 | RX / TX | RX / TX (the same) |
| AFSRCTL, RTDM, XFMT, TX side | the same: I2S, 2 slots | the same |

**[C]** The 70CDR receives on two serializers, AXR4 and AXR5. The MS-50G only on AXR5.
The MS-50G OS on a 70CDR also drives the AXR4 pin as a GPIO output. That pin is probably the
second ADC's data line. This is a pin conflict that exists now on the user's pedal **[I]**.

**EDMA.** MS-50G `0xC00C5960`, 70CDR `0xC00C8F00`. PaRAM builder `0xC00C5900` / `0xC00C8EA0`.

- MS-50G RX: channel 0 plus links 66/67. Source RBUF5 (`base+0x294`), ACNT 4, BCNT 16, into
  2 x 0x40 buffers at `0x11F034F8` and `0x11F03538`.
- 70CDR RX: source `0x01D02000`, ACNT **8**, BCNT 16, DSTBIDX 8, into 2 x **0x80** buffers
  at `0x11F034F8` and `0x11F03578`.
- TX is the same on both: XBUF6, 2 slots. The 70CDR TX buffers are moved up to `0x11F035F8`
  and `0x11F03638`.

**L2 audio block.** MS-50G call list `0x1181BD60`, 70CDR `0x1181BDE0`. Both run the same
sequence:

`rx_deint` -> `in_combine` -> `to_float` -> chain -> ... -> `out_to_int` -> `tx_interleave`

| stage | MS-50G | MS-70CDR |
|---|---|---|
| rx_deint | `0x1181BBEC`: 2 words per frame, AXR5 slots 0/1 -> arrays `0x11F035F8` / `0x11F03618` | `0x1181BB0C`: 4 words per frame -> 4 arrays `0x11F03678`, `...698`, `...6B8`, `...6D8` |
| in_combine | `0x1181B8E0`: one stateful pass, uses both ADC slots, coeffs `0x11F03A04`; result into the slot-0 array **[I]** | `0x1181B680`: the same idea, run twice (stride 64 bytes, one per ADC pair), coeffs `0x11F03AA4` -> `0x11F036F8` (L), `0x11F03718` (R) |
| to_float | `0x1181B760`: one array -> **the same value stored to L `0x11F03638`, R `0x11F03658`** and `0x11F03758` | `0x1181B8C0`: L and R converted separately -> `0x11F03738` / `0x11F03758`; `if (B14+572 == 0) R = L` |
| TX side | `0x1181BB60`, L/R arrays `0x11F036B8` / `0x11F036D8` | `0x1181BA80`, `0x11F037B8` / `0x11F037D8`; same code |

- **[C]** The mono comes from the input stage. The MS-50G OS reads one ADC pair, AXR5
  (inferred to be the input L/mono jack). It makes one mono signal and copies it into both
  chain inputs.
- The chain and the outputs are stereo in both OSes. So the user hears stereo only where an
  effect creates it. Many MS-50G ZDLs (drives, amps) are probably mono internally **[I]**.
- The interpretation of the stages is **[I]**: each input jack seems to use both channels of
  one stereo ADC (dual-range combine, with `abs`/compare). The 70CDR has one such ADC per
  input: AXR5 for L, AXR4 for R.
- **R-jack logic, 70CDR only [C].** A poll loop near `0xC00C6A50` reads GPIO 90 (`0xC00CD568`).
  - After 15 equal reads it sets B14+572 = 1 (stereo) and writes GPIO 63 = 1
    (`0xC00CD404` -> `0xC00E20E0`). Otherwise it sets mono (R = L) and GPIO 63 = 0.
  - The MS-50G OS has the GPIO 90 read helper (`0xC00CE0A0`) but nothing calls it.
  - GPIO 90 is probably R-jack detect, and GPIO 63 an analog switch **[I]**.
- The MS-60B OS is like the 50G: there is no `0x01D02000` reference.

**Minimal option-A patch (MS-50G OS, stereo in, stereo out). Not built, not tested.**

1. McASP init: PFUNC `0x0200FF8F`, PDIR `0x1600FFCF`, RFMT `0x000180F0`, and add SRCTL4 = `0x0E`.
   These are immediate edits plus one extra store near `0xC00C31A8`-`0xC00C32A0`.
2. RX EDMA, the 3 PaRAM calls in `0xC00C59F0`-`0xC00C5A88`:
   - source `0x01D02000`, ACNT 8, SRCBIDX 0, DSTBIDX 8.
   - Point the destinations at two new 0x80 buffers. The current 0x40 buffers sit right below
     the TX buffers.
   - Also update the ping-pong compares, which use PaRAM0 DST `0x01C0400C` against buffer B,
     in `rx_deint`.
3. Replace `rx_deint`, `in_combine` and `to_float`:
   - Add the 70CDR versions (about 1 KB in total), relocated, with new L1D or L2 addresses.
   - Or split AXR4 out and call the MS-50G `in_combine` a second time with its own state block.
   - Either way, `to_float` must write R from the R pair.
   - The chain inputs stay at `0x11F03638` / `0x11F03658`, so nothing downstream changes.
4. Recommended: port the GPIO 90/63 jack poll so that mono input still feeds both sides.
   Without it, a mono cable would probably give a dry R side that is silent.
5. Memory, the main risk: 0x180 bytes of new buffers plus state are needed.
   - L1D use ends at about `0x11F03B10` (50G) / `0x11F03B80` (70CDR). The space above that is
     probably free up to the SRAM/cache split, but the L1DCFG value has not been checked **[I]**.
   - L2 free space is mostly used by MIDISTOMP already. DDR buffers would need cache
     maintenance.
   - The 70CDR coefficient values for `in_combine` (`0x11F03AA4`) may differ from the
     MS-50G ones (`0x11F03A04`). The code that sets them has not been compared yet.

## 3. Model ID and other model-specific behaviour

- **SysEx model id [C].** Task_MIDI compares byte 3 against B14+220 (50G; B14+212 on the
  70CDR). The same byte goes into the identity reply (`0xC00AD884`, template `0xC00ED060`).
  - At boot, `0xC00E0D40` reads a 0x2C01-byte flash block into `0xC00029D8` and takes byte
    `0xC00055D8`, unless that byte is 0xFF. The `.cinit` default is 0xFF.
  - So the model id comes from per-unit flash data, not from the OS **[I: which flash area]**.
  - A 70CDR running the MS-50G OS may therefore still answer 0x61. Check with
    `zoomms identify` on the user's pedal.
  - No `0x58` or `0x61` constant appears in either OS. No MIDISTOMP asm hard-codes 0x58.
- No other hardware-ID or GPIO-strap model check was found. The only model branch seen is the
  70CDR-only jack logic, and it is compiled in, not selected at runtime.
- Same in both: 50 patches, 6 effect slots, the USB descriptors, and the settings strings
  (tuner, battery, LINE/COMBO/...).
- What bites option A beyond audio:
  - The file system (BIN/137) is the MS-50G set: 101 guitar effects plus CMN_DRV. The 70CDR's
    own effects (137 stock ZDLs) are not installed.
  - The boot logo says MS-50G, unless the boot-logo patch replaces it.
  - The FX category names are the guitar ones.
  - Zoom software identification depends on the flash model byte (see above).

## Recommendation

**A: keep the MS-50G OS and add a stereo-input patch. Confidence medium (about 65%).**

- The difference is limited to the McASP/EDMA init and three L2 leaf functions. The 70CDR OS
  gives working reference code for each of them.
- B means re-locating 70 write sites and 161 OS addresses. Every future MIDISTOMP release
  would then need a second build to maintain and test.
- Both options need a 70CDR owner to test. A also fixes the AXR4 pin conflict.
- Change the recommendation to B if:
  - the free-memory check fails, or
  - 70CDR owners want the stock 70CDR effect set, or
  - the A patch shows analog differences that cannot be fixed in software (gain or
    calibration).

## Model detection (one image for MS-50G/60B and MS-70CDR)

Static analysis, 2026-10-15. Addresses are MS-50G 3.10 unless marked (70CDR 2.10, 60B 2.10).

**Flash map** (both updaters' step tables): boot `0x000000` +0x40000, OS `0x040000` +0xB0000,
FS (BIN/137) `0x0F0000` +0x2C7000, BIN/133 `0x3FD000` +0x3000. The MS-50G updater erases and
writes boot, BIN/133 and OS; the 70CDR updater also writes the FS **[C]**. So a 70CDR flashed
with any MS-50G-based updater keeps its factory 70CDR file system (this corrects section 3).

**1. SysEx model byte = BIN/133 offset 0x2C00 (flash `0x3FFC00`) [C].**
- `0xC00BB960` picks the flash layout from the JEDEC id (`0xC00BB908`: F8 32 15 = 2 MB part,
  base `0x1D0000`; otherwise base `0x3FD000`, stored at B14+20). `0xC00E0D40` reads 0x2C01
  bytes from that base (SPI fast-read `0xC00BB574`) and takes the last one. Same code in the 70CDR.
- Stock BIN/133 byte 0x2C00: 0x58 in the MS-50G updater, 0x61 in the 70CDR updater (60B: 0x5F per
  `models/`). The rest of the 4 KB sector is 0xFF.
- Every MIDISTOMP build includes `boot-logo` (`scripts/midistomp_builder.py` PATCHES), so it keeps
  the BIN/133 erase+write with **MS-50G** data: every MIDISTOMP pedal, 60B and 70CDR, now has 0x58
  there **[I, follows from the flash steps]**. The stock MS-50G updater does the same.
- Verdict: correct from the factory, but already lost on every installed pedal. It is usable only if
  MIDISTOMP stops writing BIN/133 (logo drawn by the OS instead) and 70CDR users run the stock 70CDR
  updater once. One wrong flash loses it again. Secondary signal at best: 0x61 means 70CDR, 0x58 means unknown.

**2. GPIO straps: none found.** GPIO init (writes OUT, then DIR, per bank; DIR bit 1 = input):
MS-50G `0xC00CE234`, 60B `0xC00BE654` (byte for byte the same values), 70CDR `0xC00CD5B8`. Differences:

| GPIO | MS-50G / 60B | MS-70CDR | use in the 70CDR OS |
|---|---|---|---|
| 39 (GP2[7]) | output, low | output, **high** | flash read `0xC00B8E64`: addr >= 0x400000 -> GPIO39=0, addr -= 0x400000 (upper flash bank select) |
| 52 (GP3[4]) | output, low | **input** | no direct reader found |
| 90 (GP5[10]) | output, low | **input** | R-jack poll (section 2): depends on the cable, not a model id |

- GPIO 63 is an output, low, in all three. No OS reads a pin at boot to choose a model. The MS-50G
  OS has the GPIO 90 read helper `0xC00CE0A0`, but nothing calls it.
- The bootloader (BIN/136) is identical on all three (also the MS-60B `boot.elf`). It builds no GPIO
  or SYSCFG address and never reads `0x3FFC00`. Its USB name is the generic "ZOOM MS Series".
  It cannot tell the models apart **[C for what was searched]**.
- Today the MS-50G OS on a 70CDR drives GPIO 52, GPIO 90 and AXR4 low against whatever drives them
  on that board **[I: possible contention, already happening on the user's pedal]**.

**3. AXR4 activity probe (recommended) [design I, facts C].**
- MS-50G and 60B McASP init (`0xC00C32A0`; 60B `0xC00B3740`): PFUNC `0x0300FF9F`, PDIR `0x1600FFDF`.
  AXR0-4 and AXR7-15 are all GPIO outputs, and no PDOUT/PDSET/PDCLR write was found, so all of them
  are driven low. This is the usual way to park unused pins. Nothing in software uses AXR4 as a
  control line **[C]**; its board connection is **[I]**.
- On the 70CDR, AXR4 is the data out of the second (R) ADC. It is clocked by the same McASP
  frame/bit clocks as AXR5. An I2S ADC sends sign and noise bits all the time, so the pin keeps
  toggling even with no cable in.
- Probe: after the McASP clocks run, set PDIR bit 4 = 0 (input) and keep PFUNC GPIO. Sample PDIN
  (McASP +0x1C) bit 4 a few thousand times over about 10 ms and count transitions. If there are
  transitions: 70CDR, so apply the stereo config (section 2) and then GPIO 39/52/90/63 like the
  70CDR OS. If there are none: restore PDIR `0x1600FFDF`. The 60B/50G then end up exactly as today.
- Safety: an input cannot drive anything. The worst case on a 50G/60B is a few ms with the pin floating.
- A false negative (ADC held silent) gives today's mono, which is safe. A false positive needs a
  floating pin that toggles. Mitigation: require many transitions **[I: OMAP-L138 AXR pull
  default not checked]**.
- Never switch GPIO 39/52/63/90 on a pedal that failed the probe: their 50G/60B roles are unknown.

**4. Weak heuristics:** the FS content (70CDR stock ZDLs survive the cross-flash, but users and Zoom
Effect Manager change it) and the flash JEDEC id (production variation, the same check in both OSes).

**Ranking:** (1) AXR4 probe: hardware-based, independent of flash history and cables, safe.
(2) Flash byte `0x3FFC00`: only after the updater change, as confirmation.
(3) GPIO 90: no, it depends on the cable. GPIO straps or the bootloader: nothing found.

**Harmless on-pedal tests.**
- `zoomms identify` on the owner's 60B and on the 70CDR: expect 0x58 on both. This would confirm
  that the model byte was overwritten.
- A debug build that only runs the probe (input, sample, restore) and prints the transition count
  and the ones count next to the version on the boot screen.
  - Owner's MS-60B first: expect 0 transitions.
  - Then a 70CDR owner, with no cable, then L only, then L+R: expect many in every case.
  - No other pin and no audio path changes in that build.

## Why AXR4 is silent

Static analysis, 2026-10-15, after probes p1/p2 (`asm/cdr_probe/probe.S`) read zero AXR4 activity on a
70CDR running the MS-50G OS. Addresses are MS-50G 3.10 unless marked 70CDR.

**The chip is DA830-family (C6745/C6747), not OMAP-L138, for pin muxing [C].** The GPIO helpers
reject n >= 128 (`0x1181A068`, 8 banks); PINMUX0 = `0x11112101` selects the EMIFB/mDDR pins and PINMUX9
the McASP0 clocks only under the DA830 table (Linux `mach-davinci/da830.c`). Earlier sections used
OMAP-L138 pin names: ignore those.

**PINMUX is set by the OS, not the AIS [C].** The AIS of BIN/136 and BIN/129 only writes CFGCHIP3.
The SYSCFG pointer `0x1181D854` (70CDR `0x1181D8D4`, cinit) unlocks KICK0/1 at `0x11817310`. The L2 code
`0x11817400`-`0x11818F50` then writes PINMUX0-19 field by field. That code is identical in both OSes
except one instruction at `0x11818274`: `set b0,23,23` (50G) vs `set b0,20,20` (70CDR).

| PINMUX10[23:20] | value | pad AXR0_4 is routed to |
|---|---|---|
| MS-50G/60B OS | 8 | **GPIO3_4 = GPIO 52** |
| MS-70CDR OS | 1 | **McASP0 AXR4** |

**Cause 1 (confirmed from code, the board side is inferred): the MS-50G OS takes the AXR4 pad away from the McASP.**
- On DA830 parts the pad belongs to one module only. With PINMUX = GPIO, McASP PDIN bit 4 never sees
  the pad, whatever PFUNC/PDIR/SRCTL4 say. That explains p1/p2 exactly: 20000 samples, 0 highs,
  0 transitions **[I: TRM mux behaviour, not checked against the TRM text]**.
- GPIO 52 *is* that pad. The 50G GPIO init (`0xC00CE234`: DIR3 = `0x1020`, OUT3 = 0) drives it
  low, against the second ADC's data output, for as long as the pedal is on **[I: possible stress on
  the ADC output]**. The 70CDR OS leaves GPIO 52 as an input (DIR3 = `0x1030`), which is a second guard.
- p2 read GPIO 52 IN only once. A single 0 says nothing about activity.
- The probe mapping is right: IN = base+0x20+0x28*(n>>5), bit n&31 (`0x1181A068`, base pointer
  `0x1181DE70` = `0x01E26000` from cinit). GPIO 52 = IN23 bit 20, GPIO 90 = IN45 bit 26.

**Other differences, ranked lower:**
2. **GPIO 39 = GP2[7], pad NEMA_OE (PINMUX18[23:20] = 8, a GPIO on both) [C].** In the 70CDR the flash
   read/write/erase (`0xC00B8E64`, `0xC00B8D0C`, `0xC00B9424`) do this for addr >= 0x400000: SPI0 SCS0 is
   switched to GPIO 84 held high (PINMUX7[31:28] = 8, `0x1181A4D8`), then GPIO 39 goes low. So
   GPIO 39 is the **chip select of a second SPI flash** (bank at 4 MB) **[I, strong]**, not ADC power.
   The MS-50G OS holds it low, which keeps that chip selected all the time. Every MS-50G flash command
   then also reaches chip 1. Writes cannot run there (WEL needs a full CS cycle), but chip 1 could
   drive SOMI during reads. The pedal works, so chip 1 is probably not fitted or stays quiet **[I]**.
   It is unlikely to matter for audio.
3. **GPIO 90 = GP5[10], pad AXR1_10, a GPIO [C].** 70CDR poll `0xC00C6AB4`: GPIO 90 = 0 for 15 polls
   means GPIO 63 = 1 and stereo; 1 means GPIO 63 = 0 and mono. p2 read 0 with every cable, and with
   the 70CDR logic that would mean "stereo" all the time. The detect line may need a pull-up that
   is not powered **[I]**.
4. **GPIO 63 = GP3[15], pad ACLKX1 (PINMUX11[27:24] = 8) [C].** It is driven only at run time by the
   jack poll. It is probably the L-to-R analog switch, not the ADC enable **[I]**.
- The same in both [C]: AIS, bootloader, PSC enables (`0x1181736C`), EMIF/PLL and all other PINMUX fields.
  The McASP clocks are the same too: PDIR bits 29-31 = 0, so ACLKR/AHCLKR/AFSR are inputs (the
  McASP is a receive slave) and the second ADC uses the same clocks as AXR5. PFUNC/PDIR bit 24 is
  reserved on McASP **[I]**, so `0x0300FF9F` vs `0x0200FF8F` only changes AXR4 there.

**Next experiment (debug build, MS-70CDR only):**
- p3: after GPIO 52 -> input (as in p2), sample **GPIO IN23 bit 20** 20000 times and count the
  transitions and highs. It needs no PINMUX change and drives nothing.
- Expected: many transitions, which confirms cause 1. Then p3b: write the KICK keys
  (`0x83E70B13`, `0x95A4F1E0` to `0x01C14038`/`3C`), set PINMUX10[23:20] = 1 and sample McASP PDIN
  bit 4 (PDIR bit 4 = 0). This should match. After that the option-A patch can go ahead with
  PINMUX10 = `0x11188880` and GPIO 52 as an input.
- Zero again: the ADC is held off or damaged. Then try GPIO 39 high (use SET_DATA23 bit 7, `+0x40`,
  which is atomic), then GPIO 63 high, re-sampling after each.
  - Risk: GPIO 39 high only deselects the suspected chip 1, the 70CDR default state.
  - Do it outside a flash access: hold the poll task off while `0xC00B8E64` runs, or just accept a
    possible bad read in a debug build.
  - Never on a 50G/60B: there the pad's role is unknown.
- Fix in any case: the stereo patch must set PINMUX10[23:20] = 1 and GPIO 52 as input before
  McASP SRCTL4 is enabled. Otherwise the GPIO keeps driving the ADC data line.

## Stereo input patch: groundwork (static, 2026-10-15)

- Caches: L2 128 KB cache, L1D 16 KB cache (L1D SRAM ends 0x11F04000), L1P 32 KB cache. DDR 0xC0xxxxxx cacheable; shared RAM 0x80000000 not.
- Free L1D: 50G OS inits L1D up to 0x11F03B18 (70CDR 0x11F03B7C). Nothing references 0x11F03B18-0x11F04000 or 0x11F02370-0x11F03000 (no mvk/mvkh, data, cinit, nor literal in stock/pack ZDLs). Room for 2 x 0x80 RX buffers, deinterleave arrays, combine state.
- Free L2: only 0x1181DE84-DEA0 (28 B), 0x1181E6E0-E700 (32 B), 0x1181E9C0-EA00 (64 B). New input-stage code goes in DDR 0xC00F2800-0xC00F3000.
- McASP init diffs only: RFMT 0x180F0 (XFMT stays 0x180F8; the OS reuses the RFMT register value for XFMT, keep XFMT), PFUNC 0x0200FF8F, PDIR 0x1600FFCF, SRCTL4 = 0x0E. RMASK/RTDM/start sequence same.
- Boot order at 0xC00D47F0: audio init 0xC00E0C00, EDMA init 0xC00C5A8C, McASP init 0xC00C31A4. EDMA events are enabled inside McASP init, so retargeting the callp at 0xC00D47F8 gives one clean place for a boot init routine.
- 70CDR RX EDMA: source 0x01D02000, ACNT 8, DSTBIDX 8, BCNT 16, PaRAM 0/66/67, via the builder 0xC00C5900.
- Input filter coefficients: 70CDR in_combine uses 9 coefficients, 50G uses 12 (same 9 + 3 more). Calling the 50G in_combine twice is NOT equivalent to the 70CDR; port the 70CDR stage.
