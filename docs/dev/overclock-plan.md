# CPU overclock for MIDISTOMP: plan

Status (2026-11-12): the 360F build option exists and builds, but it has **not been tested on hardware**.
The tester app is not built yet. Goal: "just a boost", that is more DSP time per audio block, with low risk.

## What we know

- The chip is a TMS320C6745 (DA830 family, 300 MHz speed grade). The SDRAM is rated 143 MHz.
- The clock is set in MAIN's AIS boot script, not in OS code. The prologue is the same on stock
  MS-50G 3.10 and MS-70CDR 2.10:

  | Command | Stock arguments | Meaning |
  |---|---|---|
  | `function 5` | `18010202 000501B9 2` | PLL0: 24 MHz x 25 / 2 = 300 MHz |
  | `set 0x01C14188` | `5` | CFGCHIP3: where the EMIFB (SDRAM) clock comes from |
  | `function 2` | `1C620 10913208 30080006 81F` | SDRAM: SDCR, SDTIM1, SDTIM2, refresh count |

- Aleksander Lim's research (2026-11-12, private, not in the repo) showed that the bootloader applies
  these MAIN words.
  - Builds at 360, 360F, 408 and 408F MHz booted.
  - One pedal was stable at 504 MHz and hung at 528. Another pedal's limit was 408.
  - The FFT effect POLYSHFT hung at 480.
- His speed table: CPU = 24 x (PLLM + 1) / (POSTDIV + 1). The "F" modes take the SDRAM clock from
  SYSCLK5 (CFGCHIP3 = 0). The refresh count is SDRAM MHz x 15.6 - 1.
- **Recovery is safe.** The bootloader has its own AIS script, which keeps 300 MHz (checked: its
  `function 5` is untouched in our build). Update mode (Up + Down while plugging in USB) runs before
  MAIN, so a pedal that hangs can still be reflashed.
- **Audio rate does not change.** The McASP is a clock slave. USB is not affected either.
- **SPI0 clock scales with the CPU** (it runs from SYSCLK2). Patch saves to flash still need checking.
- Timers are believed to run from the 24 MHz oscillator. Tap tempo and MIDI clock still need checking.
- MIDISTOMP v2.0 is always built from the MS-70CDR 2.10 OS, so one set of words covers every pedal.

## What is built

- **`boot:` patch kind** (`zoomms/patcher.py`): it changes the arguments of one AIS command
  (`function N` or `set <register>`). It checks the stock arguments and requires exactly one match.
- **`patches/cpu-360f.yaml`** sets:
  - CPU 360 MHz
  - SDRAM 120 MHz, from SYSCLK5
  - refresh count 0x74F
  - DSP Full limit 300 -> 340. This is the 360/300 ratio with about 5% kept spare, and it is not yet
    confirmed by Luca. It is written after `dsp-limit`.
- **`midistomp_builder.build(..., cpu="360f")`** adds that patch. Without it the build stays at stock 300 MHz,
  and the release is unchanged.
- **Checked with the stock 2.10 updater:** only MAIN's four words and the DSP limit word change.

## Next steps

1. **Hardware test of 360F** on the MS-70CDR and MS-60B. Do it after the other sessions' changes land,
   on the latest main. Check:
   1. The pedal boots, and the CPU meter shows lower load.
   2. Tuner pitch, delay times, tap tempo, and MIDI clock in and out are unchanged.
   3. USB patch save, an Effect Manager ZDL install and the 2nd SPI flash work.
   4. The heaviest chain runs for 1 hour.
2. **One-click tester app** (Luca's design: one app and one builder for all models, with no model detection):
   1. Flash a test-only MIDISTOMP build: stock OS, a runtime speed switch and a stress kernel, with no
      features, so L2 is free.
   2. Step up in 24 MHz steps, with short runs per speed, until the first hang. This takes about 15 min.
   3. Choose the safe speed: **3 steps below the first hang**, capped at about 456 MHz.
   4. Flash the full MIDISTOMP built at that speed. Flashing uses the direct protocol
      (`scripts/zoom_flash.py`, docs/dev/flash-protocol.md).
   - Still unknown: whether the watchdog can reset a hung chip (or whether the user replugs it), and how
     the result is read back over USB.
3. For speeds other than 360F, generate the boot words from the formula instead of adding one yaml per speed.

## Open questions

- Function 5's third argument is 0x2 in MAIN and 0x4 in the bootloader. Its meaning is unknown.
- How much do heat and a weak USB power supply lower the safe speed?
- Which value the DSP Full limit should have at each speed (340 at 360F for now).
