# MIDISTOMP patch editor (local)

A small page for the MS-70CDR and MS-50G: read all 50 patches, see each slot's effect, on/off and
MIDISTOMP routing (bus, Input R, Master R, Output, mutes, solo), rename, edit routing, save a backup
and restore it. It talks to the pedal with the stock patch SysEx, so it works on stock firmware too
(routing then shows "—").

Run it in Chrome or Edge (Web MIDI):

```
py -m http.server 8737 --bind 127.0.0.1 --directory editor
```

then open http://localhost:8737 and press Connect. Close Zoom Effect Manager and other editors first.

- Writing a patch sends it (`28`), stores it (`32`), then reads it back and compares.
- MIXER settings 0-10 and PERFORM are not in the patch (record 50, see
  `docs/dev/modwerk-research.md` section 2): renaming a patch or moving it to another number resets
  them for that patch. The MIDISTOMP firmware can now report them (SysEx `F0 7D "MST"`, hello
  `01` and settings `02`, see that doc section 1); the editor does not use it yet.
- MS-60B: not supported yet (other patch layout).
- Effect names: `effect-names.js`, from g200kg/zoom-ms-utility (MIT). Pack effects show as `id …`.

Check the decoder: `node editor/test-patch.js`.
