# Modwerk: answers to their four questions

Research and drafts only, 2026-10-28. Nothing built, nothing sent. Their side:
`docs/ZOOM_MULTISTOMP.md` in repeat98/modwerk, branch `claude/zoom-midistomp-base` (read
2026-10-28). Plan entries: "Modwerk (answers they need first)" and "Research: Modwerk" in
[repo-refresh-plan.md](repo-refresh-plan.md); transport words 6/7 in
[joint-plan-v2.0.md](joint-plan-v2.0.md) section 1.

Evidence is `file:line` in this repo. "Not checked on hardware" means read from code only.

## 1. Detection over MIDI: a hello SysEx

### What exists today

- The firmware has **no SysEx code of its own**. The stock OS reads SysEx through a state table
  (`0xC00EF84C`) and runs complete messages in a command switch (`0xC00AE880`)
  (`docs/dev/os-reverse-engineering.md:86-87`). Addresses are MS-50G ones; the 70CDR
  counterparts of the SysEx executor, the table and the identity builder are **not mapped**.
- The identity reply is stock: the template is at `0xC00ED060`, built at `0xC00AD884`, and the
  model byte goes in it (`docs/dev/ms70cdr-port.md:127-128`, also 50G addresses).
- Host side: `zoomms/midi.py:9` sends `7E 00 06 01`; `midi.py:21-29` parses
  `7E ch 06 02 mfr famLo famHi modLo modHi v1..v4`; the four version bytes are the **stock OS
  version** ("2.10"), shown by `zoomms identify` (`zoomms/cli.py:23`). MIDISTOMP does not change
  them, so today the identity reply cannot tell MIDISTOMP from stock.
- The model byte is per-unit flash data (BIN/133 offset 0x2C00) and is `0x58` on almost every
  MIDISTOMP pedal, because the boot-logo build rewrites BIN/133 with MS-50G data
  (`docs/dev/ms70cdr-port.md:170-180`). It is not a MIDISTOMP marker.
- Our hook sees every received byte: `asm/midi_clock/clock.S:1-8` (end of Task_MIDI's byte
  loop, 70CDR `0xC00AEEE0`, byte at `B14+226`, `clock.S:61-70`). SysEx bytes pass through it
  too; today everything except F8/FA/FC returns at once (`clock.S:14-15`). `diag_me`
  (`asm/diag/diag_vec.asm:31`) already chains to the same site in test builds.
- Version text in a release build: only the string "v1.2" at `0xC00F2000`, used for the boot
  screen, and the menu entry (`patches/version-1.2.yaml:6-18`). Nothing readable by code
  except the DIAG stamp (`asm/diag/diag_vec.asm:19-26`, `diag.c:32`, test builds only).
  v2.0 needs a `version-2.0.yaml` first (no such file yet).
- The OS already sends SysEx to an editor in editor mode (tempo notify, `0xC00AF2D0`,
  `os-reverse-engineering.md:205`), and the identity reply goes out from Task_MIDI's own
  executor, so a send from that context works. The send routine is not mapped for the 70CDR.
- Rule from the CC work: leave stock SysEx handlers unchanged, Effect Manager uses them
  (`os-reverse-engineering.md:113-116`). Our hook must never swallow a byte.

### Proposal (not agreed, not built)

Two steps, so the cheap one can ship first.

**Step A, data only: a marker in the identity reply.** Change the four version bytes in the
identity template (a data patch, no code) to a MIDISTOMP tag, e.g. `V200` (7-bit ASCII).
Modwerk's existing identity request then tells MIDISTOMP and its version. Risks to test:
Effect Manager or Zoom's updater might read that field (unknown; `zoom-effect-manager.md:66`
lists related open questions). Needs the 70CDR address of the template.

**Step B, code: a "hello" exchange.** Use the MIDI "non-commercial" manufacturer id `7D`, not
Zoom's `52`, so no stock command can fire on it. All data bytes are 7-bit.

Request, host to pedal (7 bytes):

    F0 7D 4D 53 54 01 <nonce> F7        "MST", command 01 = hello, nonce 00..7F

Reply 1, version (11 bytes), sent at once:

    F0 7D 4D 53 54 41 <nonce> <major> <minor> <patch> F7      command 41; v2.0.0 = 02 00 00

Reply 2, status (13 bytes), sent right after:

    F0 7D 4D 53 54 42 <nonce> <f0> <f1> <f2> <state> F7       command 42

- `f0 f1 f2`: 21 feature bits, 7 per byte, low bit first: 0 CC, 1 clock+transport,
  2 MIDI settings, 3 tempo-hold, 4 looper services, 5 mixer, 6 PERFORM, 7 MASTER, 8 KALEIDO,
  9 diag, 10 DSP 300. Each set from the same magic words the code already checks
  (transport `0x5A4D5401`, looper services `0x5A4C5301`, diag `"DIAG"`).
- `state`: bit 0 editor mode on (SysEx 50), bit 1 looper recording or playing. The value
  `0x7F` means "unknown". Modwerk should not flash while bit 0 or 1 is set.
- An unknown command with the `7D "MST"` header is ignored; the nonce comes back unchanged so
  replies can be matched.

