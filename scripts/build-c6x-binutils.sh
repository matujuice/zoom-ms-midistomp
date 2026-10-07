#!/bin/sh
# Build GNU binutils for TI C6000 (assembler, linker, objdump with C674x
# compact-instruction support). Used instead of TI's CGT, which is not
# needed for disassembly or for assembling firmware patches.
set -eu
VER=${VER:-2.42}
PREFIX=${PREFIX:-/opt/c6x}
WORK=${WORK:-$(mktemp -d)}
cd "$WORK"
curl -fsSLo binutils.tar.xz "http://archive.ubuntu.com/ubuntu/pool/main/b/binutils/binutils_${VER}.orig.tar.xz"
tar xf binutils.tar.xz
mkdir -p "binutils-${VER}/b" && cd "binutils-${VER}/b"
../configure --target=tic6x-elf --prefix="$PREFIX" --disable-nls --disable-werror \
  --disable-gdb --disable-gprofng --disable-sim
make -j"$(nproc)" MAKEINFO=true
make install MAKEINFO=true
echo "installed to $PREFIX/bin"
