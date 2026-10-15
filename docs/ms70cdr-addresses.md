# MS-70CDR 2.10 address map (task T2)

Every MS-50G 3.10 OS value the MIDISTOMP release/v2.0 patches and asm depend on, with its MS-70CDR 2.10 counterpart. Static analysis only (disassembly of both OS images, `tic6x-elf-objdump`); nothing was flashed. No patch or asm file was changed. Plan: `docs/ms70cdr-base.md`; OS comparison: `docs/ms70cdr-port.md`.

**Confidence:** high = identical or near-identical code/data context, the callee/caller pair also located; medium = found but not the same thing as on the 50G, or only checked statically; low = plausible only; not found = no counterpart located (never a guess).

**Counts, OS sites and symbols (all tables except the last):** 209 total: 200 high, 7 medium, 0 low, 2 not found; 180 distinct (50G, 70CDR) pairs (172 high, 6 medium, 0 low, 2 not found). Our own code areas (last table, not OS addresses): 20 total: 5 high, 15 medium, 0 low, 0 not found.

**Global shifts:** DDR code moves from -0x5A0 to +0x720 (no single delta; use the tables); the B14 base is 0xC00EF748 (50G 0xC00EFCC0) and the B14 offsets change by -8 to -20 (table per patch, all taken from aligned loads/stores); strings in 0xC00E9xxx move -0x4A0 (-0x49B after "EXIT"); the whole L2 BSS moves +0x80; the L1D slot-state block and the L2 frame buffer (0x11816800) do not move.

## Needs review (for T2r)

### Blockers (verified, not address uncertainty)

1. **Our L2 area no longer fits.** The 70CDR OS keeps variables in L2 up to 0x1181DF04 (50G: 0x1181DE84), because its audio code section is 0x80 bytes bigger and the L2 BSS follows it. The patches start at 0x1181DEA0, so the first 100 bytes of midi-cc's handler would overwrite OS variables (GPIO bank pointer 0x1181DEF0, McASP base 0x1181DE8C, ...). Starting at 0x1181DF08 leaves 8440 bytes up to 0x11820000, the patches need 8448 (8544 available on the 50G, slack 96). Some code has to move to DDR; the transport block at 0x1181FF00 is read by effects and should keep its address.
2. **Looper draw hook has no counterpart.** `looper.yaml` retargets `callp 0xC00B5794 || or a13,a4` at 0xC00BA9CC. 0xC00B5794 is a setter for `B14+612` (its only reader is the getter 0xC00B5830); both functions and the word are gone in the 70CDR. The nearest hook is the next call in the draw path, 0xC00BB0EC (`callp 0xC00D5720 || ldw b14(708)`, the 50G 0xC00D5B60 call), but `draw_pre` would have to run without the setter. Needs a design decision.

### Medium, low and not found

| Item | Group | Confidence | Why |
|---|---|---|---|
| CC trampoline cave | midi-cc.yaml | medium | The 50G cave (24 zero bytes) has no counterpart: the matching return at 0xC00AF1D4 is followed by only 8 zero bytes. 0xC00BB190 is a spare, valid cave (scan), not the same function. |
| rec_save cave | midi-settings.yaml | medium | No counterpart function end (0xC00C5780 is preceded by a callp). 0xC00C6968 is a spare, valid cave (scan). |
| tempo_draw cave | tempo-hold.yaml | medium | No counterpart function end (the overlay-state wrappers in front of it are mostly gone). 0xC00CB62C is a spare, valid cave (scan). |
| cc trampoline (retarget) | looper.yaml | medium | Same cave as midi-cc (see above). |
| draw hook call site | looper.yaml | not found | Blocker 2 above. |
| LCD_MODE | looper.yaml | not found | Blocker 2 above. |
| LED path (comment) | looper.yaml | medium | Only mentioned in a comment of looper.S; two aligned call sites, body similarity 0.77. |
| block.S regions | looper.yaml | medium | Region boundaries come from the 50G RAM test; the 70CDR layout is unmeasured (T5). |
| test regions | ram-test.yaml | medium | Same: the free-RAM boundaries are not built by any OS constant, so they cannot be derived statically (T5). |
| 15 free-area rows (L2 after the first section, DDR areas, L2 end) | free areas table | medium | Only a static scan (mvk/mvkh constants, image words). The 70CDR .bss/.far is not in the image, so the RAM test (T5) must confirm. |

### Not checked (not addresses)

- Event, screen and menu-row numbers used by the asm (34, 65, 160, 224-231, 69-75, screens 0/1/9/13/14) were not compared; the key loop's 19 callp targets and both screen switch tables line up one to one (17 words each), which suggests they are unchanged.
- Addresses that appear only in asm/yaml comments are not listed (they equal rows that are, unless noted).
- Register conventions and struct layouts behind the stock functions (e.g. FX_PARAM_DESC descriptor +12, ZDL `ctx[1]`) were assumed equal; only addresses were mapped.
- Sites whose yaml `expect:` is another patch's output (CC call site in midi-settings, poll call in ram-test, the four looper trampolines) list the **stock** 70CDR bytes; the `expect` to use is the previous patch's new data.

## Global

| Name | What it is | MS-50G | MS-70CDR | How found | Conf. |
|---|---|---|---|---|---|
| B14 (DP) base | data pointer set in _c_int00 | `0xC00EFCC0` | `0xC00EF748` | _c_int00 (0xC00DDCC0 / 0xC00DD800): mvk -832 / mvkh 0xC00E -> 0xC00EFCC0; mvk -2232 / mvkh -> 0xC00EF748 | high |
| entry point | _c_int00 | `0xC00DDCC0` | `0xC00DD800` | ELF entry address | high |
| model byte | SysEx model id byte (Task_MIDI compare, identity reply); no asm uses it | B14+220 | B14+212 | aligned load votes 212:20 | high |
| OS image end | end of the loaded DDR image (also the end of the cinit tables) | `0xC00F1958` | `0xC00F1364` | last loaded section end; also the constant a cinit-bound function builds (0xC00D81A4 / 0xC00D7D24) | high |
| L2 audio code end | end of the L2 audio code section; everything after it in L2 moves by the same +0x80 | `0x1181BF00` | `0x1181BF80` | sections .s1181ab80 (+0x1380 / +0x1400) | high |

## midi-cc.yaml (asm/midi_cc)

| Name | What it is | MS-50G | MS-70CDR | How found | Conf. |
|---|---|---|---|---|---|
| CC call site | Task_MIDI: callp midi_channel_msg (write) | `0xC00AF088` exp `130ffe1f` | `0xC00AEE6C` exp `1318fe1f` | context match 8 instr before + 5 after; callee c00ae0f8->c00adf20 (2 callers, both located); preceding stb b14(235)->b14(227) identical | high |
| CC trampoline cave | trampoline cave (16 zero bytes after a return) | `0xC00AF408` | `0xC00BB190` | counterpart return (bnop b3,5 at 0xC00AF1D4) is followed by only 8 zero bytes; no 24-byte cave there. Picked a spare cave: zero run 0xC00BB190-0xC00BB19F after bnop b3,5 at 0xC00BB18C, not a branch target, plain packet (scan) | medium |
| STOCK_CHANNEL_MSG | stock midi_channel_msg (step.S, handler tail call) | `0xC00AE0F8` | `0xC00ADF20` | function match, first-60-instr similarity 1.00, 2 callers vs 2, 2 aligned call sites vote for it | high |
| FX_PARAM_DESC | (slot, param) -> descriptor | `0xC00B07AC` | `0xC00B056C` | function match, first-60-instr similarity 1.00, 21 callers vs 21, 20 aligned call sites vote for it | high |
| FX_SET_PARAM | set an effect parameter | `0xC00BAEE0` | `0xC00BB600` | function match, first-60-instr similarity 1.00, 7 callers vs 7, 7 aligned call sites vote for it | high |
| SEM_PEND | Semaphore_pend wrapper | `0xC00C7C60` | `0xC00C7EE0` | function match, first-60-instr similarity 1.00, 74 callers vs 74, 68 aligned call sites vote for it | high |
| SEM_POST | Semaphore_post wrapper | `0xC00D70C0` | `0xC00D6B00` | function match, first-60-instr similarity 1.00, 91 callers vs 91, 86 aligned call sites vote for it | high |
| UI_REFRESH | UI refresh after a CC knob change | `0xC00ACEA4` | `0xC00ACD84` | function match, first-60-instr similarity 0.75, 2 callers vs 2, 2 aligned call sites vote for it; same callees (IS_DIRTY, c00ba128->c00ba808), 2 callers aligned | high |
| EVENT_POST | (event, mask) UI event post | `0xC00CC680` | `0xC00CBF40` | function match, first-60-instr similarity 1.00, 16 callers vs 13, 10 aligned call sites vote for it; 50G has 16 callers, 70CDR 13 (some callers removed) | high |
| SEM_HANDLE_OFS | semaphore handle used by SEM_PEND/POST | B14+784 | B14+764 | aligned ldw/stw votes 764:39; same "callp SEM_POST \|\| ldw b14(.),a4" pattern | high |
| UI_EVENT_OFS | UI task event word | B14+676 | B14+656 | aligned load/store votes 656:9, 692:1 (the 692 vote is a one-off alignment error) | high |
| CUR_PATCH | current patch 0-49 (step.S) | B14+332 | B14+324 | aligned load/store votes 324:30; same use before the tuner softkeys ldw b14(324) | high |

