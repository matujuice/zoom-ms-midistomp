"""Stock-UI screen shots (MIDI menu, tempo, MENU, SETTINGS, HOLD FOR, boot): builds the MS-70CDR 2.10 OS with our
patches, disassembles it with TI dis6x, runs C auto-init in c6x.py and calls the OS's own draw routines.

Needs Zoom's updater (ZOOM_UPDATER, default ~/Downloads/ZOOM MS-70CDR v2.10 Updater.exe) and TI CGT 8.5 (TI_CGT).
run(dir) writes <dir>/<screen>.fb, 8192 '0'/'1' (y*128+x)."""
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import c6x  # noqa: E402
from build_mixer_ui import CGT  # noqa: E402
from zoomms import ais, cli, parts, patcher  # noqa: E402

UPDATER = Path(os.environ.get("ZOOM_UPDATER", Path.home() / "Downloads/ZOOM MS-70CDR v2.10 Updater.exe"))
FB, B14, STOP, SP = 0x11816800, 0xC00EF748, 0xDEAD0000, 0x1180CF78
RELEASE = ["version-1.2", "boot-logo", "midi-cc", "midi-clock", "midi-settings", "tempo-hold", "scroll"]
# v2 = the 2.0 set (diag takes the m0 probe's place, looper goes before mixer-m2)
STAMP = ["version=V2.0", "commit=08f3ed8", "date=2026-10-24"]  # fixed diag.c build stamps, so the shots do not change per run
IMAGES = {"release": RELEASE, "v2": RELEASE + ["looper", "mixer-m2", "diag"]}


def available():
    return UPDATER.exists() and (CGT / "bin").exists()


def elf(secs, entry=0xC00DD800):
    """The image as a C6000 ELF with Tag_ISA = C674x, so dis6x expands compact instructions."""
    secs = sorted(secs)
    sub = b"c6xabi\0" + bytes([1]) + struct.pack("<I", 5 + 2) + bytes([4, 8])
    attr = b"A" + struct.pack("<I", 4 + len(sub)) + sub
    names = [f".s{a:08x}" for a, _ in secs] + [".c6xabi.attributes", ".shstrtab"]
    strtab, noff = b"\0", []
    for n in names:
        noff.append(len(strtab))
        strtab += n.encode() + b"\0"
    ph, body, offs = 0x34, bytearray(), []
    base = ph + 0x20 * len(secs)
    for _, d in secs:
        offs.append(base + len(body))
        body += d + b"\0" * (-len(d) % 4)
    attr_off = base + len(body)
    body += attr + b"\0" * (-len(attr) % 4)
    str_off = base + len(body)
    body += strtab + b"\0" * (-len(strtab) % 4)
    sh_off, nsh = base + len(body), len(secs) + 3
    out = bytearray(sh_off + 0x28 * nsh)
    out[:16] = b"\x7fELF\x01\x01\x01" + b"\0" * 9
    struct.pack_into("<HHIIIIIHHHHHH", out, 16, 2, 140, 1, entry, ph, sh_off, 0, 0x34, 0x20, len(secs), 0x28, nsh, nsh - 1)
    for i, ((a, d), so) in enumerate(zip(secs, offs)):
        struct.pack_into("<8I", out, ph + i * 0x20, 1, so, a, a, len(d), len(d), 7, 4)
        struct.pack_into("<10I", out, sh_off + (i + 1) * 0x28, noff[i], 1, 6, a, so, len(d), 0, 0, 4, 0)
    out[base:base + len(body)] = body
    struct.pack_into("<10I", out, sh_off + (nsh - 2) * 0x28, noff[-2], 0x70000003, 0, 0, attr_off, len(attr), 0, 0, 1, 0)
    struct.pack_into("<10I", out, sh_off + (nsh - 1) * 0x28, noff[-1], 3, 0, 0, str_off, len(strtab), 0, 0, 1, 0)
    return bytes(out)


def build_images(tmp):
    os_part = next(p for p in parts.find_parts(UPDATER) if p.resource_id == 129)
    original = parts.read_part(UPDATER, os_part)
    for name, ps in IMAGES.items():
        img = ais.parse(original)
        texts = cli.build_stamp([str(ROOT / "patches" / f"{p}.yaml") for p in ps], STAMP)
        for p in ps:
            patcher.apply(img, patcher.load(ROOT / "patches" / f"{p}.yaml"), "ms70cdr-2.10", texts)
        with open(tmp / f"{name}.mem", "wb") as f:
            for s in img.sections:
                f.write(struct.pack("<II", s.addr, len(s.data)) + bytes(s.data))
        (tmp / f"{name}.elf").write_bytes(elf([(s.addr, bytes(s.data)) for s in img.sections]))
        with open(tmp / f"{name}.dis", "w") as f:
            subprocess.run([str(CGT / "bin/dis6x"), f"{name}.elf"], cwd=tmp, check=True, stdout=f)


