# Desktop store screenshots

Made from the real Qt window by `packaging/tools/qt_help_screenshots.py`
(offscreen, a throwaway profile, no sound). Don't edit the PNGs by hand.
Full-colour, 1920x1080. Each shot comes in the light theme (`NN-name.png`) and
the dark theme (`NN-name-dark.png`, the same scene). Songs: Scarborough Fair
(traditional) and Amazing Grace (John Newton, 1779), both public domain.

```bash
# all twelve (light and dark)
pipenv run python packaging/tools/qt_help_screenshots.py --only 01-play-piano-roll,02-edit,03-play-fret-cards,04-play-staff,05-identifier,06-voicings
# one theme only
pipenv run python packaging/tools/qt_help_screenshots.py --theme dark --only 04-play-staff
```

| Light | Dark | Shows |
|---|---|---|
| `desktop/01-play-piano-roll.png` | `desktop/01-play-piano-roll-dark.png` | Play workspace, Amazing Grace mid-playback on the piano roll |
| `desktop/02-edit.png` | `desktop/02-edit-dark.png` | Edit workspace, Scarborough Fair with the Directives sidebar |
| `desktop/03-play-fret-cards.png` | `desktop/03-play-fret-cards-dark.png` | Play workspace, guitar fret cards, mid-playback |
| `desktop/04-play-staff.png` | `desktop/04-play-staff-dark.png` | Play workspace, the staff view, mid-playback |
| `desktop/05-identifier.png` | `desktop/05-identifier-dark.png` | The chord identifier with A C E G entered |
| `desktop/06-voicings.png` | `desktop/06-voicings-dark.png` | Settings, Voicings, a new fretboard voicing |

Where they are used: the AppStream metainfo (`<screenshots>`, raw GitHub
URLs on `main`, so they show once the images are pushed), the Microsoft Store
listing and the Snap Store listing (uploaded by hand). The Microsoft Store takes
PNGs of at least 1366x768.