## midi-clock.yaml (asm/midi_clock)

| Name | What it is | MS-50G | MS-70CDR | How found | Conf. |
|---|---|---|---|---|---|
| Task_MIDI loop hook | end of Task_MIDI byte loop: ldw b14(224),b0 (write) | `0xC00AF0F8` exp `6e380000` | `0xC00AEEE0` exp `6e360000` | both are the target of the loop-closing bnop (0xC00AF0F8 / 0xC00AEEE0); same 12-instr body (add 1, shr 11, shru 20, andn 4095 ring wrap) ; only the b14 disp changes 224->216 | high |
| clock trampoline cave | trampoline cave (16 zero bytes after a return) | `0xC00A1A50` | `0xC00A1A50` | same address: 16 zero bytes after bnop b3,5 at 0xC00A1A4C in both (plain packet, no target; scan) | high |
| poll call site | Task_SwitchNrmlSpdRead: callp Clock_getTicks (write) | `0xC00CA630` exp `12a82910` | `0xC00C6998` exp `12943010` | context match: prologue mvk 16,a4; callp sleep(c00cf000->c00cebc0); callp getTicks; then mvk -8308 / mvkh (SW_STATE base) loop, identical for 40 instr; getTicks c00df360->c00dee20 (40 votes) | high |
| poll trampoline cave | trampoline cave (16 zero bytes after a return) | `0xC00C8050` | `0xC00C82D0` | zero run after the return bnop b3,5 at 0xC00C82CC (same function as 0xC00C804C by alignment, 16 bytes both); plain packet, no target (scan) | high |
| DIVU | unsigned divide a4 / b4 (RTS helper) | `0xC00DCA20` | `0xC00DC560` | function match, first-60-instr similarity 1.00, 43 callers vs 43, 42 aligned call sites vote for it | high |
| CLOCK_GETTICKS | SYS/BIOS Clock_getTicks, 1 ms | `0xC00DF360` | `0xC00DEE20` | function match, first-60-instr similarity 1.00, 47 callers vs 47, 40 aligned call sites vote for it | high |
| TEMPO_VALUE | patch TEMPO, int BPM | `0xC009C06C` | `0xC009C06C` | mvk/mvkh constant built identically in 3 aligned sites (same address, data below the image shift) | high |
| SET_SETTING | (setting, value, notify) | `0xC00CAC64` | `0xC00CAB44` | function match, first-60-instr similarity 1.00, 2 callers vs 2, 2 aligned call sites vote for it | high |
| TEMPO_SETTING | setting struct: value ptr, min 40, max 250 | `0xC00EE3D8` | `0xC00EDEE0` | same use: mvk 250,b2 ; mvk lo ; callp SET_SETTING(…,1) in the tap-tempo clamp (0xC00B9EAC / 0xC00BA58C); BSS/cinit data, content not in image | high |
| EVENT_POST | (event, mask) UI event post (also midi-cc) | `0xC00CC680` | `0xC00CBF40` | function match, first-60-instr similarity 1.00, 16 callers vs 13, 10 aligned call sites vote for it; see midi-cc | high |
| read index (hook) | Task_MIDI receive ring read index (ldw b14(224), also the replaced instruction) | B14+224 | B14+216 | aligned votes 216:3; manual: ldw b14(216) at 0xC00AEEE0 | high |
| byte just taken | clock.S: ldbu b14(234) | B14+234 | B14+226 | stb a0,*+b14(234) at 0xC00AEF04 aligns with stb a0,*+b14(226) at 0xC00AECEC (same function, same neighbours 233->225, 235->227, 236->228, all -8) | high |
| UI_EVENT_OFS | UI task event word (poll.S) | B14+676 | B14+656 | see midi-cc | high |

## midi-settings.yaml (asm/midi_settings)

