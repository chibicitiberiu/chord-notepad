# T session log: TestFlight smoke

Copy this outside the repository as `T<n>-<date>.md` and fill it in during
the session. docs/IOS.md, "T".

- Date, start and end time:
- Her consent:
- TestFlight build (version, build number, commit) and its expiry:
- `readiness.py T` result:
- iPhone model, iOS version; headphones or Bluetooth used:
- Screen recording on? File name:

## Checklist

Each row: OK, or what happened (with the recording's time).

| # | Check | Result | Time in recording |
|---|---|---|---|
| 1 | Install from TestFlight, first launch: the tour over the quick-start song |  |  |
| 2 | Tap a chord: it sounds, delay felt |  |  |
| 3 | Play, pause, play again |  |  |
| 4 | Home, back to the app: still playing or paused as expected |  |  |
| 5 | Silent switch on, then off, while playing |  |  |
| 6 | Headphones or Bluetooth connected and removed while playing |  |  |
| 7 | An alarm or timer goes off while playing |  |  |
| 8 | ☰ › Diagnostics › Export diagnostics, sent to him |  |  |
| 9 | TestFlight feedback: a screenshot with a comment |  |  |

Then the session's numbered issue list, each with what happened against
its expected result:

1.

## After

- [ ] `pull_testflight_feedback.py --out <folder>` run
- [ ] crashes symbolicated (`symbolicate.sh`, the run's `ios-testflight-dsyms`)
- [ ] diagnostics zip and recording filed with this log
- [ ] new issues added to the list for the next session
