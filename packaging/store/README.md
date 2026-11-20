# Store listing assets

Everything uploaded to a store's listing lives here, one folder per store. Files
marked "generated" are made by the command in the last column; don't edit them by
hand.

The hero, poster, box art and Snap banner are drawn over a photo that is not in
the repo. It is Pixabay #1655558 by Steve Buissinne (Pixabay Content License),
and the licence forbids redistributing the photo on its own, so only the
finished images are committed. Download it from pixabay.com and pass its path to
`make_store_assets.sh`.

## Microsoft Store (Partner Center)

| File | Field | Size | Made by |
|---|---|---|---|
| `msstore/listing-ro-RO.txt` | Store listings > Romanian (see the `==` section headings in the file) | text | hand-written |
| `msstore/whats-new/<version>.txt` | Store listings > each language > What's new in this version (1500 characters) | text | hand-written; check with `python3 packaging/store/msstore/count_whats_new.py` |
| `msstore/graphics/tile-71.png`, `tile-150.png`, `tile-300.png` | Store logos: 1:1 box art tiles | 71, 150, 300 px square | `make_store_assets.sh` |
| `msstore/graphics/hero-3840x2160.png` | Super hero art (16:9, no title allowed) | 3840x2160 | `make_store_assets.sh photo.jpg` |
| `msstore/graphics/poster-1440x2160.png` | Poster art (9:16) | 1440x2160 | `make_store_assets.sh photo.jpg` |
| `msstore/graphics/box-2160x2160.png` | Box art (1:1) | 2160x2160 | `make_store_assets.sh photo.jpg` |
| `screenshots/desktop/` | Screenshots | 1920x1080 | see [screenshots/README.md](screenshots/README.md) |

## Google Play

| File | Field | Size | Made by |
|---|---|---|---|
| `play/listing-en-US.txt` | Main store listing: title, short and full description | text | hand-written; check with `python3 packaging/store/play/count_listing.py` |
| `play/graphics/icon-512.png` | App icon | 512x512 | `python3 android/tools/make_play_graphics.py` |
| `play/graphics/feature-graphic.png` | Feature graphic | 1024x500 | `python3 android/tools/make_play_graphics.py` |
| `play/screenshots/{phone,tablet7,tablet10}/` | Phone and tablet screenshots | see its README | see [play/screenshots/README.md](play/screenshots/README.md) |

## Snap Store

| File | Field | Size | Made by |
|---|---|---|---|
| `snap/banner-3000x1000.jpg` | Banner image (under 2 MB) | 3000x1000 | `make_store_assets.sh photo.jpg` |

## AppStream metainfo (Flatpak, Linux software centres)

`packaging/linux/io.github.chibicitiberiu.ChordNotepad.metainfo.xml` links the
desktop screenshots by raw GitHub URL on `main`, so `screenshots/desktop/` must
stay where it is: released versions of the metainfo point at it.

## Rendering the graphics

```bash
packaging/store/make_store_assets.sh /path/to/stevepb-piano-1655558.jpg
```

Needs ImageMagick (`magick`) and the Comfortaa font. Without a photo it renders
only the three tiles.