| Name | What it is | MS-50G | MS-70CDR | How found | Conf. |
|---|---|---|---|---|---|
| screen 1 key table entry | switch table word, SETTINGS key handler -> settings_keys (write) | `0xC00EF300` exp `04840ac0` | `0xC00EEFA0` exp `b4830ac0` | whole 17-word key switch table found: same pattern (entry 1 = callp LIST_KEYS 0xC00A7904 stub, 4 words pointing at the default menu-keys stub); screen 1 = table base | high |
| screen 1 draw table entry | switch table word, SETTINGS draw -> settings_draw (write) | `0xC00EF2BC` exp `64940ac0` | `0xC00EEBB4` exp `00940ac0` | whole 17-word draw switch table found by its pointers (a9400..a93b0 = the 50G a9464..a9414 callp stubs); entry 1 = table base | high |
| screen 14 key table entry | switch table word (unused screen) -> midi_keys (write) | `0xC00EF334` exp `60830ac0` | `0xC00EEFD4` exp `10830ac0` | key table base + 0x34; value is the menu-keys default stub (0xC00A8310), same as the 50G (0xC00A8360) | high |
| screen 14 draw table entry | switch table word (unused screen) -> midi_draw (write) | `0xC00EF2F0` exp `00940ac0` | `0xC00EEBE8` exp `98930ac0` | draw table base + 0x34; value is the menu-draw default stub (0xC00A9398) | high |
| screen 13 key table entry | switch table word (unused screen) -> opt_keys (write) | `0xC00EF330` exp `60830ac0` | `0xC00EEFD0` exp `10830ac0` | key table base + 0x30; default stub | high |
| screen 13 draw table entry | switch table word (unused screen) -> opt_draw (write) | `0xC00EF2EC` exp `00940ac0` | `0xC00EEBE4` exp `98930ac0` | draw table base + 0x30; default stub | high |
| menu keys stub | default stub: callp STOCK_MENU_KEYS (write) | `0xC00A8360` exp `93cafe1f` | `0xC00A8310` exp `93d6fe1f` | stub block of 3 callp+lddw+bnop: callp c00a79b4 is the first stub in both (the automatic alignment first landed on the next stub, 0xC00A8320; corrected by hand); the table entry for screens 13/14 points here | high |
| menu_keys cave | trampoline cave (16 zero bytes after a return) | `0xC00BEDF0` | `0xC00BEC90` | zero run after return bnop b3,5 at 0xC00BEC8C (alignment of the 50G cave 0xC00BEDF0), 16 bytes, plain packet, no target (scan) | high |
| menu draw stub | default stub: callp 0xC00A7460 (write) | `0xC00A9400` exp `120cfc1f` | `0xC00A9398` exp `121cfc1f` | only caller of c00a7460 (1 caller in each OS); it is the default draw stub of the draw table (entries at 0xC00EEBDC, E4, E8, EC) | high |
| menu_draw cave | trampoline cave (16 zero bytes after a return) | `0xC00C2164` | `0xC00C1FC4` | zero run (28 bytes) after bnop b3,5 at 0xC00C1FC0; plain packet, no target (scan) | high |
| version EXIT | compact mvk .L2 3,b4 -> 4 (write) | `0xC00A7638` exp `2766` | `0xC00A7638` exp `2766` | same address: code is byte-identical for 13948 instr before and 100 after in the aligned diff | high |
| pack call | settings save: callp pack (write) | `0xC00B9CF4` exp `93f13310` | `0xC00BA3D4` exp `938d3210` | 0x10 before SAVE_SETTINGS in both (0xC00B9D04 / 0xC00BA3E4); callee c00d3c6c->c00d382c; 3 callers each | high |
| pack cave | trampoline cave (16 zero bytes after a return) | `0xC00B97E8` | `0xC00B9EC8` | zero run (24 bytes) after bnop b3,5 at 0xC00B9EC4; plain packet, no target (scan) | high |
| unpack call | settings load at boot: callp unpack (write) | `0xC00BA09C` exp `13603310` | `0xC00BA77C` exp `13fc3110` | 0x398 after SAVE_SETTINGS in both; callee c00d3b80->c00d3740 | high |
| unpack cave | trampoline cave (16 zero bytes after a return) | `0xC00BDB44` | `0xC00BD9E4` | zero run (28 bytes) after bnop b3,5 at 0xC00BD9E0; plain packet, no target (scan) | high |
| rec_load call | record 51 load at boot: callp REC_LOAD (write) | `0xC00B8DD4` exp `92f1f71f` | `0xC00B8B14` exp `92f5f71f` | caller context ratio 1.0 (28 instr); callee c00b4d4c->c00b4aac | high |
| rec_load cave | trampoline cave (16 zero bytes after a return) | `0xC00C4AAC` | `0xC00C492C` | zero run (20 bytes) after bnop b3,5 at 0xC00C4928; plain packet, no target (scan) | high |
| rec_save call | record 51 save: callp REC_SAVE (write) | `0xC00B86E0` exp `93b6f81f` | `0xC00B8420` exp `93baf81f` | 0x10 after SAVE_LAST_PATCH (0xC00B86D0 / 0xC00B8410) in both; callee c00b4c94->c00b49f4 | high |
| rec_save cave | trampoline cave (16 zero bytes after a return) | `0xC00C5D88` | `0xC00C6968` | counterpart function end not present in the same place (0xC00C5780 is preceded by a callp, not a return). Picked a spare cave: 24 zero bytes after bnop b3,5 at 0xC00C6964; plain packet, no target (scan) | medium |
| CC call site (gate) | Task_MIDI CC call site (same as midi-cc) (write) | `0xC00AF088` exp `130ffe1f` | `0xC00AEE6C` exp `1318fe1f` | see midi-cc | high |
| PC call site (gate) | Task_MIDI PC call site: callp midi_channel_msg (write) | `0xC00AF0AC` exp `130bfe1f` | `0xC00AEE90` exp `1314fe1f` | second caller of c00ae0f8->c00adf20; context ratio 1.0 against 0xC00AEE90 (the other caller scores 0.6) | high |
| gate cave | trampoline cave (16 zero bytes after a return) | `0xC00B2FAC` | `0xC00B2D0C` | zero run (20 bytes) after bnop b3,5 at 0xC00B2D08; plain packet, no target (scan) | high |
| SET_SCREEN | (screen, row) | `0xC00A75E0` | `0xC00A75E0` | function match, first-60-instr similarity 1.00, 32 callers vs 32, 31 aligned call sites vote for it | high |
| LIST_INDEX | -> row + top of the list | `0xC00A7040` | `0xC00A7040` | function match, first-60-instr similarity 1.00, 8 callers vs 8, 8 aligned call sites vote for it | high |
| LIST_SCROLL | (delta, rows) | `0xC00A72D4` | `0xC00A72D4` | function match, first-60-instr similarity 1.00, 3 callers vs 3, 3 aligned call sites vote for it | high |
| STOCK_MENU_KEYS | menu key handler (target of the stub) | `0xC00A79B4` | `0xC00A79B4` | function match, first-60-instr similarity 0.98, 1 callers vs 1; same address; only caller is the stub | high |
| STOCK_LIST_KEYS | settings list key handler | `0xC00A7904` | `0xC00A7904` | function match, first-60-instr similarity 1.00, 1 callers vs 1; same address; only caller is the table-1 entry (0xC00A83B4 in the 70CDR) | high |
| KEY_DONE | key dispatcher epilogue (branch target) | `0xC00A840C` | `0xC00A83C0` | function match, first-60-instr similarity 1.00, 15 callers vs 15, 12 aligned call sites vote for it; epilogue ldw *++b15(24),b3 ; nop 4 ; bnop b3,5; all key-table entries bnop to it (15 branches each) | high |
| DRAW_DONE | draw dispatcher epilogue (branch target) | `0xC00A9468` | `0xC00A9404` | function match, first-60-instr similarity 0.78, 16 callers vs 16, 15 aligned call sites vote for it; epilogue ldw *++b15(8),b3 ; nop 4 ; bnop b3,5; draw-table entries bnop to it (16 branches each) | high |
| DRAW_TITLE | (string) screen title | `0xC00A7378` | `0xC00A7378` | function match, first-60-instr similarity 1.00, 19 callers vs 19, 18 aligned call sites vote for it | high |
| DRAW_TEXT | (0, string, x, y) | `0xC009FCE0` | `0xC009FCE0` | function match, first-60-instr similarity 1.00, 9 callers vs 9, 8 aligned call sites vote for it | high |
| DRAW_ICON | (0, x, y, w, h, bitmap) | `0xC009F9B0` | `0xC009F9B0` | function match, first-60-instr similarity 1.00, 65 callers vs 65, 64 aligned call sites vote for it | high |
| DRAW_BOX | (0, x, y, x2, y2, mode) | `0xC00A0144` | `0xC00A0144` | function match, first-60-instr similarity 1.00, 34 callers vs 34, 30 aligned call sites vote for it | high |
| HILITE | (row, narrow for a scrollbar) | `0xC00A73A4` | `0xC00A73A4` | function match, first-60-instr similarity 1.00, 8 callers vs 8, 7 aligned call sites vote for it | high |
| SCROLLBAR | (top, rows) | `0xC00A88CC` | `0xC00A8874` | function match, first-60-instr similarity 0.98, 1 callers vs 1, 1 aligned call sites vote for it; entry is the second "callp e14c0" (prologue helper) after the epilogue call, same as 50G; caller is the single screen-1 draw (0xC00A88F8 -> 0xC00A88A4) | high |
| DRAW_ARROWS | (0) | `0xC00A7400` | `0xC00A7400` | function match, first-60-instr similarity 1.00, 14 callers vs 14, 13 aligned call sites vote for it | high |
| SOFTKEY | (knob, string, 0) | `0xC009F8F0` | `0xC009F8F0` | function match, first-60-instr similarity 1.00, 49 callers vs 49, 42 aligned call sites vote for it | high |
| BATTERY_LEVEL | -> 0..4, 5+ = no battery icon | `0xC00D7820` | `0xC00D7260` | function match, first-60-instr similarity 1.00, 2 callers vs 2, 2 aligned call sites vote for it | high |
| BATTERY_ICONS | table of icon pointers (menu draw) | `0xC00EEFB8` | `0xC00EEA50` | the single mvk/mvkh use in the menu draw (0xC00A7494 / 0xC00A7494) with identical surrounding instr; BSS/cinit data | high |
| SAVE_SETTINGS | (words), writes record 50 | `0xC00B9D04` | `0xC00BA3E4` | function match, first-60-instr similarity 1.00, 5 callers vs 5, 5 aligned call sites vote for it | high |
| CLAMP | (value, min, max) | `0xC00A766C` | `0xC00A766C` | function match, first-60-instr similarity 1.00, 12 callers vs 12, 11 aligned call sites vote for it | high |
| PACK | settings pack (target of the pack call) | `0xC00D3C6C` | `0xC00D382C` | function match, first-60-instr similarity 1.00, 3 callers vs 3, 3 aligned call sites vote for it | high |
| UNPACK | settings unpack | `0xC00D3B80` | `0xC00D3740` | function match, first-60-instr similarity 1.00, 3 callers vs 3, 3 aligned call sites vote for it | high |
| REC_SAVE | (record, buffer) | `0xC00B4C94` | `0xC00B49F4` | function match, first-60-instr similarity 1.00, 3 callers vs 3, 3 aligned call sites vote for it | high |
| REC_LOAD | (record, buffer) -> 0 = ok | `0xC00B4D4C` | `0xC00B4AAC` | function match, first-60-instr similarity 1.00, 6 callers vs 6, 6 aligned call sites vote for it | high |
| SAVE_LAST_PATCH | (patch), writes record 51 | `0xC00B86D0` | `0xC00B8410` | function match, first-60-instr similarity 1.00, 3 callers vs 3, 2 aligned call sites vote for it; 50G 3 callers vs 70CDR 3 | high |
| STOCK_CHANNEL_MSG | stock midi_channel_msg | `0xC00AE0F8` | `0xC00ADF20` | function match, first-60-instr similarity 1.00, 2 callers vs 2, 2 aligned call sites vote for it | high |
| SETTINGS_WORDS | settings words array | `0xC009D8F8` | `0xC009D8F8` | 13 aligned mvk/mvkh sites build the same value | high |
| HOLD_WORD | stock HOLD FOR: 0 tuner, 1 tempo | `0xC009D920` | `0xC009D920` | 2 aligned sites (HOLD FOR getter/setter 0xC00B9BA8, 0xC00B9CE0 -> 70CDR same lo/hi) | high |
| STR_MENU | string "MENU" | `0xC00E958C` | `0xC00E90F1` | string match in both images, same neighbouring strings | high |
| STR_SETTINGS | string "SETTINGS" | `0xC00E94A4` | `0xC00E9004` | string match in both images, same neighbouring strings | high |
| STR_ENTER | string "ENTER" | `0xC00E9591` | `0xC00E90F6` | string match in both images, same neighbouring strings | high |
| STR_EXIT | string "EXIT" | `0xC00E9597` | `0xC00E90FC` | string match in both images, same neighbouring strings | high |
| STR_BLANK | empty string (menu_names blank softkey) | `0xC00E959C` | `0xC00E9101` | const vote 11 aligned sites; sits right after "EXIT" like the 50G | high |
| OFF_ON | pointer pair "OFF","ON" (followed by 1, 2) | `0xC00ED238` | `0xC00ECD38` | table content equal with pointers masked; 70CDR pointers read back as "OFF","ON" (0xC00E907D/81) | high |
| menu name 0 | menu_names[0] string "DELETE EFFECT UNIT" | `0xC00E9484` | `0xC00E8FE4` | string match in both images, same neighbouring strings | high |
| menu name 1 | menu_names[1] string "EFFECT CHAIN" | `0xC00E9497` | `0xC00E8FF7` | string match in both images, same neighbouring strings | high |
| menu name 4 / VERSION | menu_names[4] string "VERSION" | `0xC00E94AD` | `0xC00E900D` | string match in both images, same neighbouring strings | high |
| settings name 1 | settings_names[1] string "BYPASS/MUTE TUNER" | `0xC00E94C8` | `0xC00E9028` | string match in both images, same neighbouring strings | high |
| settings name 2 | settings_names[2] string "POWER MANAGEMENT" | `0xC00E94DA` | `0xC00E903A` | string match in both images, same neighbouring strings | high |
| settings name 3 | settings_names[3] string "AUTO SAVE" | `0xC00E94EB` | `0xC00E904B` | string match in both images, same neighbouring strings | high |
| settings name 4 | settings_names[4] string "BATTERY TYPE" | `0xC00E94F5` | `0xC00E9055` | string match in both images, same neighbouring strings | high |
| settings name 5 | settings_names[5] string "LCD BACKLIGHT" | `0xC00E9502` | `0xC00E9062` | string match in both images, same neighbouring strings | high |
| settings name 6 | settings_names[6] string "LCD CONTRAST" | `0xC00E9510` | `0xC00E9070` | string match in both images, same neighbouring strings | high |
| hold name TUNER | hold_names[0] string "TUNER" | `0xC00E953F` | `0xC00E909F` | string match in both images, same neighbouring strings | high |
| hold name TEMPO | hold_names[1] (the tap screen title) string "TEMPO" | `0xC00EB13F` | `0xC00EB0DC` | string match; the second "TEMPO" in the 70CDR (0xC00EB5D4) has other neighbours; 0xC00EB0DC sits between "ON/%s" and "ACTIVE/PASSIVE" like the 50G | high |
| list top | settings list scroll top (b14(372)) | B14+372 | B14+360 | aligned load/store votes 360:21 | high |
| list row | highlighted screen row (b14(368)) | B14+368 | B14+356 | aligned load/store votes 356:25 | high |
| CUR_PATCH | current patch | B14+332 | B14+324 | see midi-cc | high |

