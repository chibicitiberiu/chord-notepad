#!/usr/bin/env bash
# Generate the two Android release keys (docs/RELEASE.md, "Android: keys").
#
#   foss.p12    the FOSS key: signs the APK on GitHub releases (and F-Droid, if
#               it ever builds reproducibly). Losing it means GitHub installs
#               can never be updated again; users would have to uninstall.
#   upload.p12  the Play upload key: signs the AAB uploaded to Play Console.
#               Google re-signs with its own app signing key; a lost upload
#               key can be reset through Play support.
#
# Run it yourself in a terminal (in Claude Code: prefix with `!`), so the
# passwords never show up in a transcript:
#
#   android/tools/make_keys.sh /path/outside/the/repo/android-keys
#
# Passwords are read with `read -s` and handed to keytool through the
# environment of the keytool process only. Nothing is uploaded: the script
# prints the `gh secret set` commands to run next. It refuses to write inside
# the repository and never overwrites an existing keystore.
set -euo pipefail

usage() {
    echo "usage: $0 <directory outside the repo>" >&2
    echo "  env: CN_KEY_DNAME (default 'CN=Tiberiu Chibici, O=Chord Notepad')" >&2
    exit 2
}
[[ $# -eq 1 ]] || usage

command -v keytool >/dev/null || { echo "keytool not found (source android/local.env for the JDK)" >&2; exit 1; }

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
dir=$(realpath -m "$1")
case "$dir/" in
    "$repo"/*) echo "refusing to create keys inside the repository ($dir)" >&2; exit 1 ;;
esac
mkdir -p "$dir"
chmod 700 "$dir"

dname=${CN_KEY_DNAME:-"CN=Tiberiu Chibici, O=Chord Notepad"}
# 50 years: Play wants validity past 2033; the FOSS key must outlive the app.
validity=18250

read_password() {  # $1 = label; sets $password
    local again
    while true; do
        read -rsp "Password for the $1 keystore (min 12 chars): " password; echo >&2
        read -rsp "Again: " again; echo >&2
        if [[ "$password" != "$again" ]]; then
            echo "They don't match, try again." >&2
        elif (( ${#password} < 12 )); then
            echo "Too short, try again." >&2
        else
            return 0
        fi
    done
}

make_key() {  # $1 = name (foss|upload), $2 = label
    local name=$1 label=$2 store="$dir/$1.p12"
    if [[ -e "$store" ]]; then
        echo "$store exists; skipping (delete it yourself if you really mean to replace it)" >&2
    else
        read_password "$label"
        CN_KEY_PW="$password" keytool -genkeypair -v \
            -storetype PKCS12 -keystore "$store" -storepass:env CN_KEY_PW \
            -alias "$name" -keyalg RSA -keysize 4096 -sigalg SHA256withRSA \
            -validity "$validity" -dname "$dname"
        chmod 600 "$store"
        # The public certificate, kept next to the keystore (Play asks for
        # the upload certificate when resetting an upload key; developer
        # verification asks for the FOSS key's fingerprint).
        CN_KEY_PW="$password" keytool -exportcert -rfc \
            -keystore "$store" -storepass:env CN_KEY_PW -alias "$name" -file "$dir/$name-cert.pem"
        unset password
    fi
}

make_key foss "FOSS (GitHub APK)"
make_key upload "Play upload"

fingerprints="$dir/fingerprints.txt"
{
    echo "Chord Notepad Android signing certificates (public data; safe to publish)"
    echo "Package: com.tibich.chordnotepad"
    for name in foss upload; do
        echo
        echo "[$name]"
        keytool -printcert -file "$dir/$name-cert.pem" | grep -E 'Owner:|Valid from|SHA256:|SHA1:'
    done
} > "$fingerprints"
cat "$fingerprints"

cat <<EOF

Keys are in $dir (fingerprints in $fingerprints).

Next steps (docs/RELEASE.md, "Android"):

1. Two encrypted offline backups of the whole directory, kept in two places,
   with the passwords in your password manager. For example:
     tar -C "$(dirname "$dir")" -cf - "$(basename "$dir")" | gpg --symmetric --cipher-algo AES256 -o android-keys.tar.gpg
   then copy android-keys.tar.gpg to two USB sticks / offline media. Check one
   restores (gpg -d android-keys.tar.gpg | tar -t) before relying on it.

2. GitHub environment secrets. Create the environment first (repo Settings >
   Environments > New environment "android-release"), then run these yourself
   (the password commands prompt for the value; paste it there):
     base64 -w0 "$dir/foss.p12"   | gh secret set ANDROID_FOSS_KEYSTORE_B64   --env android-release
     gh secret set ANDROID_FOSS_STORE_PASSWORD   --env android-release
     base64 -w0 "$dir/upload.p12" | gh secret set ANDROID_UPLOAD_KEYSTORE_B64 --env android-release
     gh secret set ANDROID_UPLOAD_STORE_PASSWORD --env android-release
     gh secret list --env android-release

3. Record the SHA-256 fingerprints above in docs/RELEASE.md ("Signing
   certificates") so users can check the GitHub APK with
   'apksigner verify --print-certs', and use the FOSS one for developer
   verification.
EOF