**Firmware work for step B** (1 session plus a hardware test):
1. Find the 70CDR transmit routine used by the identity reply and the SysEx executor
   (`0xC00AE880`-equivalent). Not done.
2. Receive: a small state machine in the existing Task_MIDI hook (`clock.S` / `diag_me`
   chain). Fast path stays one compare (byte `F0` or "in sequence"); zero extra cost otherwise
   (CPU rule). Check what the stock state table does with `F0 7D`: it must ignore it.
   **Not checked on hardware.**
3. Transmit from Task_MIDI's context (as the identity reply), not from the audio path.
4. Version bytes: from `version-2.0.yaml` (release) or the DIAG stamp.
5. Test: `tests/` host test for the parser, then a pedal test with and without Effect Manager.

Open: is `7D` acceptable to their side and to Windows MIDI stacks (some drop unknown
SysEx)? Does the hello also work through `zoomms`? (We can add `zoomms hello`, small.)

## 2. Where routing and PERFORM live in a patch

Short version: **routing is in byte 17 of each 18-byte slot block; PERFORM and half of the
mixer settings are not in the patch at all but in global record 50, matched to a patch by a
hash.** An editor that writes whole patches loses nothing if it keeps byte 17 and does not
change effect ids or name; if it does, the pedal falls back to defaults for that patch.

### Byte 17 (in the patch)

A packed patch is 122 bytes: six 18-byte slot blocks, then the name at bytes 111-121
(`asm/mixer/pages.c:196-206` hashes `rec[111..121]`). Bytes 0-16 of a block are the effect's
(P8 reaches byte 15), byte 17 is ours (`pages.c:176-195`, `asm/mixer/mixer.S:22-29`).
Stock leaves byte 17 at 0 and ignores it (`docs/dev/mixer-mode-m3-research.md:93-100`).

| Bits of byte 17 | What | Source |
|---|---|---|
| 0-1 | bus of this slot: 0 PRE, 1 A, 2 B (3 = POST is not stored) | `pages.c:219,257`, `chain.h:8-10` |
| 2-6 | 5-bit chunk `i` of a 22-bit word: Input R ^ 100 (8 bits), Master R ^ 100 (8), Output mode (2), Mute A, Mute B, Solo (2) | `pages.c:221-224,241-246,253-258` |
| 6 of block 6 (slot 5) | marker "5-bit chunk layout" (older saves used 6-bit chunks) | `pages.c:217,260` |
| 7 | always 0: after a SysEx round trip it lands in other bytes | `pages.c:260`, commit b70dc01 |

Notes for an editor:
- The **chunk bits (2-6) belong to the block position, not to the effect**. Only bits 0-1
  travel with the effect. If the editor reorders effects, move bits 0-1 with the effect and
  keep bits 2-6 where they are.
- Byte 17 = 0 is safe: PRE bus, Input R and Master R unity, Output stereo, no mutes
  (`mixer.S:47-48`, `pages.c:241-244`). A patch with a zeroed byte 17 just loses its routing.
- Do **not** write bit 7. Do not use bytes 14 and 15 for anything: they are the effect's.
  Very old builds (M3b5/6) stored settings there; the pedal reads those once
  (`pages.c:228-229`, `mixer.S:37-40`).
- The pedal puts byte 17 into every patch it sends to an editor (`pack_dump`,
  `mixer.S:41-42`) and keeps the editor's byte 17 in a patch the editor stores
  (`mixer.S:34-35`). So read-modify-write is enough: read the patch from the pedal, change
  only what you know, write the whole 122 bytes back.

### Record 50 (not in the patch)

Mixer settings 0-10 (mode, send, levels, curve, XFade...) and PERFORM live in the global
record 50, grown from 24 to **6428 bytes** (`asm/mixer/chain.h:25-26`, `patches/mixer-m2.yaml`
record size table entry):

| Offset | Size | What |
|---|---|---|
| 0 | 24 | stock globals |
| 24 + 16n | 16 | mixer entry for patch n: 4 B hash, settings 0-10, pad (`pages.c:179,251-272`) |
| 824 | 4 | magic `PRF2` (`asm/perform/perform_store.c:11,13`) |
| 828 + 112n | 112 | PERFORM entry for patch n (`perform_store.c:14`, `perform.h:91`) |

- The hash is FNV-1a over the six effect ids (bits 1-28 of each block: `b[0]&0xFE, b[1], b[2],
  b[3]&0x1F`) and the name (`pages.c:196-206`). **Not** over params, on/off or byte 17.
- A PERFORM entry has no hash of its own; it is valid if mixer entry n has the live hash and
  the PERFORM entry's byte 15 is `0xA5` (`perform_store.c:29-38`).
- Load order for settings 0-10: entry n if the hash matches, else old bytes 14/15, else any
  entry with the same hash (a copy), else defaults (`pages.c:214-246`).
- Written only by STORE of the patch being played (`pages.c:262-270`, `perform_store.c:64-83`).

What this means for a patch editor:

| The editor... | Result |
|---|---|
| changes params, on/off, tempo, keeps ids, order, name, byte 17 | nothing lost |
| zeroes byte 17 | routing back to PRE/default; settings 0-10 and PERFORM kept |
| renames the patch, or adds, removes, swaps or reorders effects | hash changes: settings 0-10 and PERFORM for it fall back to defaults (`pages.c:187-189`); the old entry stays until the next STORE for that patch overwrites it |
| writes a patch to another slot number | entry n does not match; a copy finds its original's entry by hash (`pages.c:229-232`), a new patch gets defaults |

Record 50 is not reachable through the patch SysEx an editor uses. **Open:** do Modwerk's
per-file USB commands (list/read/write/delete in normal mode) reach the record store, or only
the effect file system? Records 50 (globals, mixer + PERFORM) and 51 (MIDI settings,
`settings.S`) must not be written or deleted by them. A stock factory reset or a downgrade
also clears the table (`mixer-mode-m3-research.md:112-114`).

Docs gap: the comment above `mix_get` (`pages.c:176-181`) still says bits 2-7 and 36 bits,
and `mixer.S:25` says 21 bits; the code (5 bits per block, 22 used) is right. Fix on the
next firmware pass.

Offer to Modwerk: a one-page `docs/dev/patch-routing-bytes.md` with the table above, for
their editor, once Luca agrees.

## 3. Feature dependencies

### Current packaging