## tempo-hold.yaml (asm/tempo_hold)

| Name | What it is | MS-50G | MS-70CDR | How found | Conf. |
|---|---|---|---|---|---|
| HOLD FOR (press) | footswitch press, tempo screen open: callp HOLD FOR getter (write) | `0xC00ACBD8` exp `12231a10` | `0xC00ACAB8` exp `12231b10` | caller of c00b9cd8->c00ba3b8 with ratio 1.0 (28 instr); order inside the footswitch handler unchanged | high |
| HOLD FOR (release) | footswitch release, tempo screen open: callp HOLD FOR getter (write) | `0xC00ACA40` exp `12531a10` | `0xC00AC920` exp `12531b10` | caller of the same getter, ratio 1.0 | high |
| tempo timeout | compact set a6,0,30,a6 ("forever") in the overlay state-2 call (write) | `0xC00CB96C` exp `891e1803` | `0xC00CCCC8` exp `891e1803` | same sequence "mvk 0,a6 ; callp OVL_SET \|\| mvk 0,a4 \|\| set a6,0,30,a6 \|\| mvk 2,b4" ; bytes identical (891e1803). The 50G has four such sets (states 6,8,7,2), the 70CDR only this one | high |
| tempo box | data: x,y,w,h halfwords of the tempo box (write) | `0xC00EBB64` exp `04001d0078001a00` | `0xC00EB700` exp `04001d0078001a00` | 8 bytes unique in both images; the surrounding 48 bytes are identical | high |
| softkey label TAP | mvk lo16 of the "TAP" string ptr (write) | `0xC00CB3C8` exp `aae36602` | `0xC00CB2A8` exp `aa676402` | lo 16 bits change (0xCDC7 -> 0xC8CF = "TAP" at 0xC00EC8CF); opcode otherwise identical; run of 881 aligned instr around | high |
| overlay draw call | callp TEMPO_BOX in the draw for states 2/5 (write) | `0xC00BA930` exp `1365e01f` | `0xC00BB050` exp `135adf1f` | only caller of TEMPO_BOX (c00aac48->c00aab10) in both | high |
| tempo_draw cave | trampoline cave (16 zero bytes after a return) | `0xC00CBA70` | `0xC00CB62C` | the 50G function before it (overlay-state wrappers; 3 of the 4 set-a6 siblings are gone in the 70CDR) has no counterpart, so there is no cave there. Picked a spare cave: 20 zero bytes after bnop b3,5 at 0xC00CB628; plain packet, no target (scan) | medium |
| knob call | key loop: callp STOCK_KNOB (write) | `0xC00AD10C` exp `9322fe1f` | `0xC00ACFE8` exp `1321fe1f` | key-loop callp sequence matches 19/19 in order (table below); callee c00ac214->c00ac0e8 | high |
| knob cave | trampoline cave (16 zero bytes after a return) | `0xC00D1BB0` | `0xC00D1770` | zero run after bnop b3,5 at 0xC00D176C, 16 bytes, plain packet, no target (scan) | high |
| tap call (knob press) | callp STOCK_TAP (write) | `0xC00AC9F0` exp `12791a10` | `0xC00AC8D0` exp `12791b10` | caller of c00b9da8->c00ba488 ratio 1.0 | high |
| tap call (release) | callp STOCK_TAP (write) | `0xC00ACA50` exp `126d1a10` | `0xC00AC930` exp `126d1b10` | caller of c00b9da8->c00ba488 ratio 1.0 | high |
| tap cave | trampoline cave (16 zero bytes after a return) | `0xC00D2030` | `0xC00D1BF0` | zero run after bnop b3,5 at 0xC00D1BEC, 16 bytes, plain packet, no target (scan) | high |
| toggle call | footswitch press flip: callp TOGGLE (write) | `0xC00ACC2C` exp `9238fe1f` | `0xC00ACB0C` exp `1237fe1f` | caller of c00abde4->c00abcb8 ratio 1.0 | high |
| toggle cave | trampoline cave (16 zero bytes after a return) | `0xC00D3370` | `0xC00D2F30` | zero run after bnop b3,5 at 0xC00D2F2C, 16 bytes, plain packet, no target (scan) | high |
| release call | key loop: callp STOCK_RELEASE (write) | `0xC00AD2D8` exp `93ebfe1f` | `0xC00AD1B8` exp `93ebfe1f` | key-loop callp sequence (19/19); callee c00aca1c->c00ac8fc | high |
| release cave | trampoline cave (16 zero bytes after a return) | `0xC00D3F30` | `0xC00D3AF0` | zero run after bnop b3,5 at 0xC00D3AEC, 16 bytes, plain packet, no target (scan) | high |
| type hold 229 | key loop: callp STOCK_TYPE_HOLD, event 229 (write) | `0xC00AD064` exp `1364fd1f` | `0xC00ACF40` exp `1363fd1f` | key-loop callp sequence; first of the two calls to c00abb80->c00aba58 | high |
| type hold 228 | key loop: callp STOCK_TYPE_HOLD, event 228 (write) | `0xC00AD090` exp `1360fd1f` | `0xC00ACF6C` exp `135ffd1f` | key-loop callp sequence; second call to c00aba58 | high |
| cursor hold | key loop: callp STOCK_CURSOR_HOLD, events 230/231 (write) | `0xC00AD034` exp `134efd1f` | `0xC00ACF10` exp `134dfd1f` | key-loop callp sequence; callee c00aba90->c00ab968 | high |
| combo cave | trampoline cave (16 zero bytes after a return) | `0xC00D44D0` | `0xC00D4090` | zero run after bnop b3,5 at 0xC00D408C, 16 bytes, plain packet, no target (scan) | high |
| hold call | key loop: callp STOCK_HOLD, event 224 (write) | `0xC00AD0E4` exp `13affd1f` | `0xC00ACFC0` exp `13aefd1f` | key-loop callp sequence; callee c00abe58->c00abd30 (body ratio only 0.73, but identical callee set and one caller each) | high |
| hold cave | trampoline cave (16 zero bytes after a return) | `0xC00D46B0` | `0xC00D4270` | zero run after bnop b3,5 at 0xC00D426C, 16 bytes, plain packet, no target (scan) | high |
| dirty call | AUTO SAVE changed check: callp IS_DIRTY (write) | `0xC00ACCE4` exp `92621710` | `0xC00ACBC4` exp `922e1710` | caller of c00b87f4->c00b8534 ratio 1.0 | high |
| dirty cave | trampoline cave (16 zero bytes after a return) | `0xC00D4BF0` | `0xC00D47B0` | zero run after bnop b3,5 at 0xC00D47AC, 16 bytes, plain packet, no target (scan) | high |
| type release 69 | key loop: callp STOCK_TYPE_REL (write) | `0xC00AD1F8` exp `9372fe1f` | `0xC00AD0D8` exp `1372fe1f` | key-loop callp sequence; second call to c00ac574->c00ac450 | high |
| type release 71 | key loop: callp STOCK_TYPE_REL (write) | `0xC00AD1A8` exp `937afe1f` | `0xC00AD088` exp `137afe1f` | key-loop callp sequence; first call to c00ac450 | high |
| cursor release | key loop: callp STOCK_CURSOR_REL, events 73/75 (write) | `0xC00AD158` exp `935efe1f` | `0xC00AD038` exp `935dfe1f` | key-loop callp sequence (the 70CDR callee is 0xC00AC30C); consistent -0x128 shift against the neighbouring 0xC00AC3B4->0xC00AC28C | high |
| swallow cave | trampoline cave (16 zero bytes after a return) | `0xC00D8B70` | `0xC00D86F0` | zero run after bnop b3,5 at 0xC00D86EC, 16 bytes, plain packet, no target (scan) | high |
| middle knob release | key loop: callp STOCK_MIDDLE, event 65 (write) | `0xC00AD290` exp `13c6fe1f` | `0xC00AD170` exp `13c6fe1f` | key-loop callp sequence; callee c00ac8b0->c00ac790 | high |
| tuner_exit cave | trampoline cave (16 zero bytes after a return) | `0xC00D9190` | `0xC00D8D10` | zero run after bnop b3,5 at 0xC00D8D0C, 16 bytes, plain packet, no target (scan) | high |
| tuner softkey call | tuner screen: callp softkey(1, blank label) (write) | `0xC00BA5E8` exp `1362ca1f` | `0xC00BAD40` exp `1376c91f` | the 3 softkey calls (knobs 0,1,2) are in the same order; knob 1 (mvk 1,a4 \|\| mv a10,b4) is 0xC00BAD40 | high |
| tuner_label cave | trampoline cave (16 zero bytes after a return) | `0xC00DAFD0` | `0xC00DAA30` | zero run after bnop b3,5 at 0xC00DAA2C; 16 bytes, plain packet, no target (scan). Same offset in the fetch packet (+0x10), so the hand-coded "b SOFTKEY" only needs the new packet base 0xC00DAA20 | high |
| OVL_GET | (0) -> overlay state, -1 = none | `0xC00CBA10` | `0xC00CCD6C` | function match, first-60-instr similarity 0.35, 15 callers vs 12, 12 aligned call sites vote for it; body identical for all 17 instr (callee addresses shifted); the 0.35 similarity is a disassembler artefact (stray nop suffixes) | high |
| OVL_SET | (0, state, ms) overlay set | `0xC00CB8A4` | `0xC00CCC84` | function match, first-60-instr similarity 0.53, 10 callers vs 7; same body (callp e14c0 ; mv b4,a11 ; stw *+a5[a4] with the same table base -8280); the 70CDR has 7 callers vs 10 | high |
| TEMPO_BOX | (0, tempo) draw the tempo box | `0xC00AAC48` | `0xC00AAB10` | function match, first-60-instr similarity 0.83, 1 callers vs 1, 1 aligned call sites vote for it; body ratio 0.83 (first 60 instr), one caller in each OS, identical callee list | high |
| DRAW_TEXT | (0, string, x, y) | `0xC009FCE0` | `0xC009FCE0` | function match, first-60-instr similarity 1.00, 9 callers vs 9, 8 aligned call sites vote for it | high |
| CLAMP | (value, min, max) | `0xC00A766C` | `0xC00A766C` | function match, first-60-instr similarity 1.00, 12 callers vs 12, 11 aligned call sites vote for it | high |
| TOGGLE | (slot) flip effect on/off | `0xC00ABDE4` | `0xC00ABCB8` | function match, first-60-instr similarity 0.97, 3 callers vs 3, 3 aligned call sites vote for it | high |
| IS_DIRTY | patch-changed check | `0xC00B87F4` | `0xC00B8534` | function match, first-60-instr similarity 1.00, 5 callers vs 5, 5 aligned call sites vote for it | high |
| STOCK_KNOB | knob turn handler | `0xC00AC214` | `0xC00AC0E8` | function match, first-60-instr similarity 0.78, 1 callers vs 1; single caller in the key loop (confirmed by call order); body ratio 0.78 | high |
| STOCK_TAP | tap tempo | `0xC00B9DA8` | `0xC00BA488` | function match, first-60-instr similarity 1.00, 3 callers vs 3, 3 aligned call sites vote for it | high |
| STOCK_HOLD | footswitch hold | `0xC00ABE58` | `0xC00ABD30` | function match, first-60-instr similarity 0.73, 1 callers vs 1; single caller (key loop), same callee set | high |
| STOCK_RELEASE | footswitch release | `0xC00ACA1C` | `0xC00AC8FC` | function match, first-60-instr similarity 1.00, 1 callers vs 1, 1 aligned call sites vote for it | high |
| STOCK_TYPE_HOLD | type key hold | `0xC00ABB80` | `0xC00ABA58` | function match, first-60-instr similarity 1.00, 2 callers vs 2; 2 callers (events 228/229) match in order | high |
| STOCK_CURSOR_HOLD | cursor key hold | `0xC00ABA90` | `0xC00AB968` | function match, first-60-instr similarity 0.98, 1 callers vs 1 | high |
| STOCK_TYPE_REL | type key release | `0xC00AC574` | `0xC00AC450` | function match, first-60-instr similarity 0.92, 2 callers vs 2, 2 aligned call sites vote for it | high |
| STOCK_CURSOR_REL | cursor key release | `0xC00AC434` | `0xC00AC30C` | function match, 1 callers vs 1; single caller in key-loop order; 70CDR entry is 0xC00AC30C (not ...308) | high |
| HOLD FOR getter | HOLD FOR getter (callee of the two press/release sites) | `0xC00B9CD8` | `0xC00BA3B8` | function match, first-60-instr similarity 1.00, 8 callers vs 8, 7 aligned call sites vote for it | high |
| STOCK_MIDDLE | middle knob release (tuner_exit) | `0xC00AC8B0` | `0xC00AC790` | function match, first-60-instr similarity 1.00, 1 callers vs 1, 1 aligned call sites vote for it | high |
| FOOT_PRESS | footswitch press handler (tuner_exit) | `0xC00ACAB0` | `0xC00AC990` | function match, first-60-instr similarity 1.00, 1 callers vs 1, 1 aligned call sites vote for it | high |
| SOFTKEY | (knob, string, 0) | `0xC009F8F0` | `0xC009F8F0` | function match, first-60-instr similarity 1.00, 49 callers vs 49, 42 aligned call sites vote for it | high |
| EXIT label | EXIT string used by tuner_label string "EXIT" | `0xC00E9597` | `0xC00E90FC` | string match in both images, same neighbouring strings | high |
| TAP string | old softkey label string "TAP" | `0xC00ECDC7` | `0xC00EC8CF` | string match in both images, same neighbouring strings | high |
| TEMPO string | tempo box title (new softkey label) string "TEMPO" | `0xC00EB13F` | `0xC00EB0DC` | string match in both images, same neighbouring strings | high |
| HOLD_WORD | stock HOLD FOR: 0 tuner, 1 tempo | `0xC009D920` | `0xC009D920` | see midi-settings | high |
| SW_STATE | 7 footswitch/key states, bit i clear = down | `0xC009DF90` | `0xC009DF90` | reached as base 0xC009DF8C +4 in Task_SwitchNrmlSpdRead in both (mvk -8308 / mvkh, then add 4); not built as a constant | high |
| MODE | 0 = play (hold.S, tuner_exit.S) | B14+328 | B14+320 | aligned votes 320:84, 340:1 | high |
| PENDING | prompt over the Effect View | B14+348 | B14+340 | aligned votes 340:18 | high |
| HOLD_FIRED | 1 = the release does not tap | B14+360 | B14+348 | aligned votes 348:3; manual: "mvk 1,b0 ; stw b0,b14(360)" at 0xC00ABE50 = same at 0xC00ABD28 b14(348) | high |

