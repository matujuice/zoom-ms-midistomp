# MIDISTOMP patch editor (local)

A small page for the MS-70CDR and MS-50G: read all 50 patches, see each slot's effect, on/off and
MIDISTOMP routing (bus, Input R, Master R, Output, mutes, solo), rename, add and remove effects, edit their settings and routing, save a backup
and restore it. It talks to the pedal with the stock patch SysEx, so it works on stock firmware too
(routing then shows "—").

Run it in Chrome or Edge (Web MIDI):

```
py -m http.server 8737 --bind 127.0.0.1 --directory editor
```

then open http://localhost:8737 and press Connect. Close Zoom Effect Manager and other editors first.

- Writing a patch sends it (`28`), stores it (`32`), then reads it back and compares.
- MIXER settings 0-10 and PERFORM are not in the patch (record 50, see
  `docs/dev/modwerk-research.md` section 2), but matched by its effects and name. On MIDISTOMP
  firmware with the SysEx receiver (`F0 7D "MST"`: hello `01`, MIXER read `02` and write `03`,
  PERFORM read `04` and write `05`, see that doc section 1) the editor shows and edits them on the ROUTE, MIX and OUT slots, and when a rename,
  effect move changes the match it writes the old settings under the new one first, so the
  pedal keeps MIXER and PERFORM. Input and Master also set Input R and Master R, as on the pedal.
  Backups carry the MIXER settings and PERFORM too (PERFORM needs firmware with `04`). On stock or
  older firmware both go back to defaults.
- PERFORM: click PERFORM under the chain to set it up as on the pedal's SETUP: Cycle, each control's
  target (an effect's Footsw or parameter, or a mixer level) and its Turn / Press / Hold moves (Value,
  When, Lag), and the looper events in a patch with GRDLOOP. Targets keep their slot numbers when
  effects move, as on the pedal; the editor warns when one points at an empty slot or a missing parameter.
- Add an effect with the "+" at the output end of a zone (Pre, A, B, Post): pick it from the stock list
  or the effects pack, by category or by name. It starts with its default settings. Remove one from its
  settings. A chain holds up to 6. The stock list covers all MS models: an effect this pedal does not have
  becomes THRU when written, and the table says so. The editor does not count DSP: if the pedal shows
  DSP FULL, remove or swap an effect. Adding, removing or moving effects changes the MIXER and PERFORM
  match, so the editor writes them under the new one as for a rename.
- Effect names and parameters: `effect-names.js` and `effect-params.js`, from g200kg/zoom-ms-utility
  (MIT); the pack's in `pack-params.js`, built from the pack's manifests by `scripts/make_pack_params.py`.

Check the decoder: `node editor/test-patch.js`.
