#!/usr/bin/env bash
# Put signing certificates into a temporary keychain on a macOS runner
# (ios.yml's release lanes, build.yml's Developer ID DMG; docs/RELEASE.md and
# docs/IOS.md, "Enrollment day").
#
#   packaging/apple/import_certificates.sh <keychain> <P12 variable> <password variable> [<P12 var> <pw var>]...
#
# The arguments are the NAMES of environment variables holding a base64
# .p12 and its password, so no secret is on a command line or in the log. A
# pair whose .p12 variable is empty is skipped (the optional fallback
# certificates). The keychain gets a random password, is unlocked for six
# hours, goes first in the user's search list, and lets codesign use its keys
# without a prompt. Prints how many signing identities it holds, not their
# names. Delete it afterwards with `security delete-keychain <keychain>`.
set -euo pipefail

KEYCHAIN=${1:?usage: import_certificates.sh <keychain> <p12 var> <password var> ...}
shift
[ $(( $# % 2 )) -eq 0 ] && [ $# -gt 0 ] || { echo "error: give .p12 and password variable names in pairs" >&2; exit 2; }

PASSWORD=$(openssl rand -base64 24)
security create-keychain -p "$PASSWORD" "$KEYCHAIN"
security set-keychain-settings -lut 21600 "$KEYCHAIN"
security unlock-keychain -p "$PASSWORD" "$KEYCHAIN"

imported=0
while [ $# -gt 0 ]; do
    p12_var=$1 password_var=$2
    shift 2
    p12=${!p12_var:-}
    if [ -z "$p12" ]; then
        echo "$p12_var is empty: skipped"
        continue
    fi
    file=$(mktemp)
    printf '%s' "$p12" | base64 --decode > "$file"
    security import "$file" -k "$KEYCHAIN" -f pkcs12 -P "${!password_var:-}" \
        -T /usr/bin/codesign -T /usr/bin/security -T /usr/bin/productbuild >/dev/null
    rm -f "$file"
    echo "imported $p12_var"
    imported=$((imported + 1))
done
[ "$imported" -gt 0 ] || { echo "error: no certificate imported" >&2; exit 1; }

security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$PASSWORD" "$KEYCHAIN" >/dev/null
# shellcheck disable=SC2046 # the existing keychains, one word each
security list-keychains -d user -s "$KEYCHAIN" $(security list-keychains -d user | tr -d '"')
security find-identity -v -p codesigning "$KEYCHAIN" | tail -n 1