Key loop (Task key handler) callp sequence, one to one in both OSes: this is how the ten key-loop sites above were paired.

| # | MS-50G site -> callee | MS-70CDR site -> callee |
|---|---|---|
| 1 | `C00AD034` -> `C00ABA90` | `C00ACF10` -> `C00AB968` |
| 2 | `C00AD064` -> `C00ABB80` | `C00ACF40` -> `C00ABA58` |
| 3 | `C00AD090` -> `C00ABB80` | `C00ACF6C` -> `C00ABA58` |
| 4 | `C00AD0B8` -> `C00ABD0C` | `C00ACF94` -> `C00ABBE8` |
| 5 | `C00AD0E4` -> `C00ABE58` | `C00ACFC0` -> `C00ABD30` |
| 6 | `C00AD10C` -> `C00AC214` | `C00ACFE8` -> `C00AC0E8` |
| 7 | `C00AD134` -> `C00AC3B4` | `C00AD010` -> `C00AC28C` |
| 8 | `C00AD158` -> `C00AC434` | `C00AD038` -> `C00AC30C` |
| 9 | `C00AD180` -> `C00AC54C` | `C00AD060` -> `C00AC424` |
| 10 | `C00AD1A8` -> `C00AC574` | `C00AD088` -> `C00AC450` |
| 11 | `C00AD1D0` -> `C00AC72C` | `C00AD0B0` -> `C00AC60C` |
| 12 | `C00AD1F8` -> `C00AC574` | `C00AD0D8` -> `C00AC450` |
| 13 | `C00AD224` -> `C00AC72C` | `C00AD104` -> `C00AC60C` |
| 14 | `C00AD248` -> `C00AC754` | `C00AD128` -> `C00AC634` |
| 15 | `C00AD26C` -> `C00AC898` | `C00AD14C` -> `C00AC778` |
| 16 | `C00AD290` -> `C00AC8B0` | `C00AD170` -> `C00AC790` |
| 17 | `C00AD2B4` -> `C00AC938` | `C00AD194` -> `C00AC818` |
| 18 | `C00AD2D8` -> `C00ACA1C` | `C00AD1B8` -> `C00AC8FC` |
| 19 | `C00AD300` -> `C00ACAB0` | `C00AD1E0` -> `C00AC990` |

