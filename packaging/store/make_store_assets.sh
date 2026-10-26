#!/usr/bin/env bash
# Render the Microsoft Store listing images.
#
# Usage: packaging/store/make_store_assets.sh [photo.jpg] [out_dir]
#
# Always renders the tile icons (from the app's SVG icon). With a photo it also
# renders the hero, poster and box art in the style of the tibich.com project
# poster: the photo darkened to ~57% and slightly desaturated, the app icon and
# the name in white Comfortaa with a soft shadow. The photo used for the listing
# is Pixabay #1655558 by Steve Buissinne ("stevepb-piano-1655558.jpg").
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
svg="$here/../../resources/chord-notepad-icon.svg"
photo="${1:-}"
out="${2:-$here/out}"
mkdir -p "$out"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# Store display tile icons (1:1): icon on a transparent background with a
# little breathing room so it isn't cropped by the Store's rounded tiles.
for size in 300 150 71; do
  inner=$(( size * 88 / 100 ))
  magick -background none -density 1200 "$svg" -resize "${inner}x${inner}" \
    -gravity center -extent "${size}x${size}" "$out/tile-${size}.png"
done

if [[ -z "$photo" ]]; then
  echo "Wrote tile icons to $out (pass a photo for hero/poster/box art)"
  exit 0
fi

# Crop the photo to WxH (centered), darken it like the website poster.
background() {  # width height dest
  magick "$photo" -resize "${1}x${2}^" -gravity center -extent "${1}x${2}" \
    -modulate 100,90 -evaluate multiply 0.57 "$3"
}

# White title text with a soft drop shadow, scaled to the point size.
title() {  # text pointsize dest
  local blur=$(( $2 / 20 + 2 )) drop=$(( $2 / 40 + 1 ))
  magick -background none -fill white -font Comfortaa-Bold -pointsize "$2" \
    -gravity center label:"$1" \
    \( +clone -background black -shadow "55x${blur}+0+${drop}" \) +swap \
    -background none -layers merge +repage "$3"
}

icon() {  # size dest
  magick -background none -density 2400 "$svg" -resize "${1}x${1}" "$2"
}

# 16:9 super hero art: the photo only (the Store forbids the product title).
background 3840 2160 "$out/hero-3840x2160.png"

# 9:16 poster art: icon above a two-line name.
background 1440 2160 "$tmp/poster-bg.png"
icon 520 "$tmp/icon-poster.png"
title $'Chord\nNotepad' 230 "$tmp/title-poster.png"
magick "$tmp/poster-bg.png" \
  "$tmp/icon-poster.png" -gravity north -geometry +0+560 -composite \
  "$tmp/title-poster.png" -gravity north -geometry +0+1130 -composite \
  "$out/poster-1440x2160.png"

# 1:1 box art: icon above the name on one line.
background 2160 2160 "$tmp/box-bg.png"
icon 640 "$tmp/icon-box.png"
title 'Chord Notepad' 210 "$tmp/title-box.png"
magick "$tmp/box-bg.png" \
  "$tmp/icon-box.png" -gravity north -geometry +0+560 -composite \
  "$tmp/title-box.png" -gravity north -geometry +0+1280 -composite \
  "$out/box-2160x2160.png"

echo "Wrote: $(ls "$out" | tr '\n' ' ')"
