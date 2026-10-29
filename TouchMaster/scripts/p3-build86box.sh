#!/bin/sh
# Out-of-tree build of the user's 86Box-Next2 source with the automation socket
# (and GDB stub) on, for scripted boots. Same options as their build-static
# except AUTOMATION/GDBSTUB on, LATEST_VERSIONS/DISCORD off. The source tree's
# .build-number (bumped by every link) is saved and restored, so the user's
# tree is left exactly as it was.
# Run from MSYS2:  ... bash -l scripts/p3-build86box.sh [<src> [<builddir> [rig]]]
# P10: a third argument "rig" builds without AUTOMATION/GDBSTUB (the GDB stub starts
# the CPU stopped), for the ready-to-run rigs in Rigs/.
# P3b: src=/f/Claude/86Box-Next2-touchmaster (branch touchmaster), builddir=analysis/p3/build86tm
set -e
SRC=${1:-/f/Claude/86Box-Next2}
OUT=${2:-/f/Claude/TouchMaster/analysis/p3/build86}
DBG="-DAUTOMATION=ON -DGDBSTUB=ON"
if [ "$3" = rig ]; then DBG="-DAUTOMATION=OFF -DGDBSTUB=OFF"; fi
BN=$(cat $SRC/.build-number 2>/dev/null || echo)
restore() { if [ -n "$BN" ]; then printf '%s\n' "$BN" > $SRC/.build-number; fi; }
trap restore EXIT
echo "source HEAD: $(git -C $SRC rev-parse HEAD) dirty: $(git -C $SRC status --porcelain | wc -l)"
cmake -S $SRC -B $OUT -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DQT=ON -DUSE_QT6=ON -DSTATIC_BUILD=ON -DDYNAREC=ON -DOPENAL=ON -DRTMIDI=ON -DFLUIDSYNTH=ON \
  -DSOUNDCANVAS=ON -DLIBRASHADER=ON -DWITH_LZMA_ASM=ON -DEMBED_QTBASE_TRANSLATIONS=ON \
  $DBG -DLATEST_VERSIONS=OFF -DDISCORD=OFF -DBUILD_TESTING=OFF
cmake --build $OUT
ls -la $OUT/src/*.exe
sha256sum $OUT/src/*.exe