## scroll.yaml (asm/scroll)

| Name | What it is | MS-50G | MS-70CDR | How found | Conf. |
|---|---|---|---|---|---|
| slide sleep call | slide step: callp sleep (write) | `0xC00C4D98` exp `13501410` | `0xC00C4C18` exp `13f81310` | inside slide step 0xC00C4C64->0xC00C4AE4 (same body, 984 aligned instr before); sleep c00cf000->c00cebc0 (35 votes) | high |
| bump call 1 | key handler right/left release: callp bump (write) | `0xC00AC4D8` exp `93213110` | `0xC00AC3B0` exp `93153110` | caller of bump c00c4dcc->c00c4c4c ratio 1.0; first of the two | high |
| bump call 2 | key handler: callp bump (write) | `0xC00AC528` exp `93153110` | `0xC00AC400` exp `93093110` | second caller of the same bump, ratio 1.0 | high |
| bump sleep call | stock bump: callp sleep(125) (write) | `0xC00C4DF4` exp `13441410` | `0xC00C4C74` exp `13ec1310` | inside bump 0xC00C4C4C; same body; 1011 aligned instr before | high |
| STOCK_STEP | slide step(dir) | `0xC00C4C64` | `0xC00C4AE4` | function match, first-60-instr similarity 1.00, 2 callers vs 2, 2 aligned call sites vote for it | high |
| STOCK_SLEEP | sleep(ms), inferred | `0xC00CF000` | `0xC00CEBC0` | function match, first-60-instr similarity 1.00, 48 callers vs 47, 35 aligned call sites vote for it | high |
| STOCK_BUMP | bump(dir) | `0xC00C4DCC` | `0xC00C4C4C` | function match, first-60-instr similarity 1.00, 2 callers vs 2, 2 aligned call sites vote for it | high |
| CURSOR | byte 0 = cursor (5 = effect 1), word 1 = effect count | `0xC009C064` | `0xC009C064` | 4 aligned mvk/mvkh sites (cursor getter 0xC00C09D4->0xC00C0834) build the same value | high |

## version-1.1.yaml

| Name | What it is | MS-50G | MS-70CDR | How found | Conf. |
|---|---|---|---|---|---|
| boot version format | mvk lo16 of "v%s" (write); mvkh unchanged | `0xC00CD960` exp `2ada26006b076000` | `0xC00CD7C0` exp `2a8a24006b076000` | lo16 0x4DB4 -> 0x4914 = "v%s" at 0xC00E4914; opcode and the mvkh word identical; 115 aligned instr before, 597 after | high |
| "v%s" format string | format of the boot-screen version line | `0xC00E4DB4` | `0xC00E4914` | string match | high |
| VERSION (replace, menu list) | find "VERSION\0" occurrence 1 | `0xC00E94AD` | `0xC00E900D` | byte search: exactly 2 occurrences of "VERSION\0" in the 70CDR image, same count as the 50G (count: 2 holds) | high |
| VERSION (replace, screen title) | find "VERSION\0" occurrence 2 | `0xC00EBADC` | `0xC00EB604` | byte search (see above) | high |

## boot-logo.yaml

| Name | What it is | MS-50G | MS-70CDR | How found | Conf. |
|---|---|---|---|---|---|
| BIN/133 offset 0 | logo bitmap, expect_sha256 of the first 1024 bytes | `0e02045b371a5d5f...6941` | `4cec107883a50b5a...c082` (full: 4cec107883a50b5abbfc01ba76317a462d3759b98810865c33476675e03dc082) | sha256 of the 70CDR updater BIN/133 bytes 0-1023; the bitmap is the "MS-70CDR" logo, so scripts/midistomp_logo.py needs the 70CDR bitmap as input | high |
| BIN/133 model byte | flash model id read by Task_MIDI/identity (not written by boot-logo; info) | offset 0x2C00 = 0x58 | offset 0x2C00 = 0x61 | read from both BIN/133 files (docs/ms70cdr-port.md section "Model detection") | high |

## looper.yaml (asm/looper)

