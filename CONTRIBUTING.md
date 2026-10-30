# Contributing to Chord Notepad

Thanks for helping. Bug reports, fixes, translations of the help and new
features are all welcome. For anything bigger than a small fix, open an issue
first so we can agree on the approach before you spend time on it.

## Licence of your contribution

Chord Notepad is licensed under the [GNU AGPL-3.0](LICENSE) together with the
additional permissions and terms in [LICENSE.ADDITIONAL](LICENSE.ADDITIONAL).
They let the app use app stores' purchase libraries and be distributed through
app stores, and they keep the "Chord Notepad" name and icon for the original
project.

By submitting a contribution (a pull request, a patch or code in an issue),
you agree that:

- it's licensed under the GNU AGPL-3.0 together with the additional
  permissions and terms in LICENSE.ADDITIONAL, and
- you wrote it, or otherwise have the right to submit it under those terms.

You keep the copyright in your contribution. You don't need to sign anything.
Signing off your commits (`git commit -s`) is welcome but not required.

If your contribution includes code from somewhere else, say where it came from
and what licence it's under, so it can be checked and credited.

## Before you send a pull request

- Run the tests: `make test`.
- Add or update tests for what you changed.
- If you changed what users see, update the user guide in `help/`
  (see [docs/HELP_AUTHORING.md](docs/HELP_AUTHORING.md)) and check that
  `make docs-check` passes.
- Code style: see "Code Conventions" in [CLAUDE.md](CLAUDE.md) and the
  architecture notes in [README.md](README.md). The Android app's notes are in
  [docs/ANDROID.md](docs/ANDROID.md).
