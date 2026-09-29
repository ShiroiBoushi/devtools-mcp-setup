# devtools-mcp-setup

A small cross-platform helper script to configure [`chrome-devtools-mcp`](https://github.com/ChromeDevTools/chrome-devtools-mcp) against any Chromium-based browser — Chrome, Edge, Brave, Opera, Opera GX, Vivaldi, or Chromium — instead of manually hunting down install paths and remote-debugging flags every time.

It launches your chosen browser with a **dedicated, throwaway profile** and remote debugging enabled, and can optionally merge the corresponding MCP server entry into your Claude Desktop config.

## What it does

- Detects installed Chromium-based browsers on Windows, macOS, and Linux
- Launches the one you pick with `--remote-debugging-port` and a fresh `--user-data-dir` (never your everyday profile)
- Prints the exact MCP config snippet for `chrome-devtools-mcp`
- Optionally merges that snippet into `claude_desktop_config.json` (for Claude Desktop) — additively, without touching your other configured servers

## What it does *not* do

- It does **not** read, copy, or reuse your real browser profile, cookies, or saved passwords
- It does **not** send anything over the network itself — it only starts a local process
- It does **not** overwrite other MCP servers already in your config
- It does **not** modify Claude Code's config directly (see [Claude Code](#claude-code) below)

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
```

Supported `--browser` keys: `chrome`, `edge`, `brave`, `opera`, `opera-gx`, `vivaldi`, `chromium`

### Verifying it worked

Once the browser launches, open (in any other browser tab, or via `curl`):

```
http://127.0.0.1:9222/json/version
```

You should see a JSON response. If you get a connection error, the debugging port didn't bind — usually because another instance of the same browser was already running on the default profile. Close all instances of that browser first, then retry.

## Claude Desktop

With `--configure-claude-desktop`, the script:

1. Locates `claude_desktop_config.json` for your OS
2. Backs it up to `claude_desktop_config.json.bak` before changing anything
3. Merges in a `chrome-devtools` entry under `mcpServers`, leaving every other entry untouched
4. Refuses to touch the file at all if it isn't valid JSON to begin with

Restart Claude Desktop after running it for the change to take effect.

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

MIT (or whatever you prefer — update this section before publishing).