| Name | What it is | MS-50G | MS-70CDR | How found | Conf. |
|---|---|---|---|---|---|
| poll trampoline (retarget) | trampoline cave (16 zero bytes after a return) | `0xC00C8050` | `0xC00C82D0` | same cave as midi-clock (the looper overwrites the 16 bytes written by midi-clock) | high |
| toggle trampoline (retarget) | trampoline cave (16 zero bytes after a return) | `0xC00D3370` | `0xC00D2F30` | same cave as tempo-hold | high |
| hold trampoline (retarget) | trampoline cave (16 zero bytes after a return) | `0xC00D46B0` | `0xC00D4270` | same cave as tempo-hold | high |
| cc trampoline (retarget) | trampoline cave (16 zero bytes after a return) | `0xC00AF408` | `0xC00BB190` | same cave as midi-cc (new cave) | medium |
| draw hook call site | last call before the LCD send: callp LCD_MODE (0xC00B5794) \|\| or a13,a4 (write) | `0xC00BA9CC` exp `93baf51f` | not found | The callee (a 2-instr setter "stw a4,*+b14(612) ; bnop") and its getter 0xC00B5830 do not exist in the 70CDR: the B14+612 word has no counterpart and no store near the draw call. The call list after the overlay draw is: 50G ba9cc [LCD_MODE\|\|or a13,a4] ba9d4 [c00d5b60\|\|ldw b14(728)] ba9e4 [c00b5a80] ... ; 70CDR bb0ec [c00d5720\|\|ldw b14(708)] bb0f8 [c00b57c8] ... The closest hook is the call 0xC00BB0EC (callp 0xC00D5720 = 50G 0xC00D5B60) but draw_pre would then have to run before it and cannot call the setter. Needs a design decision | not found |
| EVENT_POST | (event, mask) | `0xC00CC680` | `0xC00CBF40` | function match, first-60-instr similarity 1.00, 16 callers vs 13, 10 aligned call sites vote for it; see midi-cc | high |
| OVL_GET | (0) -> overlay state, -1 = none | `0xC00CBA10` | `0xC00CCD6C` | function match, first-60-instr similarity 0.35, 15 callers vs 12, 12 aligned call sites vote for it; see tempo-hold | high |
| LCD_MODE | callee of the draw hook (setter of B14+612) | `0xC00B5794` | not found | function and the B14+612 word are gone in the 70CDR (see draw hook call site) | not found |
| LCD send | stock LCD send called after the hook (comment) | `0xC00B5A80` | `0xC00B57C8` | function match: 23 callers each, 21 aligned call sites vote | high |
| GPIO_BANK01 | pointer the OS GPIO writer uses (pin 0 = LED) | `0x1181DE70` | `0x1181DEF0` | 6 aligned mvk/mvkh uses; L2 data moved +0x80 (whole L2 BSS shifted by the bigger audio code) | high |
| GPIO writer | GPIO write helper 0x11819FC4(pin, value) (comment) | `0x11819FC4` | `0x11819FC4` | identical code at the same address (L2 core unchanged) | high |
| SLOT_STATE | word 1 of slot 0 state = params pointer (0x11F03000 + 4) | `0x11F03004` | `0x11F03004` | slot-state getter 0xC00C8BEC->0xC00C8E6C is byte-identical (mvk 212 ; mpyli ; mvk 12288/mvkh 0x11F0 -> base 0x11F03000) | high |
| SLOT_STRIDE | state block size per slot | 212 | 212 | same getter code (mvk 212,a0) | high |
| LED_APPLIED | bit 0: LED state the LED task wrote last | `0xC00EF078` | `0xC00EEB10` | 3 aligned mvk/mvkh sites in the LED task (0xC00C75B4 / 0xC00C73F4); 0xC00EF070 -> 0xC00EEB08 (13 votes) is the neighbour word | high |
| CURSOR | signed byte: cursor of view 0 | `0xC009C064` | `0xC009C064` | see scroll | high |
| CURSOR_SLOT | word [24 x cursor]: slot under it | `0xC00EEEB0` | `0xC00EE948` | 2 aligned mvk/mvkh sites in the footswitch press code (0xC00CC128 / 0xC00CB9E8) | high |
| FB | frame buffer (column bytes, 128 per 8-pixel row) | `0x11816800` | `0x11816800` | 48 aligned mvk/mvkh sites build the same value | high |
| FB_DIRTY | byte: rows to send | `0xC00EF118` | `0xC00EEBB0` | 37 aligned const sites; it is the word just before the first data section (0xC00EF11C / 0xC00EEBB4) | high |
| FONT7 | Effect View bold font, 7 bytes a character | `0xC00E8C78` | `0xC00E87D8` | content equal (first 28 bytes) + 3 aligned const sites | high |
| VIEW_KNOBS | word: 1 = knob pages, 0 = cover | `0xC009D398` | `0xC009D398` | 12 aligned const sites | high |
| MODE | 0 = play | B14+328 | B14+320 | see tempo-hold | high |
| PENDING | prompt over the Effect View | B14+348 | B14+340 | see tempo-hold | high |
| UI_EVENT | UI task event word | B14+676 | B14+656 | see midi-cc | high |
| LED path (comment) | LED set helper 0xC00CE054(0, 1-bit) | `0xC00CE054` | `0xC00CD3B4` | 2 aligned call sites vote; similarity 0.77. Only in a comment, looper.S writes GPIO via GPIO_BANK01 | medium |
| block.S regions | big buffer regions 3,2,1 (DDR) | `0xC0636980`+0x199680, `0xC01ADAD4`+0x5252C, `0xC0102000`+0x96000 | unchanged, not verified | not OS addresses; see "Our code areas"; boundaries come from the RAM test (T5) | medium |

## ram-test.yaml (asm/ram_test)

| Name | What it is | MS-50G | MS-70CDR | How found | Conf. |
|---|---|---|---|---|---|
| poll call site | Task_SwitchNrmlSpdRead: callp (write; same site as midi-clock) | `0xC00CA630` exp `12a82910` | `0xC00C6998` exp `12943010` | see midi-clock | high |
| screen 9 draw stub | callp 0xC00A8474 (write) | `0xC00A9434` exp `920afe1f` | `0xC00A93D0` exp `120dfe1f` | the VERSION screen draw stub: only caller of c00a8474->c00a8428; it is the screen-9 entry of the draw table (0xC00EEBD4 -> 0xC00A93D0) | high |
| TITLE | (title) | `0xC00A7378` | `0xC00A7378` | function match, first-60-instr similarity 1.00, 19 callers vs 19, 18 aligned call sites vote for it | high |
| TITLE_STR | "VERSION" (RAMTEST in this build) string "VERSION" | `0xC00E94AD` | `0xC00E900D` | string match in both images, same neighbouring strings | high |
| SNPRINTF | (buf, size, fmt, ...) | `0xC00DE3A0` | `0xC00DDEE0` | function match, first-60-instr similarity 1.00, 23 callers vs 24, 22 aligned call sites vote for it | high |
| TEXT | (0, text, x, y) | `0xC00A0040` | `0xC00A0040` | function match, first-60-instr similarity 1.00, 39 callers vs 34, 32 aligned call sites vote for it; 39 callers in the 50G, 34 in the 70CDR | high |
| SOFTKEY | (knob, text, 0) | `0xC009F8F0` | `0xC009F8F0` | function match, first-60-instr similarity 1.00, 49 callers vs 49, 42 aligned call sites vote for it | high |
| S_EMPTY | empty string | `0xC00E959C` | `0xC00E9101` | see midi-settings STR_BLANK | high |
| S_EXIT | "EXIT" string "EXIT" | `0xC00E9597` | `0xC00E90FC` | string match in both images, same neighbouring strings | high |
| POLL_TRAMP | midi-clock poll trampoline (jump target) | `0xC00C8050` | `0xC00C82D0` | see midi-clock (cave) | high |
| test regions | DDR/shared RAM regions the test fills (OS unused RAM) | 1: 0xC00F2000-0xC0197FFF, 2: 0xC01ADAD4-0xC01FFFFF, 3: 0xC0636980-0xC07CFFFF, 4: 0xC07F4000-0xC07FFFFF, 5: 0x80000000-0x8001FFFF | not re-measured | These are the free RAM found on the 50G OS. Static check on the 70CDR: the OS image ends at 0xC00F1364 (50G 0xC00F1958); the only OS constants in 0xC00F1364-0xC0800000 are the same six arena bases (0xC022D000, 0xC02D9440, 0xC0385880, 0xC0431CC0, 0xC04DE100, 0xC058A540) and 0xC87D0000/0xC87D4000/0xC87D4004 + 0x80000000 as before. Region boundaries are not built by any constant, so they must be measured again (T5) | medium |
| UNCACHED alias | 0xC8xxxxxx alias used by the OS for DMA buffers | `0xC87D0000`, `0xC87D4000`, `0xC87D4004` | same three constants | const scan of both OSes | high |

