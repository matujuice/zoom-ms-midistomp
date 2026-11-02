"""Host check for asm/mixer/chain_draw.c: build it with a host C compiler plus
tests/chain_draw_host.c, draw the preview states (the chain screen; the node pages are stock drawing) and write each as <name>.fb (the raw
128 x 64 framebuffer) and <name>.png (4x, the mockup's colors) in build/out/chain-preview/.

Usage: py scripts/chain_draw_preview.py [outdir]
Exit code 2 when no host C compiler is found."""
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = [ROOT / "asm/mixer/chain_draw.c", ROOT / "tests/chain_draw_host.c"]
INC = ROOT / "asm/mixer"
BG, INK = (0xE2, 0xE5, 0xE8), (0x3A, 0x3C, 0x96)   # the mockup's LCD colors
EXTRA = ["C:/msys64/ucrt64/bin/gcc.exe", "C:/msys64/mingw64/bin/gcc.exe", "C:/mingw64/bin/gcc.exe",
         "C:/Program Files/LLVM/bin/clang.exe"]


def find_cc():
    """The command that compiles a C file, or None."""
    for name in ("gcc", "clang", "cc", "cl"):
        if shutil.which(name):
            return [shutil.which(name)]
    for p in EXTRA:
        if Path(p).exists():
            return [p]
    if subprocess.run([sys.executable, "-m", "ziglang", "version"], capture_output=True).returncode == 0:
        return [sys.executable, "-m", "ziglang", "cc"]   # pip install ziglang
    return None


def compile_driver(cc, exe):
    if Path(cc[0]).stem.lower() == "cl":
        cmd = cc + ["/nologo", "/I" + str(INC), *map(str, SRC), "/Fe:" + str(exe), "/Fo:" + str(exe.parent) + "\\"]
    else:
        cmd = cc + ["-std=c99", "-Wall", "-Wextra", "-O1", "-I" + str(INC), *map(str, SRC), "-o", str(exe)]
    subprocess.run(cmd, check=True)


def render(fb, scale=4):
    img = Image.new("RGB", (128, 64))
    img.putdata([INK if fb[y * 16 + x // 8] >> (7 - x % 8) & 1 else BG for y in range(64) for x in range(128)])
    return img.resize((128 * scale, 64 * scale), Image.NEAREST)


def run(outdir):
    cc = find_cc()
    if cc is None:
        return None
    outdir.mkdir(parents=True, exist_ok=True)
    exe = outdir / "chain_draw_host.exe"
    compile_driver(cc, exe)
    subprocess.run([str(exe), str(outdir)], check=True)
    pngs = []
    for fbf in sorted(outdir.glob("*.fb")):
        render(fbf.read_bytes()).save(fbf.with_suffix(".png"))
        pngs.append(fbf.with_suffix(".png"))
    return pngs


if __name__ == "__main__":
    pngs = run(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build/out/chain-preview")
    if pngs is None:
        sys.exit("no host C compiler found (gcc, clang, cl, or `pip install ziglang`)")
    print("\n".join(map(str, pngs)))
