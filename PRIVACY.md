# Privacy Policy

_Last updated: 30 October 2026_

Chord Notepad does not collect or send any personal information. Nothing you
do in the app is shared with the developer or anyone else.

## What the app keeps, and where

- **Your songs** are ordinary text files, saved only where you choose.
- **Settings and a log file** are stored locally on your computer (on Windows
  under `%APPDATA%\ChordNotepad`, or the app's private folder when installed
  from the Microsoft Store). They never leave your computer. The log records
  what the app did, such as which audio driver it started and the paths of
  files you open or save, but not the contents of your songs.

## Android

The Android app follows the same rules, with these specifics:

- **Permissions.** It asks for none. It has no internet permission, so it
  can't connect to anything. Playing audio uses the system's audio focus,
  which needs no permission. The Google Play version also declares Google
  Play's billing permission, which only lets it ask the Play Store app to
  handle the optional supporter purchase; it can't be used to send data.
- **Opening files from other apps.** When you open a `.txt` file with Chord
  Notepad from a file manager, the app gets access to that one file only.
- **Your songs.** The app sees only the files you pick in the system's file
  picker (Open, Save as, Export MIDI). It keeps access to those files so the
  Recent list works; you can revoke that by removing the app.
- **Settings and the log** stay in the app's private storage on your device,
  which other apps can't read. In the Google Play version, the settings also
  hold the date the app last asked for support, so it asks at most once a
  day. The log holds the same kind of information as
  on the desktop (no song contents) and is deleted with the app.
- **Backups.** If Android backup is turned on for your device, Android may
  back up the app's settings (only `settings.json`) to your Google account or
  copy them to a new phone. The log, the recent-files list and the copied
  sound font are excluded. That backup is handled by Google under your
  account's settings; the developer can't see it.
- **The user guide** is built into the app and opens without any network.

## Network

Chord Notepad has no accounts, analytics, telemetry, ads or online features.
It does not connect to the internet. On the desktop, to show the built-in user
guide, it runs a small web server reachable only from your own computer
(127.0.0.1) and opens the guide in your web browser.

## Purchases

If you buy Chord Notepad from the Microsoft Store, the purchase is handled
entirely by Microsoft under the
[Microsoft Privacy Statement](https://privacy.microsoft.com/privacystatement).
The developer receives no personal or payment information from it.

Chord Notepad on Google Play is free. If you make the optional supporter
purchase inside it, the purchase is handled by Google under the
[Google Privacy Policy](https://policies.google.com/privacy). Google gives
the developer order and sales reports (for example the buyer's country,
which taxes depend on); the app itself sends nothing. To show the supporter
badge, the app asks the Play Store app on your phone whether you made the
purchase; that check stays on your device.
The Android download from GitHub has no purchase at all; it links to a
donation page in its About screen, which opens in your browser only if you
tap it.

## Contact

Questions about this policy:
[open an issue on GitHub](https://github.com/chibicitiberiu/chord-notepad/issues).