## Our code areas (not OS addresses): are they still free?

Our code is not an OS address, but it must not overlap anything the 70CDR OS uses. L2 constants/image words and DDR constants were scanned in both OSes (see the table).

| Name | What it is | MS-50G | MS-70CDR | How found | Conf. |
|---|---|---|---|---|---|
| L2 OS variables end | last OS-referenced L2 word (50G: 0x1181DE80, pointer, +4) | `0x1181DE84` | `0x1181DF04` | mvk/mvkh scan of all of L2: highest constant 0x1181DE80 (50G) vs 0x1181DF00 (70CDR); the whole L2 BSS moved +0x80 because the audio code section grew by 0x80 (0x1181AB80+0x1380 vs +0x1400) | high |
| L2 free start | first free L2 address for our code | `0x1181DEA0` (what the patches use) | `0x1181DF08` (4-byte pointer at 0x1181DF00 ends at 0x1181DF04) | derived from the line above. 0x1181DEA0-0x1181DF03 now holds OS variables: GPIO bank pointer 0x1181DEF0, McASP base 0x1181DE8C, 0x1181DEB0-0x1181DED8 etc. | high |
| L2 free end | end of L2 RAM | `0x11820000` | `0x11820000` | same memory map (cache split is set by the OS L2CFG, not compared)  | medium |
| L2 space balance | bytes our L2 sections need vs have | need 8448 B (416+1696+192+448+4224+1152+32+224+64); 50G has 8544 B (0x1181DEA0-0x11820000), slack 96 B | have 8440 B (0x1181DF08-0x11820000), 8444 B from 0x1181DF04; need 8448 | does not fit (short by 4-8 bytes) even with zero slack, and the fixed addresses (transport block 0x1181FF00, vectors) cannot move without breaking effects that read them. Some code must go to DDR (T3/T4 decision). This is a verified conflict, listed under Blockers | high |
| L2 midi_cc handler | handler.S, 416 B | `0x1181DEA0`-`0x1181E03F` | conflict: 0x1181DEA0-0x1181DF03 now holds OS variables (GPIO bank pointer 0x1181DEF0, McASP base 0x1181DE8C, 0x1181DEB0-0x1181DED8 ...) | OS L2 variables end at 0x1181DF04 (see above); verified conflict, listed under Blockers | high |
| L2 clock.S | clock handler, 1696 B | `0x1181E040`-`0x1181E6DF` | free at this address, but the chain in front of it must move (see balance) | static check: no mvk/mvkh constant and no image word at or above 0x1181DF08 (0x1181DF00 is the last OS word); indexed access from a base pointer cannot be excluded | medium |
| L2 clock variables | VARS, 192 B | `0x1181E700`-`0x1181E7BF` | free | static check: no mvk/mvkh constant and no image word at or above 0x1181DF08 (0x1181DF00 is the last OS word); indexed access from a base pointer cannot be excluded | medium |
| L2 tuner_exit | tuner_exit.S, 64 B | `0x1181E7C0`-`0x1181E7FF` | free | static check: no mvk/mvkh constant and no image word at or above 0x1181DF08 (0x1181DF00 is the last OS word); indexed access from a base pointer cannot be excluded | medium |
| L2 poll.S | transport poll, 448 B | `0x1181E800`-`0x1181E9BF` | free | static check: no mvk/mvkh constant and no image word at or above 0x1181DF08 (0x1181DF00 is the last OS word); indexed access from a base pointer cannot be excluded | medium |
| L2 settings.S | MIDI SETTINGS, 4224 B | `0x1181EA00`-`0x1181FA7F` | free | static check: no mvk/mvkh constant and no image word at or above 0x1181DF08 (0x1181DF00 is the last OS word); indexed access from a base pointer cannot be excluded | medium |
| L2 hold.S | tempo/hold handlers, 1152 B | `0x1181FA80`-`0x1181FEFF` | free | static check: no mvk/mvkh constant and no image word at or above 0x1181DF08 (0x1181DF00 is the last OS word); indexed access from a base pointer cannot be excluded | medium |
| L2 transport block | published to effects (docs/transport-block.md), 32 B | `0x1181FF00`-`0x1181FF1F` | free; the address is part of the effect ABI, so it should stay | static check: no mvk/mvkh constant and no image word at or above 0x1181DF08 (0x1181DF00 is the last OS word); indexed access from a base pointer cannot be excluded | medium |
| L2 hold2.S | hold2 handlers, 224 B | `0x1181FF20`-`0x1181FFFF` | free (ends exactly at 0x11820000) | static check: no mvk/mvkh constant and no image word at or above 0x1181DF08 (0x1181DF00 is the last OS word); indexed access from a base pointer cannot be excluded | medium |
| DDR ram_test | ramtest.S, 672 B | `0xC00F1960`-`0xC00F1BFF` | free (the 70CDR image is 0x5F4 shorter, so the area 0xC00F1364-0xC00F195F is free too) | static check only: above the 70CDR image end 0xC00F1364; no OS constant points into 0xC00F1364-0xC0800000 except the six arena bases; the OS .bss/.far is not in the image (cinit compressed), so the RAM test (T5) must confirm | medium |
| DDR version string | "v1.1", 8 B | `0xC00F2000` | free | static check only: above the 70CDR image end 0xC00F1364; no OS constant points into 0xC00F1364-0xC0800000 except the six arena bases; the OS .bss/.far is not in the image (cinit compressed), so the RAM test (T5) must confirm | medium |
| DDR step.S | patch step, 128 B | `0xC00F2020`-`0xC00F209F` | free | static check only: above the 70CDR image end 0xC00F1364; no OS constant points into 0xC00F1364-0xC0800000 except the six arena bases; the OS .bss/.far is not in the image (cinit compressed), so the RAM test (T5) must confirm | medium |
| DDR scroll.S | scroll, 256 B | `0xC00F2100`-`0xC00F21FF` | free | static check only: above the 70CDR image end 0xC00F1364; no OS constant points into 0xC00F1364-0xC0800000 except the six arena bases; the OS .bss/.far is not in the image (cinit compressed), so the RAM test (T5) must confirm | medium |
| DDR looper.S | looper hooks, 1536 B | `0xC00F2200`-`0xC00F27FF` | free | static check only: above the 70CDR image end 0xC00F1364; no OS constant points into 0xC00F1364-0xC0800000 except the six arena bases; the OS .bss/.far is not in the image (cinit compressed), so the RAM test (T5) must confirm | medium |
| DDR services block | block.S, 128 B | `0xC00F3000`-`0xC00F307F` | free | static check only: above the 70CDR image end 0xC00F1364; no OS constant points into 0xC00F1364-0xC0800000 except the six arena bases; the OS .bss/.far is not in the image (cinit compressed), so the RAM test (T5) must confirm | medium |
| L1D | nothing of ours is loaded in L1D; looper reads slot state `0x11F03000..` | OS uses up to 0x11F03B18 | OS uses up to 0x11F03B7C (bigger input buffers) | const scan; SLOT_STATE base unchanged | high |

## Method

- Both OS images were disassembled (`tic6x-elf-objdump -d`) and aligned instruction by instruction after masking addresses and large immediates (anchors on unique 12-instruction runs, then recursive diff). Function pairs were confirmed by body similarity, caller/callee sets and call order; call sites by their enclosing function and neighbours; data by the code that builds/loads it (`mvk/mvkh` pairs resolved to 32-bit constants, 40-90 votes for common ones), string matches, and byte-identical table contents.
- The alignment alone put several sites on a neighbouring call (e.g. the menu-keys stub, the key-loop calls); those were corrected by hand using the function pairing above.
- Caves: 16 aligned zero bytes after a `bnop .S2 b3,5` return, no branch/call target or image word pointing into the zero run, and the fetch packet header slot of every packet touched is not 0xE... (plain packet). The same scan accepts all 21 50G caves. `tuner_label_trampoline.S` hand-encodes its branch relative to the fetch packet: the new cave 0xC00DAA30 is at the same packet offset (+0x10), only the packet base (0xC00DAA20) changes.
- Throwaway scripts live in the session scratchpad, not in the repo.
