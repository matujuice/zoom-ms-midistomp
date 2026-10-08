# Building and flashing a modified OS

## What our updaters do differently from Zoom's

The stock updater runs a fixed script (see `zoomms/flash.py`):

1. erase the last 4 KiB of the OS area (its trailer)
2. erase and rewrite the **bootloader**
3. erase and rewrite a 12 KiB block at 0x3FD000
4. (MS-60B, MS-70CDR only) erase and rewrite the effects file system
5. erase and write the main OS

Updaters built by `zoomms build` skip steps 2 and 3. The bootloader holds the
USB update mode, so never touching it keeps that recovery path intact even if
an update is interrupted. Built from the MS-50G updater, the effects file
system (step 4) is not touched either, so your installed effects stay.

They are also unsigned: Zoom's signature is removed because it no longer
matches. Windows SmartScreen will warn; choose "More info" then "Run anyway".

## Build

```sh
zoomms build "firmware/MS-50G_v3.10_Win_E/ZOOM MS-50G System v3.10 Updater.exe" \
  --patch patches/hello.yaml --out build/out/ms50g-3.10-hello.exe
zoomms build "firmware/MS-50G_v3.10_Win_E/ZOOM MS-50G System v3.10 Updater.exe" \
  --out build/out/ms50g-3.10-stock-keepboot.exe      # recovery: stock OS, bootloader untouched
zoomms build "firmware/MS-50G_v3.10_Win_E/ZOOM MS-50G System v3.10 Updater.exe" \
  --patch patches/version-0.2.yaml --patch patches/midi-cc.yaml --build-id ms50g-3.10 \
  --out build/out/ms50g-3.10-mod0.2-midicc.exe     # v0.2 test build
zoomms build "firmware/MS-50G_v3.10_Win_E/ZOOM MS-50G System v3.10 Updater.exe" \
  --patch patches/version-0.3.yaml --patch patches/midi-cc.yaml --patch patches/midi-clock.yaml \
  --build-id ms50g-3.10 --out build/out/ms50g-3.10-mod0.3-midiclock-fix7.exe   # v0.3 test build
zoomms build "firmware/MS-50G_v3.10_Win_E/ZOOM MS-50G System v3.10 Updater.exe" \
  --patch patches/version-0.4.yaml --patch patches/midi-cc.yaml --patch patches/midi-clock.yaml \
  --build-id ms50g-3.10 --out build/out/ms50g-3.10-mod0.4-transport.exe   # v0.4 test build
zoomms build "firmware/MS-50G_v3.10_Win_E/ZOOM MS-50G System v3.10 Updater.exe" \
  --patch patches/version-0.5.yaml --patch patches/midi-cc.yaml --patch patches/midi-clock.yaml \
  --patch patches/midi-settings.yaml \
  --build-id ms50g-3.10 --out build/out/ms50g-3.10-mod0.5-midisettings.exe   # v0.5 test build
```

The v0.3 line needs `patches/midi-clock.yaml` as tagged `v0.3`.

Changing assembly in `asm/` needs GNU binutils for tic6x
(`scripts/build-c6x-binutils.sh`); regenerate the bytes in the patch file with
`zoomms asm <file.S> --addr <addr>`. `pytest` checks they match.

## First test (Luca's MS-60B running the MS-50G 3.10 OS)

**Result 2026-10-07: passed.** The patched OS flashed with the bootloader steps
skipped, booted normally, and the menu showed MOD 0.1. So the bootloader does
not reject a modified OS.

1. Keep both `ms50g-3.10-stock-keepboot.exe` and Zoom's original MS-50G v3.10
   updater at hand.
2. Pedal off. Hold the top and bottom buttons while plugging in USB: it should
   show the firmware update screen.
3. Run `ms50g-3.10-hello.exe` and let it finish. Do not unplug during the update.
4. Power-cycle the pedal normally. In the menu, the VERSION entry should now
   read **MOD 0.1**.

If it does not boot, or shows an error:

1. Enter update mode again (step 2) and run `ms50g-3.10-stock-keepboot.exe`.
2. Only if that fails, run Zoom's original updater (which also rewrites the
   bootloader, as it did when you first installed the MS-50G firmware).

Report back what you saw in each case; a failure to boot is also a useful
result (it would mean the bootloader checks something we have not found).

## v0.2 test (MIDI program change and CC)

**Result 2026-10-08: passed** on Luca's MS-60B with `ms50g-3.10-mod0.2-midicc.exe`
(sha256 `272d3d09d1cd6b260b7a6442e02b0db10e03d2d8259f38cfe4956e9f5d063371`),
messages sent from MIDI-OX (View > Control Panel: the Patch buttons send
Program Change, top row then bottom row; the Controller area with "Auto Send
Value" sends CCs).

- Program Change loads patches (PC 0 = patch 1, PC 9 = patch 10).
- CC 14/24/34/44/54/64 switch effects 1-6 on and off; the knob CCs change values.
- Unused CCs (CC 7) change nothing.
- Effect Manager in normal mode still connects and lists the effects.
