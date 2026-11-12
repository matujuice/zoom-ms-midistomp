# Patch manager: plan and file format (proposal)

Jannik (Modwerk board, 2026-11-12) set the order and rules. This file proposes the patch file format he asked for.

## Order
1. Patch manager: read, write and back up patches. MIDISTOMP's record 50 entry (MIXER, PERFORM) sits beside the stock patch.
2. Editing, built on top of the manager.
3. Sharing, once the editor works. There is no sharing place yet.

Both 1 and 2 go as PRs on Modwerk's existing Zoom page, and they link to this repo's code (`editor/patch.js`, `editor/index.html`).

## Pedal safety (Jannik)
- No write without a backup. The manager saves a full backup, and checks it, before its first write in a session.
- The stock-only view stays. On stock firmware, or with MIDISTOMP data turned off, the manager shows and writes only the stock patch.
- SysEx: 7D is fine, followed by a short MIDISTOMP signature. MIDI settings (record 51) go in the same backup.

## One patch: `*.msp.json`
One versioned JSON file per patch. The stock bytes and MIDISTOMP's settings are kept apart, so a stock-only tool can read or write the `stock` part and ignore the rest.

```json
{
  "format": "midistomp-patch",
  "version": 1,
  "model": "MS-50G",
  "saved": "2026-11-12T10:00:00Z",
  "stock": {
    "record": "<122 bytes as hex: the stock patch record, exactly as the pedal sends it>"
  },
  "midistomp": {
    "firmware": "2.0.x",
    "mixer": [11 numbers],
    "perform": "<208 bytes as hex>"
  }
}
```

- `stock` is required. `midistomp` is optional, and each key in it is optional. A missing key means stock defaults on load.
- `stock.record` is the only part a stock pedal ever receives.
- `mixer` and `perform` keep the layout the pedal uses (record 50 entry; `asm/perform/perform.h`), so the file needs no conversion code of its own.
- The name and effect list are not stored twice: they are read from `stock.record`. A sharing page can show them by decoding the record with `patch.js`.
- `version` goes up only when an existing field changes meaning. New optional keys do not bump it. A reader refuses versions newer than it knows.
- On load, the manager checks the whole file (hex lengths, routing bytes, value ranges, `PT_OK` in `perform`) before it changes anything. It already does this for backups.

## Full backup: `*-patches-YYYY-MM-DD.json`
This is today's editor backup (`format: "midistomp-patches"`, version 1: 50 records, `mixer[50]`, `perform[50]`), with one addition:
- `midi`: record 51 (MIDI settings) as hex.

Version 1 backups without `midi` still load.

## Open
- Whether a single-patch file should also carry the effect pack's versions (which ZDL build made the effect), so a shared patch can warn about a missing or older effect.
