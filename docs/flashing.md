# Building and flashing a modified OS

## What our updaters do differently from Zoom's

The stock updater runs a fixed script (see `zoomms/flash.py`):

1. erase the last 4 KiB of the OS area (its trailer)
2. erase and rewrite the **bootloader**
3. erase and rewrite a 12 KiB block at 0x3FD000
4. (MS-60B, MS-70CDR only) erase and rewrite the effects file system
5. erase and write the main OS

Updaters built by `zoomms build` skip steps 2, 3 and 4. The bootloader holds the
USB update mode, so never touching it keeps that recovery path intact even if
an update is interrupted. Skipping step 4 (the MS-70CDR updater has it; the
MS-50G one never did) keeps your installed effects: an update never deletes them.
The MIDISTOMP builder takes Zoom's MS-70CDR 2.10 updater (`--build-id ms70cdr-2.10`).

Zoom's updater only flashes a pedal whose model byte (flash `0x3FFC00`, BIN/133
offset 0x2C00) is on its list: `0x57` and `0x61` in the MS-70CDR updater, so a
pedal on the MS-50G firmware (`0x58`, every v1.0/v1.1 install) gets "Illegal
device connected". Built updaters accept `0x57`, `0x58`, `0x5F` and `0x61`
(`flash.accept_models`: the list moves into 4 unused bytes after it, both loop
bounds go from 2 to 4). The bytes the pedal is sent are unchanged.

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
  --build-id ms50g-3.10 --out build/out/ms50g-3.10-mod0.5-midisettings-r2.exe   # v0.5 test build
zoomms build "firmware/MS-50G_v3.10_Win_E/ZOOM MS-50G System v3.10 Updater.exe" \
  --patch patches/version-0.6.yaml --patch patches/midi-cc.yaml --patch patches/midi-clock.yaml \
  --patch patches/midi-settings.yaml --patch patches/tempo-hold.yaml \
  --build-id ms50g-3.10 --out build/out/ms50g-3.10-mod0.6-tempohold.exe   # v0.6 test build
zoomms build "firmware/MS-50G_v3.10_Win_E/ZOOM MS-50G System v3.10 Updater.exe" \
  --patch patches/midi-cc.yaml --patch patches/midi-clock.yaml \
  --patch patches/midi-settings.yaml --patch patches/tempo-hold.yaml --patch patches/ram-test.yaml \
  --build-id ms50g-3.10 --out build/out/ms50g-3.10-mod0.6-ramtest.exe   # RAM test (#19), diagnostic only
zoomms build "firmware/MS-50G_v3.10_Win_E/ZOOM MS-50G System v3.10 Updater.exe" \
  --patch patches/version-1.0.yaml --patch patches/boot-logo.yaml --patch patches/midi-cc.yaml \
  --patch patches/midi-clock.yaml --patch patches/midi-settings.yaml --patch patches/tempo-hold.yaml \
  --build-id ms50g-3.10 --out build/out/ms50g-3.10-midistomp-1.0.exe   # MIDISTOMP V1.0
zoomms build "firmware/MS-50G_v3.10_Win_E/ZOOM MS-50G System v3.10 Updater.exe" \
  --patch patches/version-1.1.yaml --patch patches/boot-logo.yaml --patch patches/midi-cc.yaml \
  --patch patches/midi-clock.yaml --patch patches/midi-settings.yaml --patch patches/tempo-hold.yaml \
  --patch patches/scroll.yaml \
  --build-id ms50g-3.10 --out build/out/ms50g-3.10-midistomp-1.1.exe   # MIDISTOMP V1.1 (frozen, tag v1.1)
zoomms build "firmware/MS-70CDR_v2.10_Win_E/ZOOM MS-70CDR v2.10 Updater.exe" \
  --patch patches/version-1.2.yaml --patch patches/boot-logo.yaml --patch patches/midi-cc.yaml \
  --patch patches/midi-clock.yaml --patch patches/midi-settings.yaml --patch patches/tempo-hold.yaml \
  --patch patches/scroll.yaml \
  --build-id ms70cdr-2.10 --out "build/out/MIDISTOMP V1.2 Updater.exe"   # MIDISTOMP V1.2, all pedals
```

`patches/boot-logo.yaml` changes updater part BIN/133 (boot logo) instead of
the OS, so that build keeps the stock BIN/133 erase and write steps; the
bootloader steps stay skipped. `ms50g-3.10-stock-keepboot.exe` skips BIN/133
and so leaves the MIDISTOMP logo in place; Zoom's own updater restores it.

The v0.3 line needs `patches/midi-clock.yaml` as tagged `v0.3`, the v1.0 line
`patches/midi-cc.yaml` as tagged `v1.0` (v1.1 adds CC 80/81 to it).

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

## Mac updater

`zoomms build-mac` does the same for Zoom's Mac updater app, see
`zoomms/macapp.py`. v1.2 is built from `MS-70CDR_v2.10_Mac_E`; v1.1 was built
from `MS-50G_v3.10_Mac_E` (command below, needs tag `v1.1`). In both, the
`Resources/Main.bin`, `Preset.bin`, `boot.bin` and `FS.bin` are byte-identical
to BIN/129, 133, 136 and 137, and `_RomProcedure` in the executable is the
same script as the Windows updater's (7 steps, 9 with the MS-70CDR's FS.bin),
with types 0 = erase, 1 = write. The build replaces `Main.bin` and
`Preset.bin`, updates their entries in the executable's MD5 table, and sets
the same steps as the Windows build to type 2, which the loop skips. Built
with the same patch set, `Main.bin` and `Preset.bin` match the Windows build's
BIN/129 and BIN/133 exactly.

The MS-70CDR app's model check (in `-[MainWindow SendIdReq]`) loops over
`_kTargetDeviceIDs`, two int32 `{0x57, 0x61}`. A double follows the list, so
it can't grow in place: the build reads the list as bytes instead (one
`movzbl` plus a nop in place of `shl`/`add`/`movl`), stores `0x57 0x58 0x5F
0x61` in its 8 bytes and raises the loop bound from 2 to 4. The MS-50G app's
check is different and is left alone.

The window title (Zoom's app name, a constant CFString) becomes the name of
the `--out` app, at most 27 characters. The app must be re-signed ad hoc on
the Mac (`xattr -cr` then `codesign --force --deep --sign -`).

```sh
zoomms build-mac "firmware/MS-70CDR_v2.10_Mac_E/ZOOM MS-70CDR v2.10 Updater.app" \
  --patch patches/version-1.2.yaml --patch patches/boot-logo.yaml --patch patches/midi-cc.yaml \
  --patch patches/midi-clock.yaml --patch patches/midi-settings.yaml --patch patches/tempo-hold.yaml \
  --patch patches/scroll.yaml --build-id ms70cdr-2.10 --out "build/out/MIDISTOMP V1.2 Updater.app"
zoomms build-mac "firmware/MS-50G_v3.10_Mac_E/ZOOM MS-50G v3.10 Updater.app" \
  --patch patches/version-1.1.yaml --patch patches/boot-logo.yaml --patch patches/midi-cc.yaml \
  --patch patches/midi-clock.yaml --patch patches/midi-settings.yaml --patch patches/tempo-hold.yaml \
  --patch patches/scroll.yaml --build-id ms50g-3.10 --out "build/out/MIDISTOMP V1.1 Updater.app"   # tag v1.1
```
