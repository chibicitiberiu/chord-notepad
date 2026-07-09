# Changelog

<!--
This file holds release notes for the *next* full release.
Write entries here as you work. When a full release is published, the contents
of this file are used as the GitHub release description, then automatically
moved to CHANGELOG_HISTORY.md and this file is reset.
-->

### Fixed

- **Windows:** Fixed a startup failure where bundled runtime libraries such as
  `ucrtbase.dll` were rejected with a "Bad Image" error (status `0xc0e90002`).
  UPX executable compression was rewriting these DLLs and stripping their
  signatures; it is now disabled so the original signed libraries ship intact.