The release set (`scripts/midistomp_builder.py:23`) is: version, boot-logo, midi-cc,
midi-clock, midi-settings, tempo-hold, scroll. **Mixer, PERFORM, MASTER, KALEIDO, the mixer's
Effect Chain and pedal-input pages are one patch file today, `patches/mixer-m2.yaml`** ("test
builds only"). The looper services are `patches/looper.yaml`, diag is `patches/diag.yaml`,
DSP 300 is a single write inside `diag.yaml` and the M0 probe.

### Dependency table

| Feature | Patch file | Needs | Reads (soft, by magic) | Hard-wired to |
|---|---|---|---|---|
| MIDI CC (14-74 effect control, 80/81 patch) | midi-cc | nothing | | CC call site `0xC00AF088`; handler at DDR `0xC00F2800`, step at `0xC00F2020` |
| MIDI clock + transport block | midi-clock | nothing | | Task_MIDI byte-loop hook `0xC00AEEE0`, 16 ms poll site `0xC00C6998`, cave `0xC00A1A50`/`0xC00C82D0`; L2 block `0x1181FF00`, vars `0x1181E700` (`patches/midi-clock.yaml:17-37`) |
| MIDI settings | midi-settings | midi-cc, midi-clock (applied after; clock.S and poll.S read its flags word `0x1181EA00`) | | menu, record 51; L2 `0x1181EA00` |
| Tempo screen, HOLD FOR, combos | tempo-hold | midi-settings | | needs the HOLD FOR choice screen |
| Scroll | scroll | nothing | | DDR `0xC00F2100` |
| Looper services | looper | midi-cc, midi-clock, tempo-hold (it retargets their trampolines, `looper.yaml:13`) | | DDR `0xC00F2200`, services block `0xC00F3000` (magic `0x5A4C5301`), big buffer regions 3, 2, 1 (`looper-services.md:39-43`) |
| Mixer + Effect Chain screen | mixer-m2 | the release set above, midi-cc (its CC 85-101 sit on the handler, `mixer-m2.yaml:90-92`), midi-settings (menu and tables, `:96-125`) | looper (`mixer.S:108` checks `0x5A4C5301`; apply looper first) | slot-loop packet `0x1181BE00`, record 50 (`R50 0xC01086E0`), patch save/load/pack/dirty hooks, DDR `0xC00F6000-0xC0110480` |
| PERFORM | in mixer-m2 | mixer (hooks `mix_get/mix_put`, the hash, record 50) | transport (`perform_engine.c:96`), looper (`SV_OK`) | screen 11, PERFORM table in record 50 |
| MASTER, KALEIDO | in mixer-m2 | mixer (menu entry byte `0xC00F60BF`, `master.h:34`) | transport (`master.c:872`) | DDR `0xC010A000-0xC0110480` |
| Diag | diag | mixer-m2 (engine calls `diag_end` only if its magic is there), midi-clock (its hook site expects midi-clock's callp), the mixer MENU7 slot "SYSTEM" | | DDR `0xC00F3100`; test builds only |
| DSP 300 | write inside diag/m0-probe | nothing | | one write: `0xC00BB52C`, `eab02102` to `6acb2102` (`diag.yaml`, `asm/m0_probe/dsp_limit.S`) |

### Answer for Modwerk

- **Can be separate mods today (own yaml, no cross-hooks):** midi-cc, midi-clock, scroll,
  boot-logo, version. midi-settings and tempo-hold are a chain on top of these.
- **A chain, not independent:** midi-cc, midi-clock, midi-settings, tempo-hold, looper in
  that order; each later patch retargets the earlier one's trampolines. Treat it as one mod
  "MIDI + hold + looper services" with the looper as an optional last step.
- **One block:** mixer, PERFORM, MASTER, KALEIDO. Splitting needs real work: they share the
  menu table (MENU7), record 50 and the patch hooks. Cheapest honest answer: one mod
  "Mixer suite" with the features inside it shown as read-only items.
- **DSP 300** is easy to split (a single 4-byte write, no dependency) but today it ships only
  in test builds, and above the stock limit "clicks or dropouts" are possible
  (`mixer-mode-m0.md:474-481`). **Ships in v2.0** (Luca, 2026-10-28).
- **Diag** stays a test build; not for their base.
- **Transport block goes in the base.** Words 0-5 exist (`docs/dev/transport-block.md`,
  address `0x1181FF00`, magic `0x5A4D5401`). Words 6 and 7 are planned for v2.0 with no
  version bump (`joint-plan-v2.0.md:9-26`): word 6 `0x1181FF18` = 1 while the footswitch is
  physically down; word 7 `0x1181FF1C` = the hold claim an effect writes every block and the
  poll clears every 16 ms. Both are 0 on older firmware and the magic stays the same, so
  effects can read them without a version check. They are written by `poll.S` (midi-clock)
  and read by the hold path (`looper.S` `hold_pre`, `asm/looper/hold_trampoline.S`), so
  "transport in the base" must include the hold path, not only midi-clock. **Not built yet.**
- Detection (answer 1) gives the feature bits so Modwerk can tell which of these are in the
  flashed image.

### Shared addresses (so two mods never overlap)

| Area | Range | Owner |
|---|---|---|
| L2 transport block | `0x1181FF00-0x1181FF1F` | midi-clock, ABI for effects |
| L2 midi-clock vars / poll / settings / hold / hold2 | `0x1181E700`, `0x1181E800`, `0x1181EA00`, `0x1181FA80`, `0x1181FF20` | `ms70cdr-addresses.md:351-363` |
| DDR small patches | `0xC00F2000` version, `0xC00F2020` step, `0xC00F2100` scroll, `0xC00F2200` looper, `0xC00F2800` midi-cc | those patches |
| DDR services block | `0xC00F3000-0xC00F307F` | looper |
| DDR diag | `0xC00F3100-` | diag |
| DDR mixer / perform / master | `0xC00F6000`, far `0xC00F7000`, C `0xC00F8000`, R50_COPY `0xC0106DC0`, R50 `0xC01086E0`, master `0xC010A000-0xC0110480` | mixer-m2 |
| DDR looper buffer | `0xC0116000` (+ regions `0xC0198000`, `0xC0636980`) | looper (`block.S:8-10`) |
| Flash records | 50 (globals, mixer, PERFORM), 51 (MIDI settings) | mixer-m2, midi-settings |

Browser builder, Zoom code, effect IDs, transport contract, fallback, testing: section 5.

## 4. Their flash steps against zoomms

Their steps (from the question, and `ZOOM_MULTISTOMP.md` "Not built yet": erase `0A`, write
`02`, finish `04`; Up+Down at power-on recovers): erase OS trailer `0x0EF000`; boot logo only
if changed; `0x040000 +0xB0000`; write Main.bin; never `0x000000` or `0x0F0000`.

### What our updaters do

Stock MS-70CDR script (Mac `SCRIPT_70CDR`, `zoomms/macapp.py:51-64`; Windows described at
`zoomms/flash.py:9-16`):

    erase 0x0EF000 +0x1000      OS trailer              (macapp.py:52, flash.py:10)
    erase 0x000000 +0x40000     bootloader              SKIPPED by us
    write 0x000000 boot.bin                             SKIPPED
    erase 0x3FD000 +0x3000      BIN/133 (Preset.bin)    kept only if the logo changed
    write 0x3FD000 Preset.bin                           kept only if the logo changed
    erase 0x0F0000 +0x2C7000    FS.bin                  SKIPPED
    write 0x0F0000 FS.bin                               SKIPPED
    erase 0x040000 +0xB0000     main OS                 (macapp.py:57)
    write 0x040000 Main.bin, whole file                 (macapp.py:58; Windows flash.py:40)

The skip rule: `flash.boot_steps` marks any step with address below `0x40000`, address
`0xF0000`, or `0x3FD000` unless a new BIN/133 is given (`flash.py:77-86`). `macapp.build_app`
and `flash.build_updater` apply it (`macapp.py:178-180`, `flash.py:100-102`). The trailer erase
`0x0EF000` is above `0x40000`, so it **stays**. Their list matches this.

Order matters: trailer erase first, OS write last. We infer (not proven) that an interrupted
update leaves the OS invalid so the bootloader stays in update mode (`flash.py:18-24`,
`docs/flashing.md`). `0xB0000` from `0x040000` ends at `0x0F0000`, so Main.bin includes the
trailer sector (`0x0EF000`); the erase just before the write is the trailer erase repeated.

### What the updaters do that their script may not show

1. **Model check before flashing.** The updater sends an identity request and refuses a pedal
   whose model byte is not on a list ("Illegal device connected"): `0x57`, `0x61` in the stock
   70CDR updater (`macapp.py:215-222`, `flash.py:107-113`, `docs/flashing.md:23-30`). MIDISTOMP
   builds extend the list to `0x57, 0x58, 0x5F, 0x61` (`flash.py:113`, `macapp.py:238-252`).
   A browser flasher has no such check unless it adds one; it should check the identity reply
   (model in that list, firmware field `2.10`) and refuse otherwise. Also refuse a pedal that
   does not answer.
2. **BIN/133 is more than the logo.** `0x3FD000 +0x3000` includes flash `0x3FFC00`, the pedal's
   **model byte** (`docs/dev/ms70cdr-port.md:170-180`). Writing Preset.bin from a stock 70CDR
   updater sets it to `0x61`; our logo build writes MS-50G data, so `0x58`. Only the first
   1024 bytes are the logo (`patches/boot-logo.yaml`). "Only if changed" is right; if they do
   write it, take Preset.bin from the user's updater and change only the logo bytes, as
   `zoomms` does (`cli.py:_apply_patches`, `patcher.apply_bin133`), so nothing else in the
   sector changes.
3. **File integrity checks.** The Mac updater refuses any resource whose MD5 is not in its
   table (`-[MainWindow ReadUpdateBin:]`, `macapp.py:12-13`), so `build_app` rewrites the MD5
   of Main.bin and Preset.bin (`macapp.py:164-176`). Our Windows path patches no hash
   (`flash.py:89-104`), so none was found there. A browser flasher is not bound by either, but
   it must not assume the pedal's bootloader accepts any bytes: only the Main.bin form below
   has been tested on hardware.
4. **Main.bin form.** Same length as stock: 0xB0000 bytes (`macapp.py:170-171`,
   `flash.py:97-98`). A rebuilt AIS stream, `0xFF` padding, then the original tail kept in
   place (version text `2.10` and "Zoom Corporation" marker, "which the bootloader may check"):
   `zoomms/ais.py:152-162`, asserted at `cli.py` (`original[-32:]`). No checksum was found in
   the OS image (`os-reverse-engineering.md:30-32`); whether the bootloader checks something
   else is unknown.
5. **FS.bin skipped on purpose**: an update must never delete the user's installed effects
   (`flash.py:20-24`, `docs/flashing.md:14-17`). Their per-effect USB installs depend on
   that. Running Zoom's own updater later rewrites the file system (and the bootloader).
6. **Bootloader never written** (`flash.py:19-22`): this keeps Up+Down update mode as the
   recovery path (`docs/safety.md:3-6`). Matches their note.
7. **Wire protocol is not in this repo.** We only know the step table (type, address, length,
   resource) that the updater sends to the bootloader over USB MIDI; the bytes themselves
   ("the bytes the pedal is sent are unchanged", `docs/flashing.md:24-26`) were never
   captured here. Their `0A / 02 / 04` therefore cannot be checked by us. Also unknown:
   chunk size, whether the updater waits for per-chunk acks, any "finish"-time reboot
   command, timing, how it behaves when the pedal is not in update mode.
8. Cosmetics we do (window title, code signature removed, PE checksum, Mac re-sign) are not
   needed for a browser flash.

### Suggested checks before they record a flash

- Record a **stock** updater flash to a MIDISTOMP pedal in a MIDI monitor and compare their
  erase/write/finish bytes and chunking to it. We can do this on Luca's pedal and send them
  the capture (with the Zoom bytes removed).
- First write on a pedal that is known to enter update mode (Up+Down while plugging in USB),
  stock updater at hand (`docs/safety.md`).
- Flash only the three steps: trailer erase, OS erase, OS write (plus 133 if the logo is
  changed). Verify afterwards with `zoomms identify` and the VERSION entry.

## 5. Browser builder, Zoom code, effect IDs, transport, fallback, testing

Read 2026-10-28 from both repos (effects pack at `de39287`). Not checked on hardware.

### 5.1 What `zoomms build` does, and the browser version

`cmd_build` (`zoomms/cli.py:108-137`), as run by `scripts/midistomp_builder.py:23`:

1. Check the user's updater by sha256 (`models/ms70cdr.yaml`: `stock_updater_sha256`).
2. Find the BIN resources with `pefile` (`zoomms/parts.py:41-58`) and read BIN/129 (main
   OS, AIS) and BIN/133 (logo + model byte block).
3. Parse the AIS stream (`zoomms/ais.py`, stdlib only).
4. For each patch YAML, in a fixed order: `replace` (same-length text), `write` (bytes at an
   address, only if the stock bytes there equal `expect`), `section` (new AIS load section),
   `bin133` (logo bytes, guarded by a sha256) (`zoomms/patcher.py:63-122`). Stamp fields
   (version, commit, date, label) fill 16-byte placeholders (`patcher.py:47-60`,
   `cli.py:74-87`; the commit comes from `git`, a browser would pass it in).
5. Rebuild BIN/129 at the stock size with the original tail (`ais.py:152-162`).
6. Windows: rewrite the flash script to skip boot/FS steps, extend the model list, drop
   Zoom's signature, fix the PE checksum (`zoomms/flash.py:89-151`). Mac: rewrite
   `_RomProcedure` types and the `_MD5Tbl` entries (`zoomms/macapp.py:164-180`).
7. Check the result (section list, entry point, last 32 bytes, nothing changed outside the
   two parts: `cli.py:122-129`).

**No TI tools at build time.** Every YAML already carries the assembled bytes as hex
(`zoomms/asm.py:4-5`); binutils / TI cl6x are only for changing the source. Python deps:
`pyyaml`, `pefile` (`pyproject.toml`).

A browser flasher needs steps 1-5 and 7 only; its output is Main.bin (0xB0000 B), plus
Preset.bin when the logo changes. Step 6 (exe/app rewrite, MD5, signature) is not needed: the
browser sends the parts itself. Two ways:

- **Pyodide**: run `ais.py` + `patcher.py` unchanged (pure Python, PyYAML is in Pyodide).
  Smallest port. The input is pinned by sha256, so the BIN/129 and BIN/133 offsets in the
  stock .exe are constants and `pefile` can go; on the Mac, `Main.bin` and `Preset.bin` are
  plain files in the .app.
- **JS port**: about 250 lines (AIS parse/build, the four patch kinds, stamp), YAMLs turned
  into JSON at release time. Test: Main.bin byte-identical to `zoomms build` for the release
  set.

Patch sizes (bytes in sections): version 8, midi-cc 551, midi-clock 2 400, midi-settings
4 289, tempo-hold 1 460, scroll 259, looper 4 482, mixer-m2 93 044, diag 6 207.

Order rule for their selector: patches apply in the release order (version, boot-logo,
midi-cc, midi-clock, midi-settings, tempo-hold, scroll, then looper, then mixer-m2). Some
`write` entries accept a list of `expect` values because an earlier patch chained the same
hook. A wrong order or a missing dependency fails loudly (`expect` mismatch); it never builds
a broken image.

v2.0 gaps: `midistomp_builder.py` still says V1.2 and its list has no looper or mixer-m2;
there is no `version-2.0.yaml` yet.

### 5.2 No Zoom code shipped

Firmware repo: releases ship `MIDISTOMP-builder.exe` and the patches; the user brings Zoom's
updater (`.github/workflows/builder.yml:1`). `bin133` uses a sha256, not Zoom bytes. Two small
items:

- `write` entries carry the **stock bytes** they replace as `expect`: about 900 bytes of Zoom
  OS instructions across the v2.0 set (release set 518, looper 68, mixer-m2 308). A browser
  build that ships the YAMLs ships those. For zero Zoom bytes, `expect` can become a sha256
  like `bin133` (small zoomms change).
- The tester zip ships a prebuilt updater (testers only, already in the plan).

Effects pack: **every ZDL carries Zoom code.** Byte search of all 17 `dist/*.ZDL` and the 11
ZDLs in `release/Matujuice_ZoomMS_pack.zip` (2026-10-09):

| Blob in `build/` | Size | What | Found in |
|---|---|---|---|
| `linesel_handlers.bin` | 480 B | stock LineSel on/off + knob 1-2 edit handlers and call stub | every ZDL |
| `divf_rts.bin` | 640 B | `__c6xabi_divf`, TI run-time code taken from a stock ZDL | every ZDL |
| `c6xabi_attributes.bin` | 62 B | stock Exciter's ABI attribute section (data, not code) | every ZDL |
| `TI_section_flags.bin` | 26 B | section flags (data) | every ZDL |
| `air_knob3_edit.bin` | 76 B | stock AIR knob-3 handler | none today (fallback path) |

`linker.py` splices them on purpose (`linker.py:374-378`, `:1645-1651`, clone path
`:770-790`). The pack already generates its own edit handlers for later knobs
(`use_object_edit_handlers`, `linker.py:303-307`). Rebuild plan: generate on/off and knob 1-2
handlers the same way (or use Roman's), take `__divf` from our own source (or drop division,
as the pack rules already ask), write the attribute bytes from the TI spec, then test one
effect on a pedal before rebuilding all. Effects-pack work, not started.

### 5.3 Effect IDs against stock

Stock MS-70CDR 2.10 FS.bin: 137 ZDLs, fxid 8-512. A patch keys an effect by a 32-bit id built
from category (gid) **and** fxid (`build/extract_effect_db.py:37-39`). Every pack effect is
gid 8. Pack numbers equal to a stock number:

| Pack | gid/fxid | Stock with the same fxid | Clash |
|---|---|---|---|
| DualShft | 8/480 | CRN_CHO 6/480 | no: other category, other 32-bit id |
| Sweep | 8/496 | ANA234CH 6/496 | no: same reason (effects pack `docs/STEREO.md:177-178`) |
| DubSiren 485, Choral 486, WaveFold 487, EuGate 488, S.GN_L 489, Scrub 490, DirtBox 491, Breather 493, GRDELAY 495, Looper 497 | 8/... | none | no |

Inside the pack, on purpose: GRDELAY/BarDelay 495, Breather/Pump 493, GRDLOOP/Looper 497
(replacements; the old builds still sit in `dist/`). Probes 498-500 are never released. New
effects take 481-484, 492, 494, 498+ (`NEW-EFFECTS.md:17`); 512 (CRN_TRI) is the only stock
number above 496.

No renumbering needed against stock. On the pedal (Luca, 2026-10-31): Sweep 8/496 and stock
ANA234CH 6/496 load together in one patch, so the OS tells effects apart by gid + fxid.
Left to do: save, power-cycle and reload that patch; ask for gid 8, fxid 480-511 in Modwerk's
ledger (other packs also use group 8, 403-957).

### 5.4 Transport block as a shared contract

- Address and layout match on the MS-70CDR 2.10: `asm/midi_clock/transport.inc` (block
  `0x1181FF00`, magic `0x5A4D5401`, words 0-5), poll site `0xC00C6998`
  (`patches/midi-clock.yaml`). The pack reads it through `src/custom/common/zmt.h` (same
  address, magic and sequence rule): Breather, DualShft, DubSiren, EuGate, Choral, GRDELAY,
  Looper, Scrub, Sweep. The Looper also reads the looper services block `0xC00F3000`, magic
  `0x5A4C5301`.
- Words 6 and 7 (footswitch down, hold claim): planned for v2.0, same magic
  (`joint-plan-v2.0.md` section 1). Not built.
- Proposed contract: the `transport-block.md` table plus words 6/7; the magic stays
  `0x5A4D5401` while words are only added; a layout change bumps the low byte. Readers check
  the magic and treat words they don't know as 0.
- Doc drift (for the coordinator): `transport-block.md` still says "MS-50G 3.10 OS only",
  names the 50G poll site `0xC00CA630` and calls words 6/7 reserved; `zmt.h:4-5` says MS-50G.

### 5.5 Stock fallback per pack effect

| Effect | Needs from MIDISTOMP | On stock firmware |
|---|---|---|
| DualShft, Choral, EuGate, DubSiren, Scrub, Breather, GRDELAY, Sweep | transport block (any MIDISTOMP) | 120 BPM, no clock sync (`zmt.h`) |
| WaveFold, S.GN_L, DirtBox | nothing | same as on MIDISTOMP |
| Looper (GRDLOOP) | transport + looper services (v2.0) | ~10 s mono, every flip a press, LED means nothing (`EFFECTS.md:196-200`); not in a release |
| RISER (planned) | words 6/7 (v2.0) | press-only sweep |
| LOUDER, Gooey meters (planned) | transport + looper services magic | static cover |

DSP: stock "DSP Full" limit 225; v2.0 raises it to 300 (decided). A patch saved above 225 and
then loaded on stock firmware gets effects bypassed to fit (`mixer-mode-m0.md:478-481`). Their
patch check should allow 300 only when the pedal reports DSP 300 (hello feature bit 10),
else 225. Costs are in each `manifest_pedal.json` (`dsp_cost`; Choral 122 is the heavy one).

### 5.6 Testing and recovery (for their write-up)

- Tested: MS-70CDR, MS-60B (v1.2), MS-50G (v1.2, from a Mac) (`README.md:106-108`). Since
  v1.2 every pedal runs the MS-70CDR 2.10 OS and reports model `0x58` after the logo build
  (section 4, point 2).
- Recovery: hold Up and Down while plugging in USB = update mode; flash the stock Zoom
  updater or a MIDISTOMP updater (`docs/safety.md:3-6`). We never write the bootloader, so this
  path survives every MIDISTOMP flash.
- Effects before firmware: a bad ZDL's worst known outcome is a freeze until power-cycle
  (`safety.md:7-9`).
- Before a flash, back up patches; after it, `zoomms identify` and the VERSION menu entry.
- A downgrade or factory reset clears record 50 (mixer + PERFORM settings,
  `mixer-mode-m3-research.md:112-114`).

## Open questions for a call

1. Hello: `7D` manufacturer id and the message layout above, or do they prefer a Zoom-id
   command? Is step A (version in the identity reply) enough for a first release?
2. Which features must the status report (list in answer 1)? Anything else (free patch
   slots, looper state)?
3. Do their per-file USB commands touch records 50 and 51? Can they promise not to?
4. Splitting the "Mixer suite": is one mod fine for v2.0? Is DSP 300 a separate switch?
5. Do they have a wire capture of the Zoom updater flash (`0A`, `02`, `04`) with chunk size
   and acks? Ours: none.
6. How do they decide a pedal is in update mode (identity reply in update mode?), and what
   does their flasher do if the pedal drops out mid-write?
7. Effect ids in the pack against stock ids (Sweep clashes with stock ANA234Cho 496) and a
   range in their ledger (separate plan item).

## Luca's decisions (2026-10-28)

- Hello: **step A in v2.0** (MIDISTOMP version tag in the identity reply), step B (own SysEx
  on 7D with feature bits) after v2.0 if they need it. Firmware: find the 70CDR identity
  template, write `version-2.0.yaml` with the tag; test with and without Effect Manager.
- DSP 300 ships in v2.0.
- Byte 17 / record 50 table: **publish** as `docs/dev/patch-routing-bytes.md` (section 2),
  once the `pages.c`/`mixer.S` comments are fixed.
- Stock flash capture: **yes**, on Luca's pedal before they flash; firmware data bytes
  removed from the log.
- Still open: words 6/7 of the transport block are planned, not built; say "planned".

## Draft replies for Luca

Short, plain, ready to paste. Edit freely.

**1. Detection over MIDI**

> For v2.0 I'll make the normal identity reply tell you it's MIDISTOMP: the four version
> bytes, which say "2.10" on stock, will hold a MIDISTOMP tag with the version (for example
> "V200"). Your identity request works as it is: if the tag is there, it's MIDISTOMP, and you
> know which version. No new SysEx needed. After v2.0, if you need to know which features are
> in the image (looper, mixer, DSP 300 and so on), I can add a small "hello" message of our
> own on manufacturer id 7D that answers with the version and a set of feature bits. Not
> built or tested on a pedal yet; I'll send you the exact bytes once it is.

**2. Routing and PERFORM in a patch**

> Routing is in byte 17 of each of the six 18-byte slot blocks of the packed 122-byte patch.
> Bits 0-1 are the slot's bus (0 PRE, 1 A, 2 B). Bits 2-6 hold a piece of the extra mixer
> settings; that piece belongs to the block position, not to the effect, so keep it where it
> is if you move effects. Bit 7 must stay 0. If you read the patch from the pedal and write it
> back with only your changes, nothing is lost; a zeroed byte 17 just means no routing.
> The other mixer settings and all PERFORM data are not in the patch: they live in the
> pedal's global record 50, matched to the patch by a hash of its six effect ids and its
> name. So renaming a patch or changing, adding, removing or reordering its effects sends it
> back to default mixer and PERFORM settings; params and on/off don't matter. Please never
> write or delete records 50 and 51 with the file commands. I'll send you the full byte table
> as a one-page doc for your editor, and I'll keep that format stable.

**3. Dependencies**

> Independent today: MIDI CC, MIDI clock with the transport block, scroll, boot logo.
> A chain, in this order: CC, clock, MIDI settings, tempo-hold, then the looper services.
> Mixer, PERFORM, MASTER and KALEIDO are one block that shares the menu, the patch hooks and
> record 50; please treat them as one mod ("Mixer suite"). DSP 300 is in v2.0: a single
> 4-byte change, so it can be its own switch. Diag is a test build, not for your base. The
> transport block (0x1181FF00, magic 0x5A4D5401) goes in the base. Two more words are planned
> for v2.0 with the same magic: word 6 = footswitch is down, word 7 = a hold claim for an
> effect; older firmware reads both as 0. The patches must be applied in a fixed order; a
> wrong order fails the build instead of making a bad image. I'll send the address table and
> the dependency list as a file.

**4. Flash steps**

> Your steps match what our updaters do: erase the OS trailer 0x0EF000 (+0x1000) first, boot
> logo block 0x3FD000 only if the logo changed, erase 0x040000 +0xB0000, write Main.bin last;
> never the bootloader at 0x000000 and never the file system at 0x0F0000. Things to add:
> (1) Zoom's updater checks the pedal's model byte before it flashes and refuses others, so
> please check the identity reply (model 0x57, 0x58, 0x5F or 0x61, firmware 2.10) and
> refuse if it does not answer. (2) The boot logo block also holds the pedal's model byte at
> 0x3FFC00; if you write it, change only the logo bytes of the user's own Preset.bin. (3)
> Main.bin must have exactly the stock size, with its tail (version text and the Zoom marker)
> unchanged; I do not know of a checksum, and the Mac updater checks MD5 only for its own
> files. (4) I have no record of the update protocol bytes (your 0A, 02, 04, chunking,
> acks), so I cannot check them. I'll capture a stock Zoom update on my pedal with a MIDI
> monitor and send you the log (firmware data removed) before you flash anything. Please do
> the first write on a pedal that you know enters update mode (Up+Down while plugging in USB),
> with the stock updater ready.

**5. Browser build, Zoom code, effect IDs**

> Building in the browser is easy: every patch already carries its machine code as hex, so no
> TI tools are needed. The browser takes Main.bin (and Preset.bin only for the logo) from the
> user's own Zoom updater, checks it by sha256, adds our patches in order and gets a Main.bin
> of the stock size. Our Python code for that is small and pure Python (it runs in Pyodide),
> or about 250 lines to port to JS. You don't need the updater rewrite or MD5 steps.
> Zoom code: the firmware patches contain no Zoom code except the few stock bytes each hook
> checks before it writes (about 900 bytes); I can change that to a hash. My effects pack does
> contain Zoom code today: the linker copies a stock knob-handler block and a division
> routine into every ZDL. I'll replace them with our own before they go into your base.
> Effect IDs: all my effects are category 8 with ids 480-500. Two numbers equal stock ones
> (480 CRN_CHO, 496 ANA234Cho) but in category 6, and the pedal keys effects by category and
> number, so there is no clash. Could you reserve category 8, ids 480-511 for me in your
> ledger? Without MIDISTOMP my tempo effects run at 120 BPM, the others work the same, and a
> patch above the stock DSP limit of 225 gets effects bypassed, so please check against 300
> only on a pedal that reports MIDISTOMP v2.0.
