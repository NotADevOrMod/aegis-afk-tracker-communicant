# Changelog

## [0.2.0]
- Tells causes apart: a network outage or a server restart is reconnected; a drop where the server never stopped answering (kick, ban, client error) is only reported. `reconnect_on_unknown_drop` opts in to reconnecting after those too.
- Detects a crashed game (crash report, JVM crash log, or vanishing while you were away), a frozen window, and reports them.
- Finds the Reconnect button among one, two or three buttons: scans for the stack, matches by label, requires a clear winner, and logs how many buttons it saw. Calibration measures the GUI scale.
- Refuses a calibration pointed at plain background.
- Defaults tightened: `min_match` 0.9, plus a `match_margin` of 0.08.
- 45 tests, including simulated disconnect screens at GUI scales 1 to 4.

## [0.1.0]
- First build. Replaces the hourly Shift+Tab/Enter script.