def boot(tmp, image, _cache={}):
    """Run _c_int00 up to just after C auto-init (globals set), before BIOS starts."""
    if image not in _cache:
        _cache[image] = c6x.parse_listing(tmp / f"{image}.dis")
    listing = _cache[image]
    for ins in listing.values():
        ins.fn = None  # compiled closures are bound to the previous CPU
    mem = c6x.Memory()
    mem.load(tmp / f"{image}.mem")
    cpu = c6x.CPU(listing, mem)
    cpu.run(0xC00DD800, 0xC00DD870, max_ep=5_000_000)
    assert cpu.R[46] == B14, hex(cpu.R[46])
    return cpu


def call(cpu, fn, *args, max_ep=5_000_000):
    for t in sorted(cpu.wq):  # land loads still in flight from the last run, so they cannot clobber the args
        for r, v in cpu.wq[t]:
            cpu.R[r] = v
    cpu.wq = {}
    for r, v in zip([4, 36, 6, 38, 8, 40, 10, 42], args):  # A4 B4 A6 B6 A8 B8 A10 B10
        cpu.R[r] = v & 0xFFFFFFFF
    cpu.R[35], cpu.R[47], cpu.branch = STOP, SP, {}
    cpu.run(fn, STOP, max_ep=max_ep)
    return cpu.R[4]


def w32(cpu, a, v):
    cpu.mem.write(a, 4, v)


def screen_list(cpu, sid, row=0, top=0):
    w32(cpu, B14 + 352, sid); w32(cpu, B14 + 356, row); w32(cpu, B14 + 360, top)
    call(cpu, 0xC00A934C, 1)


def menu(row=0, top=0):
    def draw(cpu):
        w32(cpu, B14 + 129 * 4, 5)  # BATTERY_LEVEL 5: menu draws the battery icon only for 0..4
        w32(cpu, B14 + 320, 11)  # MODE 11 (menu screens): diag.c draws its DSP / CPU badges only there
        patch_state(cpu)
        diag_measure(cpu)
        screen_list(cpu, 0, row, top)
    return draw


def settings(row, top):
    def draw(cpu):
        w32(cpu, 0xC009D8FC, 5)  # LCD CONTRAST 5 (inferred; 1..10, the flash settings record is not loaded here)
        screen_list(cpu, 1, row, top)
    return draw


def hold_for(cpu):
    call(cpu, 0x1181F304, 7)  # settings.S open_choice(s_hold): V_ITEM, SET_SCREEN(13, value)
    call(cpu, 0xC00A934C, 1)


def tempo(live):
    def draw(cpu):
        cpu.mem.write(0x1181EA00, 4, cpu.mem.read(0x1181EA00, 4) & ~1)  # MIDI_FLAGS: CLOCK RECEIVE on
        last = 1000 if live else 0  # V_LAST 0 = no clock since boot
        w32(cpu, 0x1181E704, last)

        def ticks(c):  # CLOCK_GETTICKS: 10 ms after the last tick
            c.R[4] = last + 10
            return c.R[35]
        cpu.hooks[0xC00DEE20] = ticks
        w32(cpu, 0xC009C06C, 120)  # TEMPO_VALUE
        call(cpu, 0x1181FA80, 0, 120)  # hold.S tempo_draw(0, tempo)
    return draw


def boot_screen(version):
    def draw(cpu):
        logo_buf = 0xC00929D8  # the OS reads BIN/133 here; its first 1024 bytes are the logo
        y = (ROOT / "patches/boot-logo.yaml").read_text()
        for i, b in enumerate(bytes.fromhex(re.sub(r"\s", "", y.split("data: >-", 1)[1])[:2048])):
            cpu.mem.write(logo_buf + i, 1, b)
        fmt = 0xC00F2000  # version-1.2's "v1.2" string; overwritten for a version with no patch yet
        for i, b in enumerate(version.encode() + b"\0"):
            cpu.mem.write(fmt + i, 1, b)
        buf = SP + 0x200  # the boot routine's last frame (0xc00cd7b8..0xc00cd8e8)
        w32(cpu, SP + 4, fmt); w32(cpu, SP + 8, 0)
        call(cpu, 0xC00DDEE0, buf, 8)  # snprintf(buf, 8, fmt)
        call(cpu, 0xC00A1964, 0, 1)  # clear
        call(cpu, 0xC009F800, 0, 0, 0, 128, 64, logo_buf)  # blit logo 128x64 at 0,0
        call(cpu, 0xC00A9C68, 0, buf, 64, 46)  # version text, x 64, y 46
    return draw


DIAG = 0xC00F3100  # diag_vec.asm: +0 diag_end, +24 the screen 9 keys
FX_TABLE, DESC, FAKE = 0xC00EE930, 0xC0064E04, 0xC0200000  # FAKE: free RAM (looper region 2) for the state below


