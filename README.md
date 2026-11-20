# AEGIS AFK Watch (app)

A small Windows app for BendersMC staff that tells you when you have gone AFK. It is the display half of a pair: the **AEGIS AFK Bridge** mod (separate download) sees what is happening in the game and publishes it to a local file, and this app reads that file. The app never touches the game.

- **Outside the AFK server:** after 2:00 idle the window turns orange, then red, and the wording escalates (default steps: 2:00, 3:00, 5:00).
- **Inside the AFK server:** a calm blue AFK timer once you have been idle 15 seconds. No warnings.
- **Disconnect, crash or game exit while idle:** shows "Disconnected" and how long you had been idle. It does not reconnect for you.
- **Window:** small, borderless, always on top, never steals focus. Drag it anywhere; right-click for options. Exit from the tray icon.

## How the two halves talk

```
game + Bridge mod  --writes once a second-->  %APPDATA%\AegisAfkWatch\bridge.json  <--reads--  this app
```

The file holds only: connected yes/no, the server address, the gamemode name the network last sent you to, how long you have been idle in the game, a connection counter, and a timestamp. It is a plain local file: no network, no ports, no passwords or tokens. If the timestamp stops refreshing for 5 seconds, the app concludes the game closed or crashed.

Nothing is sent to the game, no process is hooked, and the app stores nothing except its own `settings.json`.

## Settings

`%APPDATA%\AegisAfkWatch\settings.json`, created on first run (tray icon > Open settings file). Restart the app to apply changes.

| Key | Default | Meaning |
|---|---|---|
| `serverHostFragments` | `["benders"]` | The server address must contain one of these. Add the exact host if needed. |
| `afkServerNames` | `["afk"]` | Gamemode names that count as the AFK server (case-insensitive). |
| `warningStepsSeconds` | `[120, 180, 300]` | Idle seconds at which each warning level starts. First entry = when warnings begin. |
| `afkServerAfterSeconds` | `15` | Idle seconds before the AFK server turns blue. Also the minimum idle time for a drop to be flagged. |
| `disconnectLingerSeconds` | `600` | How long "Disconnected" stays up. |
| `bridgeStaleSeconds` | `5` | How long without a fresh report before the game counts as gone. |
| `windowShowWhenActive`, `windowAlwaysOnTop`, `windowOpacity`, `windowX`, `windowY`, `beepOnWarning` | | Window behaviour. Position is saved when you drag it. |

## Limits

- Windows only. The window cannot appear over true exclusive fullscreen; use windowed or borderless fullscreen.
- The mod learns the gamemode from the network's "Sending you to X now..." line. If you connect and land straight in the AFK server without that line, it assumes you are elsewhere until your next switch.
- A game freeze longer than `bridgeStaleSeconds` looks like a crash; it recovers by itself when the game wakes up.

## Building

Push to GitHub. `.github/workflows/build.yml` publishes a single self-contained `AegisAfkWatch.exe` (about 60 MB, nothing to install) and uploads it as a build artifact. Locally: `dotnet publish -c Release -o publish` with the .NET 10 SDK.

## Per-version checklist

On every Minecraft, AEGIS or .NET bump, record the result in the changelog:

1. The exe builds and starts with no console window; the mod builds and loads in AEGIS.
2. With the game closed, nothing shows. Join BendersMC: `bridge.json` appears and updates about once a second.
3. Green while active, orange at 2:00, red by 3:00, blue in the AFK server.
4. Kill the game while idle: "Disconnected" appears. Quit normally while active: nothing appears.
5. Nothing in the exe, the mod, `settings.json` or `bridge.json` contains a token or personal data.

## Layout

```
Core/      Session (state machine), Settings, Palette, Indicator. No Windows or file access.
Sources/   BridgeReader (reads bridge.json) and Watcher (turns reports into events).
Ui/        StatusForm (the window), TrayContext (tray icon and exit).
```
