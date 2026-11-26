# AEGIS Reconnect

A small Windows tool that gets you back into the game and the AFK queue after something goes wrong. It checks before it acts and confirms afterwards, instead of pressing keys and hoping.

## What it does about each kind of problem

| What happened | How it tells | What it does |
|---|---|---|
| **Wi-Fi or internet dropped** | Internet checks fail while the game was connected; the game then loses its server connection. | Reconnects. |
| **Server crashed or restarted** | The game lost its connection while your internet is fine, the server then stopped answering, and now answers again. | Reconnects. |
| **Kicked, banned, or a client-side error** | The game lost its connection, your internet is fine, and the server never stopped answering. | **Alerts you and does not reconnect.** |
| **The game crashed** | The game process vanished, with a fresh crash report or JVM crash log, or while you were away. | Alerts you (with which evidence it found). It cannot restart the game. |
| **The game froze** | Windows reports the window as not responding for 20 seconds. | Alerts you. |
| **You closed the game** | The process vanished while you were at the keyboard, with no crash evidence. | Nothing. |

The kick rule matters: reconnecting after being kicked would work around the server's own decision. Turning on `reconnect_on_unknown_drop` makes it reconnect after drops it cannot explain, which includes kicks, so leave it off unless you know why you want it.

## Finding the Reconnect button (one, two or three buttons)

A disconnect screen can have a different number of buttons each time, which moves the others. It does not rely on position:

1. It scans for button faces around the calibrated spot, using the face colour and your GUI scale, and counts them.
2. It compares each button's *label* with the Reconnect label you recorded. Every button has the same face, so the label is what tells them apart.
3. It clicks only if exactly one button clearly looks like Reconnect (90% match, and at least 8 points ahead of the next best). If none match, or two look alike, it refuses and logs how many buttons it saw and how each scored.

The calibration screen can have any number of buttons. `check` and the log tell you what it sees each time.

## Rules it keeps

- Checks the game window is in front before every click and key, so text cannot land in Discord or a browser.
- Waits until you have stopped using the computer (15 seconds by default) before taking over the mouse.
- Gives up after 3 attempts with growing waits, and tells you.
- Confirms the reconnect by watching for the game's server connection to come back.
- Sends nothing over the network except connection checks, and stores no passwords or tokens. Its files are `reconnect.json` (settings and calibration) and `reconnect.log`, in `%APPDATA%\AegisAfkWatch`.

## Setup

1. Push this repo to GitHub. The workflow runs the tests and builds `AegisReconnect.exe` (download it from the run's artifacts).
2. Start the game and join the server. Then **calibrate once**:
   ```
   AegisReconnect.exe calibrate
   ```
   Make the game show its Disconnected screen (turn Wi-Fi off for about 40 seconds), hover over the **Reconnect** button and press **F8**, then move the mouse off the button and press **F8** again. It prints the GUI scale it detected and how many buttons it can see.
3. **Check it** on any Disconnected screen:
   ```
   AegisReconnect.exe check
   ```
   It prints how many buttons are on screen, how well each matches Reconnect, and whether it would click. It sends no input.
4. **Rehearse**: `AegisReconnect.exe run --dry-run`, then turn Wi-Fi off and on. It logs each step and where it would click, but presses nothing.
5. Run it for real: `AegisReconnect.exe`. Leave the window open.

## Settings (`%APPDATA%\AegisAfkWatch\reconnect.json`)

| Key | Default | Meaning |
|---|---|---|
| `server_port` | `25565` | The server's port. `0` means any established connection that is not 80 or 443. |
| `process_names` | `["javaw", "java"]` | Process names that can be the game. |
| `window_title` | `"Minecraft"` | Text the game window's title must contain. Change both if AEGIS names them differently. |
| `internet_targets` | `1.1.1.1:443, 8.8.8.8:53` | Any one answering means "online". |
| `poll_seconds` | `5` | Time between checks. |
| `outage_after_failures` | `3` | Failed checks in a row before an outage is declared. |
| `stable_seconds` | `10` | Internet (or the server) must be steady this long before it counts as back. |
| `grace_seconds` | `60` | After an outage, how long to wait for the game to notice a dead connection. |
| `reconnect_on_unknown_drop` | `false` | Also reconnect after drops with no explanation. This includes kicks. |
| `unknown_drop_seconds` | `20` | How long the server must keep answering before a drop counts as unexplained. |
| `hung_seconds` | `20` | Report a window that has not responded for this long. |
| `crash_idle_seconds` | `60` | A vanished game counts as a probable crash if you had been idle this long. |
| `max_attempts` | `3` | Reconnect attempts per incident. |
| `connect_timeout_seconds` | `60` | How long to wait for the connection after clicking. |
| `join_delay_seconds` | `10` | Pause after reconnecting before typing the command. |
| `min_idle_seconds` | `15` | Wait until you have been idle this long before taking over. `0` disables. |
| `chat_key` | `"T"` | Key that opens chat: one letter or digit, or `/`. |
| `join_command` | `"/joinq AFK"` | What to type. |
| `beep` | `false` | Play a sound when it needs you. |
| `min_match`, `match_margin` | `0.9`, `0.08` | How closely the button must match, and how far ahead of the next button. |
| `colour_tolerance`, `face_tolerance` | `40`, `14` | Colour slack for the label and for the button face. |
| `gui_scale` | `0` | `0` uses the scale measured at calibration. Set it if the detected scale was wrong. |

## Limits

- **Windows only**, and the game must be in windowed or borderless mode. Screen pixels cannot be read from exclusive fullscreen.
- **It cannot restart a crashed game**, or navigate from the title screen back to the server. It tells you what it found.
- **Recalibrate** if you change the GUI scale, resolution, resource pack, or if AEGIS changes the disconnect screen. `check` shows when the match has dropped.
- It tells kicks from restarts by whether the server kept answering, not by reading the message. A server that restarts so fast it never stops answering looks like a kick, so it will not be reconnected.
- It cannot confirm that `/joinq AFK` was accepted; it only confirms the connection and that the command was typed.
- Run it as the same Windows user as the game, or Windows may deny it access to the game's connections.

## Before relying on it

This is an unattended macro that puts you back in the AFK queue. Confirm that your server's rules allow automated reconnecting, and if AFK time counts toward your quotas, that unattended AFK time is allowed to count.

## Per-version checklist

After a Minecraft, AEGIS or Windows update, record the result in the changelog:

1. The tests pass and the exe builds.
2. `check` on a Disconnected screen still says "WOULD CLICK", and the button count matches what you see.
3. Dry run with Wi-Fi off 40 seconds: outage, restored, reconnect needed, and where it would click.
4. A real run recovers once and sends the command.
5. End the game from Task Manager while idle: it reports a crash. Close it normally while at the keyboard: it stays quiet.
6. Nothing in `%APPDATA%\AegisAfkWatch` contains a password or token.

## Layout

```
aegis_reconnect/
  monitor.py      Pure logic: what a lost connection means, and whether to act. Tested.
  crash.py        Pure logic: crash or normal exit. Tested.
  signature.py    Pure logic: matching button labels, finding button stacks. Tested.
  vision.py       Pure logic: choosing the Reconnect button among one to three. Tested on simulated screens.
  config.py       Settings and calibration (JSON).
  winapi.py       The only code that talks to Windows: windows, pixels, mouse, keyboard.
  game.py         Finding the game, its server connection, crash files, the internet check.
  reconnector.py  The recovery sequence.
  calibrate.py    One-time button calibration.
tests/            45 unit tests, including simulated disconnect screens at GUI scales 1 to 4.
```