def patch_state(cpu):
    """A 3-effect patch as diag.c reads it (normally the ZDLs loaded from flash put this in RAM): per slot
    the audio function, the descriptor's name and declared DSP. Names are real MS-70CDR effects; the DSP
    values are inferred (sum 135, the diagnostics-plan example), the function addresses are dummies."""
    for s, (name, dsp) in enumerate([("Chorus", 20.0), ("TapeEcho", 40.0), ("HD Hall", 75.0)]):
        d, f = FAKE + 0x100 * s, FAKE + 0x1000 + 0x100 * s
        w32(cpu, FX_TABLE + 4 * s, f); w32(cpu, DESC + 28 * s, d)
        for i, b in enumerate(name.encode() + b"\0"):
            cpu.mem.write(d + 48 + i, 1, b)
        w32(cpu, d + 48 + 32, f); w32(cpu, d + 48 + 40, struct.unpack("<I", struct.pack("<f", dsp))[0])


def diag_measure(cpu):
    """diag.c's own averaging: diag_end over one 4096-block window (TSCL = cpu.t). Cycles inferred from
    docs/dev/mixer-mode-m0.md (about 100 per declared DSP unit, OS about 18 %): CPU 47 %."""
    cyc = FAKE + 0x2000
    t0 = 1 << 20
    for n in range(4097):
        for i, v in enumerate([0, 2100, 4300, 7600]):  # perf_block (PERFORM off), slots 1-3
            w32(cpu, cyc + 4 * i, v)
        cpu.t = t0 + (15800 if n != 2000 else 21300)  # the chain, one slower block for AUDIO MAX
        call(cpu, DIAG, t0, cyc)
        t0 += 25580
    blocks = [a for a in range(DIAG, DIAG + 0x2300, 4) if cpu.mem.read(a, 4) == 4097]
    assert len(blocks) == 1, blocks  # diag.c's block counter: the only word that counted every call
    w32(cpu, blocks[0], round(5512.5 * (3600 + 23 * 60 + 45)))  # UPTIME 1:23:45


def system(page):
    def draw(cpu):
        patch_state(cpu)
        diag_measure(cpu)
        for _ in range(page):
            call(cpu, DIAG + 24, 67)  # knob 3 click: next page
        screen_list(cpu, 9)
    return draw


MIXER = 0xC00F6000  # mixer.S BASE (asm/mixer/chain.h, stock.h)


def mixer_page(pg):
    """Screen 15, the node knob page PAGE = pg (pages.c PG_*) of a Parallel patch (settings by inference)."""
    def draw(cpu):
        live = {0: 1, 1: 50, 2: 100, 3: 100, 4: 80, 5: 50, 6: 100, 7: 0, 8: 100, 9: 90}  # Mode Paral, Send AB, ...
        for s in range(24):
            cpu.mem.write(MIXER + 224 + s, 1, live.get(s, 100 if s in (18, 19) else 0))  # InR, MastR follow
        w32(cpu, MIXER + 128, pg)
        screen_list(cpu, 15)
    return draw


# name -> (image, draw)
SCREENS = {
    "midi_menu": ("v2", lambda cpu: screen_list(cpu, 14)),
    "midi_menu_2": ("v2", lambda cpu: screen_list(cpu, 14, row=3, top=2)),
    "settings": ("v2", settings(3, 4)),
    "settings_2": ("v2", settings(0, 0)),
    "settings_3": ("v2", settings(3, 6)),  # pedal_in.c: 10 rows, MIDI last
    "menu": ("v2", menu()),
    "menu_2": ("v2", menu(1, 3)),  # row is relative to top: the cursor on SYSTEM
    "hold_for": ("release", hold_for),  # v2 changes HOLD FOR in the list (pedal_in.c), no choice screen
    "tempo_turn_tap": ("release", tempo(False)),
    "tempo_clock": ("release", tempo(True)),
    "boot": ("release", boot_screen("v2.0")),
    **{f"mixer_{n}": ("v2", mixer_page(pg)) for n, pg in [("in", 0), ("route", 1), ("mix_1", 3), ("mix_2", 4), ("mix_3", 5), ("out", 6)]},
    **{f"system_{n}": ("v2", system(i)) for i, n in enumerate(["version", "load", "effects", "mods"])},
}


def run(out):
    out.mkdir(parents=True, exist_ok=True)
    build_images(out)
    for name, (image, draw) in SCREENS.items():
        cpu = boot(out, image)
        for i in range(1024):
            cpu.mem.write(FB + i, 1, 0)
        draw(cpu)
        bits = "".join(str(cpu.mem.read(FB + (y >> 3) * 128 + x, 1) >> (y & 7) & 1) for y in range(64) for x in range(128))
        (out / f"{name}.fb").write_text(bits)
