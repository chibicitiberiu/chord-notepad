#!/usr/bin/env bash
# Symbolicate an iOS crash report on Linux with llvm-symbolizer and the dSYMs
# from CI (docs/IOS.md, "Crash reports").
#
#   ios/tools/symbolicate.sh <crash.ips> <dSYMs>... > crash.txt
#
# <dSYMs>: .dSYM bundles or folders holding them, e.g. a downloaded
# ios-testflight-dsyms or ios-development artifact of the run that built the
# crashing build:
#
#   gh run download <run> -n ios-testflight-dsyms -D /tmp/dsyms-<run>
#   ios/tools/symbolicate.sh crash.ips /tmp/dsyms-<run>
#
# The images are matched by UUID; a dSYM from another build is refused
# (symbolicate_ips.py). Needs python3 and llvm-symbolizer (Fedora: llvm;
# llvm-symbolizer-NN also works); swift-demangle, when on PATH, demangles
# Swift names. LLVM_SYMBOLIZER or SWIFT_DEMANGLE pick other binaries.
set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

if [ $# -lt 2 ]; then
    sed -n '2,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 2
fi

find_symbolizer() {
    if [ -n "${LLVM_SYMBOLIZER:-}" ]; then
        echo "$LLVM_SYMBOLIZER"
        return
    fi
    if command -v llvm-symbolizer >/dev/null 2>&1; then
        command -v llvm-symbolizer
        return
    fi
    # The newest versioned one (llvm-symbolizer-18, -19, ...).
    local found
    found=$(compgen -c llvm-symbolizer- 2>/dev/null | sort -t- -k3 -n | tail -n 1 || true)
    if [ -n "$found" ]; then
        command -v "$found"
    fi
}

SYMBOLIZER=$(find_symbolizer)
if [ -z "$SYMBOLIZER" ]; then
    echo "error: no llvm-symbolizer on PATH (Fedora: sudo dnf install llvm), or set LLVM_SYMBOLIZER" >&2
    exit 1
fi

args=(--symbolizer "$SYMBOLIZER")
DEMANGLER=${SWIFT_DEMANGLE:-$(command -v swift-demangle 2>/dev/null || true)}
if [ -n "$DEMANGLER" ]; then
    args+=(--demangler "$DEMANGLER")
fi

exec python3 -I "$HERE/symbolicate_ips.py" "${args[@]}" "$@"
