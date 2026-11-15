# Desktop store screenshots

Made from the real Qt window by `packaging/tools/qt_help_screenshots.py`
(offscreen, a throwaway profile, no sound). Don't edit the PNGs by hand.
Full-colour, 1920x1080, light theme unless the name says dark. Songs:
Scarborough Fair (traditional) and Amazing Grace (John Newton, 1779), both
public domain.

```bash
pipenv run python packaging/tools/qt_help_screenshots.py --only 01-play-piano-roll,02-edit,03-play-fret-cards,04-play-staff-dark,05-identifier,06-voicings
```

| File | Shows |
|---|---|
| `desktop/01-play-piano-roll.png` | Play workspace, Amazing Grace mid-playback on the piano roll |
| `desktop/02-edit.png` | Edit workspace, Scarborough Fair with the Directives sidebar |
| `desktop/03-play-fret-cards.png` | Play workspace, guitar fret cards, mid-playback |
| `desktop/04-play-staff-dark.png` | Dark theme, the staff view, mid-playback |
| `desktop/05-identifier.png` | The chord identifier with A C E G entered |
| `desktop/06-voicings.png` | Settings, Voicings, a new fretboard voicing |

Where they are used: the AppStream metainfo (`<screenshots>`, raw GitHub
URLs on `main`, so they show once the images are pushed), the Microsoft Store
listing and the Snap Store listing (uploaded by hand). The Microsoft Store takes
PNGs of at least 1366x768.
