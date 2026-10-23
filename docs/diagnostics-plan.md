# SYSTEM screen (diagnostics; replaces the m0 probe in test builds)

A CPU and DSP meter and a small dashboard. MENU shows `DSP 135/300` (the declared DSP of the patch, limit 300) at the top left of the title
bar and `CPU 47%` at the top right (left of the battery icon when on battery).
MENU > SYSTEM (the old VERSION entry) has 4 pages of 2 or 3 columns; 4 rows fit, knob 1 scrolls
(scrollbar at the right), a knob 3 click goes to the next page (4 back to 1), knob 2 (EXIT)
leaves. Softkeys: blank with the stock list arrows over knob 1 / EXIT / PAGE.

| Page | Rows |
|------|------|
| VERSION | version, commit, date, label (build stamps), uptime |
| LOAD | CPU, CPU PEAK (since the screen opened), AUDIO (the chain) and AUDIO MAX, FREE (headroom), LATE blocks (this window), LATE TOTAL (since boot), declared DSP total of the patch vs 300 |
| EFFECTS | per slot: name, average CPU % of a block, declared DSP |
| MODS | sorted from most to least CPU: EFFECT CHAIN (the mixer), PERFORM MODE, LOOPER BUFFER (the GRDLOOP slot; "-" and last without one), MIDI (Task_MIDI), DIAGNOSTICS itself, EFFECTS (the other slots), OS |

## How it measures
- CPU 300 MHz, one audio block (8 frames) = 54,422 cycles. TSCL stops while the OS idles,
  so TSCL between two block starts counts busy cycles only: average period / 54,422 = the
  whole CPU load (audio, UI, everything). A period above 60,000 is a late block (the CPU
  was saturated); a patch change makes one or two.
- `asm/mixer/engine.c` reads TSCL around perf_block and each slot's effect, and at the end
  calls `diag_end` (asm/diag, at 0xC00F3100) if its magic word is there. diag_end sums 4096
  blocks (0.74 s) and publishes the averages. Cost: about 100 cycles per block (0.2 %).
- MIDI: two callps in Task_MIDI (`diag.yaml`) time each received byte from the task's wake-up
  (0xC00AECCC) or the previous byte's end to the end of its byte loop (0xC00AEEE0, after the
  MIDI clock code), minus the audio blocks that interrupted it. The stock interrupt entry and
  exit still count as MIDI.
- EFFECT CHAIN = chain − PERFORM − slots. OS = CPU − chain − DIAGNOSTICS − MIDI: the stock audio
  driver around the chain (interrupt entry, DMA and codec copies), the 16 ms control tasks
  and the screen drawing. The m0 probe measured 22 % busy on an empty patch, so OS is about
  17-22 % on every patch and is the largest share on a light one.

## Build
- `patches/diag.yaml` reuses the probe's hooks (16 ms poll, screen 9 draw and keys), takes the
  menu draw callp at 0xC00A9398, points the menu name at "SYSTEM" (mixer.S MENU7) and
  keeps the probe's DSP limit 300.
- The screen 9 key stub passes event in A4 and steps in A5; `diag_kv` (diag_vec.asm) moves
  steps to B4 for the C (knob turns and the knob 3 click, 67) and sends other events to the
  stock version keys.
- C section 0xC00F3100-0xC00F5400 (where the probe was), built by `scripts/build_diag_ui.py`.
- Test builds use `diag.yaml` instead of `m0-probe.yaml`; the probe files stay in the repo.
