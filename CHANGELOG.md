# Changelog

<!--
This file holds release notes for the *next* full release.
Write entries here as you work. When a full release is published, the contents
of this file are used as the GitHub release description, then automatically
moved to CHANGELOG_HISTORY.md and this file is reset.
-->

### Added

- **Windows:** Release builds are now code-signed with Azure Trusted Signing.
  This clears the SmartScreen "unknown publisher" warning and lets the app
  launch on machines that enforce Windows Application Control (WDAC / Smart App
  Control), which previously blocked the unsigned executable.
