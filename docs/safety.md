# Safety rules

1. **Know the recovery path before writing anything.** The official updater
   mode (hold Up and Down while plugging in USB) is the only known recovery.
   Before any firmware experiment, confirm it works on that pedal with the
   stock updater.
2. **Back up first.** Patches and the effect list, per pedal, into `firmware/`.
3. **Effects before firmware.** Custom ZDLs load like stock effects. The worst
   reported outcome is a freeze until power-cycle (see ZoomMultistompZDL's
   `docs/LOADER-SAFETY.md`).
4. **No modified image is flashed unless** `zoomms updater-verify` is exact on
   the stock updater it came from, and `updater-info` reports no problems on
   the modified one.
5. **One pedal at a time.** Test on the pedal you are most willing to lose.
6. **Never commit Zoom files.** Updaters, stock ZDLs and dumps stay in `firmware/`.
