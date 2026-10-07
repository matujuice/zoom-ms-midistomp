# Formats

## Updater flash image
See the docstring at the top of [`zoomms/updater.py`](../zoomms/updater.py).
Source: Zoom-Firmware-Editor. Open questions: meaning of the 8-byte file table
header, of the four table copies, and of system blocks 0-2 (likely boot/OS).

## ZDL effect module
See [`zoomms/zdl.py`](../zoomms/zdl.py). Source: ZoomMultistompZDL
(`build/zdl.py`, `docs/ZDL-REVERSE-ENGINEERING-STATUS.md`). The payload is a
TI C674x ELF32 shared object; exported names like `Dll_<Name>` and
`Fx_<GID>_<Name>` are what the firmware looks up.

## SysEx
Zoom manufacturer id 0x52. Model ids in `models/*.yaml` are community-reported
and must be confirmed with `zoomms identify`.
