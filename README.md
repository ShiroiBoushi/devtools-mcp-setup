# devtools-mcp-setup

A small cross-platform helper script to configure [`chrome-devtools-mcp`](https://github.com/ChromeDevTools/chrome-devtools-mcp) against any Chromium-based browser — Chrome, Edge, Brave, Opera, Opera GX, Vivaldi, or Chromium — instead of manually hunting down install paths and remote-debugging flags every time.

It launches your chosen browser with a **dedicated, throwaway profile** and remote debugging enabled, and can optionally merge the corresponding MCP server entry into your Claude Desktop config.

## What it does

- Detects installed Chromium-based browsers on Windows, macOS, and Linux
- Launches the one you pick with `--remote-debugging-port` and a fresh `--user-data-dir` (never your everyday profile)
- Prints the exact MCP config snippet for `chrome-devtools-mcp`
- Locates `claude_desktop_config.json` automatically — including packaged/Microsoft Store installs, which live under a different path than the standard installer
- Optionally merges that snippet into the config (for Claude Desktop) — additively, without touching your other configured servers
- Optionally removes the `chrome-devtools` entry again, leaving every other server untouched

## What it does *not* do

- It does **not** read, copy, or reuse your real browser profile, cookies, or saved passwords
- It does **not** send anything over the network itself — it only starts a local process
- It does **not** overwrite other MCP servers already in your config
- It does **not** modify Claude Code's config directly (see [Claude Code](#claude-code) below)
- It does **not** start or stop anything on its own after it exits — Claude Desktop spawns and kills the `chrome-devtools-mcp` process itself, tied to its own lifecycle (see [Runtime behavior](#runtime-behavior) below)

## Requirements

- Python 3.9+
- Node.js 20+ and `npx` (needed by `chrome-devtools-mcp` itself, not by this script)
- One of the supported browsers installed

## Usage

```bash
# See what's installed and detected on this machine
python3 setup_devtools_mcp.py --list

# Launch a browser with debugging enabled (default port 9222)
python3 setup_devtools_mcp.py --browser opera-gx

# Custom port and profile directory
python3 setup_devtools_mcp.py --browser chrome --port 9333 --profile-dir ~/devtools-debug-profile

# Launch AND merge the MCP entry into Claude Desktop's config
python3 setup_devtools_mcp.py --browser opera-gx --configure-claude-desktop

# Just preview the config snippet, without launching or writing anything
python3 setup_devtools_mcp.py --print-config-only --port 9222

# Find every claude_desktop_config.json on this system (handles standard
# installer AND packaged/Microsoft Store layouts)
python3 setup_devtools_mcp.py --find-config

# Remove the chrome-devtools entry from Claude Desktop's config
python3 setup_devtools_mcp.py --remove-claude-desktop

# Point at a specific config file (needed if --find-config lists more than
# one, e.g. you have both a standard and a packaged install)
python3 setup_devtools_mcp.py --configure-claude-desktop --config-path "C:\path\to\claude_desktop_config.json"
python3 setup_devtools_mcp.py --remove-claude-desktop --config-path "C:\path\to\claude_desktop_config.json"
```

Supported `--browser` keys: `chrome`, `edge`, `brave`, `opera`, `opera-gx`, `vivaldi`, `chromium`

### Verifying it worked

Once the browser launches, open (in any other browser tab, or via `curl`):

```
http://127.0.0.1:9222/json/version
```

You should see a JSON response. If you get a connection error, the debugging port didn't bind — usually because another instance of the same browser was already running on the default profile. Close all instances of that browser first, then retry.

## Claude Desktop

### Locating the config file

The script checks all known locations for `claude_desktop_config.json`:

- Standard installer: `%APPDATA%\Claude\` (Windows), `~/Library/Application Support/Claude/` (macOS), `~/.config/Claude/` (Linux)
- Packaged/Microsoft Store installs: `%LOCALAPPDATA%\Packages\Claude_<hash>\LocalCache\Roaming\Claude\` (Windows)

Run `--find-config` to see exactly what it finds. If it finds exactly one file, `--configure-claude-desktop` and `--remove-claude-desktop` use it automatically. If it finds more than one (e.g. you have both a standard and a packaged install), it will refuse to guess — pass `--config-path` explicitly to pick one.

### Adding the server

With `--configure-claude-desktop`, the script:

1. Resolves the config path (auto-detected or via `--config-path`)
2. Backs it up to `claude_desktop_config.json.bak` before changing anything
3. Merges in a `chrome-devtools` entry under `mcpServers`, leaving every other entry untouched
4. Refuses to touch the file at all if it isn't valid JSON to begin with

### Removing the server

With `--remove-claude-desktop`, the script:

1. Resolves the config path the same way
2. Backs it up first
3. Deletes only the `chrome-devtools` entry — every other configured server is left exactly as it was
4. Does nothing (and says so) if the entry isn't present

Restart Claude Desktop after adding or removing for the change to take effect.

## Runtime behavior

Claude Desktop owns the MCP server's lifecycle — this script only edits config files and launches the browser, it doesn't manage any running process itself:

- **Claude Desktop starts** → it reads the config and spawns `chrome-devtools-mcp` as a child process
- **Claude Desktop fully quits** (not just the window — check the system tray) → that child process is killed with it
- The debug **browser** you launch with this script is independent of that — it keeps running on its own until you close it, whether or not Claude Desktop is open
- If the browser is closed while the MCP server is still running, tool calls will fail (it can no longer reach `127.0.0.1:<port>`) until you relaunch the browser

There's no standalone service to start/stop directly — to fully stop everything, close both Claude Desktop and the debug browser window.

## Claude Code

This script doesn't modify Claude Code's config directly. After launching the browser, register the server yourself:

```bash
claude mcp add chrome-devtools -- npx -y chrome-devtools-mcp@latest --browserUrl=http://127.0.0.1:9222
```

(swap in your port if you used `--port` to pick a different one)

## Security notes

- Remote debugging gives **full control** of that browser instance — page content, cookies, session tokens, everything. Keep it bound to `127.0.0.1` (the default) and never expose the port on your network.
- Always use a separate profile (the script creates one automatically) and avoid signing into sensitive accounts in it while the debug port is open.
- Close the debug browser instance when you're done with it.
- Only install `chrome-devtools-mcp` from the official npm package; pin a version if you want reproducible behavior.

## Adding a browser or fixing a path

Install locations are defined in the `BROWSER_PATHS` dict at the top of `setup_devtools_mcp.py`. If `--list` doesn't find a browser you have installed, add or correct its path there — PRs welcome.

## License

MIT
