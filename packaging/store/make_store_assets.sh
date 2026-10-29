#!/usr/bin/env bash
# Render the Microsoft Store listing images, the Snap Store banner and the
# Google Play icon and feature graphic.
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

# 3:1 Snap Store banner: icon beside the name, as one centred row. JPEG,
# since the store caps banners at 2MB.
background 3000 1000 "$tmp/banner-bg.png"
icon 400 "$tmp/icon-banner.png"
title 'Chord Notepad' 190 "$tmp/title-banner.png"
magick "$tmp/icon-banner.png" \( "$tmp/title-banner.png" -background none -gravity west -splice 70x0 \) \
  -background none -gravity center +append "$tmp/row-banner.png"
magick "$tmp/banner-bg.png" "$tmp/row-banner.png" -gravity center -composite \
  -quality 90 "$out/snap-banner-3000x1000.jpg"

# Google Play: 512 px icon. Play rounds the corners itself, so this is the
# full square: the notepad on the launcher icon's cream background
# (android/tools/make_launcher_icons.py), a little larger than in the
# adaptive icon since no circular mask applies.
magick -size 512x512 xc:'#FDF0EB' \
  \( -background none -density 2400 "$svg" -trim -resize 340x340 \) \
  -gravity center -composite -alpha off "$out/play-icon-512.png"

# Google Play feature graphic, 1024x500: icon beside the name, like the Snap
# banner. Play wants JPEG or 24-bit PNG without alpha.
background 1024 500 "$tmp/feature-bg.png"
icon 190 "$tmp/icon-feature.png"
title 'Chord Notepad' 88 "$tmp/title-feature.png"
magick "$tmp/icon-feature.png" \( "$tmp/title-feature.png" -background none -gravity west -splice 34x0 \) \
  -background none -gravity center +append "$tmp/row-feature.png"
magick "$tmp/feature-bg.png" "$tmp/row-feature.png" -gravity center -composite \
  -alpha off -quality 92 "$out/play-feature-1024x500.jpg"

echo "Wrote: $(ls "$out" | tr '\n' ' ')"
