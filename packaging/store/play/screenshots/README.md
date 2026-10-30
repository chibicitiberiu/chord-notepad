# Google Play screenshots

Generated on the emulator by `android/tools/help_screenshots.py` from
`android/tools/store_shots.json` (see "Google Play listing screenshots" in
`android/tools/HELP_SHOTS.md`). Don't edit the PNGs by hand. Full-colour RGB
PNGs, no callouts; the demo status bar (9:41) is on. Songs: Scarborough Fair (traditional
verses only) and Amazing Grace (John Newton, 1779), both public domain.

Regenerate everything (about 6 minutes):

```bash
source android/local.env
(cd android && nice -n 10 ./gradlew :app:assemblePlayDebug && ./gradlew --stop)
nice -n 10 python3 android/tools/help_screenshots.py --flavor play --manifest android/tools/store_shots.json
```

One shot: add `--only p-03-staff` (shot names are in `--list`; the prefix is
`p-` phone, `t10-` 10-inch, `t7-` 7-inch).

| Folder | Size | Notes |
|---|---|---|
| `phone/` | 1080x1920 (9:16) | cn_phone with `wm size 1080x1920` (the AVD's own 1080x2400 is beyond Play's 2:1 limit) |
| `tablet10/` | 2560x1600 | cn_tablet at its native size, landscape |
| `tablet7/` | 1920x1200 | the same cn_tablet AVD resized to 1920x1200 at 320 dpi (only one tablet AVD exists), landscape |

## Phone (8)

| File | Shows |
|---|---|
| `01-play-fret-cards.png` | Play tab, Scarborough Fair, guitar fret cards, mid-playback (chord F lit, playhead in the text) |
| `02-edit.png` | Edit tab: ribbon (Insert, Transpose, Identify, AB/Do, Convert), directives, chord highlighting |
| `03-staff.png` | Amazing Grace on the grand staff while playing (Em lit) |
| `04-piano-roll.png` | Scarborough Fair on the piano roll while playing |
| `05-voicing.png` | Voicing sheet: piano, guitars, ukulele, ensembles |
| `06-dark-play.png` | Dark theme, Play tab on the tab view |
| `07-transpose.png` | Transpose dialog (+2 semitones) over Amazing Grace |
| `08-instrument.png` | Instrument sheet, Guitar family, Steel Guitar selected |

## Tablets (4 each, same four scenes)

| File | Shows |
|---|---|
| `01-play-fret-cards.png` | Play tab, text on the left, fret cards and player on the right, mid-playback |
| `02-edit.png` | Edit tab with the ribbon |
| `04-piano-roll.png` | Piano roll while playing (Am lit) |
| `06-dark-play.png` | Dark theme, tab view while playing |
