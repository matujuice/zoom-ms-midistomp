# Formats

## Official updater (.exe)
The firmware lives in the executable's `BIN` resources. `zoomms updater-parts`
lists and extracts them. Measured on MS-50G v3.10, MS-60B v2.10, MS-70CDR v2.10:

| Resource | Size | Content | Across the three models |
|---|---|---|---|
| BIN/136 | 256 KiB | bootloader, TI AIS image | **byte-identical** |
| BIN/129 | 704 KiB | main OS, TI AIS image | per model; ~99% of strings shared, so one codebase built per model |
| BIN/133 | 12 KiB | factory patches | per model |
| BIN/137 | 2.8 MiB | flash file system with the effects | per model |

AIS (magic `0x41504954`) is the boot-script format read by the ROM bootloader
of TI C674x / OMAP-L13x parts. The identical bootloader is the strongest
evidence so far that the three pedals are the same hardware.

Effects that share a name across models are often *not* byte-identical
(22 of the 51 effects common to all three differ), so a port should copy the
build from the model it was designed for.

Free space differs a lot: MS-50G has 300 free 4 KiB blocks, MS-60B only 10 and
MS-70CDR only 17. Adding effects to an MS-60B means removing others first.

## Updater flash image
See the docstring at the top of [`zoomms/updater.py`](../zoomms/updater.py).
Source: Zoom-Firmware-Editor. The four file-table copies are generations: byte 0 of the table header is a
counter, the live table has the highest counter and 0xFF at byte 4. Older
copies and some free blocks still hold stale chains from earlier builds;
`updater-verify` keeps them as-is and reproduces the live file system exactly
for all three stock updaters. System blocks 0-2 are identical on all three
models; their meaning is still open.

## ZDL effect module
See [`zoomms/zdl.py`](../zoomms/zdl.py). Source: ZoomMultistompZDL
(`build/zdl.py`, `docs/ZDL-REVERSE-ENGINEERING-STATUS.md`). The payload is a
TI C674x ELF32 shared object; exported names like `Dll_<Name>` and
`Fx_<GID>_<Name>` are what the firmware looks up.

## SysEx
Zoom manufacturer id 0x52. Model ids in `models/*.yaml` are community-reported
and must be confirmed with `zoomms identify`.
