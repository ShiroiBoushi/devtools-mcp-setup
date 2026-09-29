#!/usr/bin/env python3
"""
setup_devtools_mcp.py
======================

Cross-platform helper to:
  1. Detect installed Chromium-based browsers (Chrome, Edge, Brave, Opera,
     Opera GX, Vivaldi, Chromium) on Windows / macOS / Linux.
  2. Launch a chosen browser with --remote-debugging-port and a dedicated,
     throwaway profile directory (never your real/default profile).
  3. Optionally register the "chrome-devtools-mcp" server in Claude
     Desktop's config file (claude_desktop_config.json), pointed at that
     debugging port.

This script does NOT touch your real browser profile, does NOT read your
saved passwords/cookies from your normal profile, and does NOT send any
data anywhere except what you explicitly do afterwards in the browser
window it opens. It only spawns a local process and (optionally) edits a
local JSON config file — with a backup made first.

Usage examples
--------------
  # Just list what's installed and detected
  python3 setup_devtools_mcp.py --list

  # Launch Opera GX with debugging on default port 9222
  python3 setup_devtools_mcp.py --browser opera-gx

  # Launch Chrome on a custom port and profile dir
  python3 setup_devtools_mcp.py --browser chrome --port 9333 \\
      --profile-dir ~/devtools-debug-profile

  # Launch + also write/merge the MCP server entry into Claude Desktop's config
  python3 setup_devtools_mcp.py --browser opera-gx --configure-claude-desktop

  # Only print the config snippet, don't touch any file or launch anything
  python3 setup_devtools_mcp.py --browser edge --print-config-only

  # Find every claude_desktop_config.json on this system (handles packaged/
  # Microsoft Store installs under AppData\\Local\\Packages\\...)
  python3 setup_devtools_mcp.py --find-config

  # Remove the chrome-devtools entry from Claude Desktop's config
  python3 setup_devtools_mcp.py --remove-claude-desktop

  # Same, but for a specific config file (if multiple were found)
  python3 setup_devtools_mcp.py --remove-claude-desktop --config-path "C:\\Users\\you\\AppData\\Local\\Packages\\Claude_xxx\\LocalCache\\Roaming\\Claude\\claude_desktop_config.json"
"""
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_PORT = 9222

# --------------------------------------------------------------------------
# Known install locations per browser, per OS. Values are template strings;
# {home} / {localappdata} / {programfiles} are filled in at runtime.
# --------------------------------------------------------------------------
BROWSER_PATHS = {
    "Windows": {
        "chrome": [
            r"{programfiles}\Google\Chrome\Application\chrome.exe",
            r"{programfilesx86}\Google\Chrome\Application\chrome.exe",
            r"{localappdata}\Google\Chrome\Application\chrome.exe",
        ],
        "edge": [
            r"{programfiles}\Microsoft\Edge\Application\msedge.exe",
            r"{programfilesx86}\Microsoft\Edge\Application\msedge.exe",
        ],
        "brave": [
            r"{programfiles}\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"{localappdata}\BraveSoftware\Brave-Browser\Application\brave.exe",
        ],
        "opera": [
            r"{localappdata}\Programs\Opera\opera.exe",
            r"{programfiles}\Opera\opera.exe",
        ],
        "opera-gx": [
            r"{localappdata}\Programs\Opera GX\opera.exe",
            r"{programfiles}\Opera GX\opera.exe",
        ],
        "vivaldi": [
            r"{localappdata}\Vivaldi\Application\vivaldi.exe",
            r"{programfiles}\Vivaldi\Application\vivaldi.exe",
        ],
        "chromium": [
            r"{localappdata}\Chromium\Application\chrome.exe",
        ],
    },
    "Darwin": {  # macOS
        "chrome": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
        "edge": ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"],
        "brave": ["/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"],
        "opera": ["/Applications/Opera.app/Contents/MacOS/Opera"],
        "opera-gx": ["/Applications/Opera GX.app/Contents/MacOS/Opera GX"],
        "vivaldi": ["/Applications/Vivaldi.app/Contents/MacOS/Vivaldi"],
        "chromium": ["/Applications/Chromium.app/Contents/MacOS/Chromium"],
    },
    "Linux": {
        "chrome": ["google-chrome", "google-chrome-stable"],
        "edge": ["microsoft-edge", "microsoft-edge-stable"],
        "brave": ["brave-browser"],
        "opera": ["opera"],
        "opera-gx": ["opera-gx"],  # rare on Linux, but some builds exist
        "vivaldi": ["vivaldi", "vivaldi-stable"],
        "chromium": ["chromium", "chromium-browser"],
    },
}

DISPLAY_NAMES = {
    "chrome": "Google Chrome",
    "edge": "Microsoft Edge",
    "brave": "Brave",
    "opera": "Opera",
    "opera-gx": "Opera GX",
    "vivaldi": "Vivaldi",
    "chromium": "Chromium",
}


def expand_windows_path(template: str) -> str:
    return template.format(
        programfiles=os.environ.get("ProgramFiles", r"C:\Program Files"),
        programfilesx86=os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        localappdata=os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")),
        home=str(Path.home()),
    )


def detect_browsers() -> dict:
    """Return {browser_key: resolved_executable_path} for everything found."""
    system = platform.system()
    candidates = BROWSER_PATHS.get(system, {})
    found = {}

    for key, paths in candidates.items():
        for p in paths:
            if system == "Windows":
                resolved = expand_windows_path(p)
                if os.path.isfile(resolved):
                    found[key] = resolved
                    break
            elif system == "Darwin":
                if os.path.isfile(p):
                    found[key] = p
                    break
            else:  # Linux: these are command names, resolve via PATH
                resolved = shutil.which(p)
                if resolved:
                    found[key] = resolved
                    break
    return found


def launch_browser(exe_path: str, port: int, profile_dir: str):
    profile_path = Path(profile_dir).expanduser().resolve()
    profile_path.mkdir(parents=True, exist_ok=True)

    args = [
        exe_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_path}",
        "--no-first-run",
        "--no-default-browser-check",
    ]

    print(f"Launching:\n  {exe_path}")
    print(f"  --remote-debugging-port={port}")
    print(f"  --user-data-dir={profile_path}")
    print()
    print("This is a SEPARATE, throwaway profile — not your everyday browser "
          "profile, and it starts logged out of everything.")
    print(f"Once it opens, verify at: http://127.0.0.1:{port}/json/version")

    # Detach so this script can exit while the browser keeps running.
    if platform.system() == "Windows":
        subprocess.Popen(args, creationflags=subprocess.DETACHED_PROCESS)
    else:
        subprocess.Popen(args, start_new_session=True)


def mcp_config_snippet(port: int) -> dict:
    return {
        "chrome-devtools": {
            "command": "npx",
            "args": [
                "-y",
                "chrome-devtools-mcp@latest",
                f"--browserUrl=http://127.0.0.1:{port}",
            ],
        }
    }


def candidate_claude_desktop_config_paths() -> list:
    """Return every plausible location for claude_desktop_config.json on this
    OS, in priority order. Covers both the standard installer layout and the
    packaged/sandboxed layout (e.g. Microsoft Store builds land under
    AppData\\Local\\Packages\\Claude_<hash>\\LocalCache\\Roaming\\Claude)."""
    system = platform.system()
    candidates = []

    if system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        localappdata = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))

        # Standard (non-packaged) installer location
        if appdata:
            candidates.append(Path(appdata) / "Claude" / "claude_desktop_config.json")

        # Packaged/sandboxed (Microsoft Store-style) location — package folder
        # name includes a publisher hash that varies per install, so glob it.
        packages_dir = Path(localappdata) / "Packages"
        if packages_dir.is_dir():
            for entry in packages_dir.glob("Claude_*"):
                candidates.append(
                    entry / "LocalCache" / "Roaming" / "Claude" / "claude_desktop_config.json"
                )

    elif system == "Darwin":
        candidates.append(
            Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        )
    else:
        # Unofficial/Linux community builds vary; this is the most common location.
        candidates.append(Path.home() / ".config" / "Claude" / "claude_desktop_config.json")

    return candidates


def find_claude_desktop_config(explicit_path: str = None) -> Path:
    """Resolve the config path to use. If explicit_path is given, use it
    as-is (created if it doesn't exist yet). Otherwise scan all candidate
    locations: if exactly one exists, use it; if several exist, refuse to
    guess and ask the user to disambiguate with --config-path; if none
    exist, fall back to the first (standard) candidate so a fresh config
    can be created there."""
    if explicit_path:
        return Path(explicit_path).expanduser().resolve()

    candidates = candidate_claude_desktop_config_paths()
    existing = [c for c in candidates if c.is_file()]

    if len(existing) == 1:
        return existing[0]

    if len(existing) > 1:
        print("Multiple claude_desktop_config.json files found on this system:")
        for c in existing:
            print(f"  {c}")
        print("\nRe-run with --config-path \"<one of the paths above>\" to pick one.")
        sys.exit(1)

    # None found: fall back to the standard location (will be created).
    return candidates[0] if candidates else Path.home() / "claude_desktop_config.json"


def load_config_safely(config_path: Path) -> dict:
    """Load JSON config, aborting (never overwriting) if it's malformed."""
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"WARNING: {config_path} is not valid JSON. "
              "Aborting so nothing gets overwritten — fix or remove it "
              "manually, then re-run.")
        sys.exit(1)


def backup_config(config_path: Path):
    if config_path.exists():
        backup_path = config_path.with_suffix(".json.bak")
        shutil.copy2(config_path, backup_path)
        print(f"Existing config backed up to: {backup_path}")


def configure_claude_desktop(port: int, config_path: Path):
    config_path.parent.mkdir(parents=True, exist_ok=True)
    backup_config(config_path)
    data = load_config_safely(config_path)

    data.setdefault("mcpServers", {})
    data["mcpServers"].update(mcp_config_snippet(port))

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Updated: {config_path}")
    print("Restart Claude Desktop for the change to take effect.")


def remove_claude_desktop(config_path: Path, server_name: str = "chrome-devtools"):
    if not config_path.exists():
        print(f"No config file found at: {config_path}")
        print("Nothing to remove.")
        return

    data = load_config_safely(config_path)
    servers = data.get("mcpServers", {})

    if server_name not in servers:
        print(f"'{server_name}' is not present in: {config_path}")
        print("Nothing to remove.")
        return

    backup_config(config_path)
    del servers[server_name]
    data["mcpServers"] = servers

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Removed '{server_name}' from: {config_path}")
    print("Every other configured server was left untouched.")
    print("Restart Claude Desktop for the change to take effect.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="List detected browsers and exit.")
    ap.add_argument("--browser", choices=list(DISPLAY_NAMES.keys()),
                     help="Which browser to launch with remote debugging.")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Remote debugging port (default {DEFAULT_PORT}).")
    ap.add_argument("--profile-dir", default=None,
                     help="Dedicated profile directory to use (default: a new temp dir).")
    ap.add_argument("--configure-claude-desktop", action="store_true",
                     help="Also merge the chrome-devtools-mcp entry into Claude Desktop's config (backs up the existing file first).")
    ap.add_argument("--remove-claude-desktop", action="store_true",
                     help="Remove the chrome-devtools entry from Claude Desktop's config (backs up first, leaves other servers untouched). Does not launch a browser.")
    ap.add_argument("--config-path", default=None,
                     help="Explicit path to claude_desktop_config.json, overriding auto-detection. Use this if --find-config shows multiple candidates, or auto-detection can't find yours (e.g. non-standard/packaged install).")
    ap.add_argument("--find-config", action="store_true",
                     help="List every claude_desktop_config.json found on this system (standard and packaged/Microsoft-Store install locations) and exit.")
    ap.add_argument("--print-config-only", action="store_true",
                     help="Just print the MCP config snippet for the given port; don't launch anything or touch any file.")
    args = ap.parse_args()

    if args.print_config_only:
        print(json.dumps({"mcpServers": mcp_config_snippet(args.port)}, indent=2))
        return

    if args.find_config:
        candidates = candidate_claude_desktop_config_paths()
        existing = [c for c in candidates if c.is_file()]
        if not existing:
            print("No claude_desktop_config.json found in any known location.")
            print("Checked:")
            for c in candidates:
                print(f"  {c}")
        else:
            print("Found:")
            for c in existing:
                print(f"  {c}")
        return

    if args.remove_claude_desktop:
        config_path = find_claude_desktop_config(args.config_path)
        remove_claude_desktop(config_path)
        return

    found = detect_browsers()

    if args.list or not args.browser:
        if not found:
            print("No supported Chromium-based browsers detected automatically.")
            print("Supported keys: " + ", ".join(DISPLAY_NAMES.keys()))
        else:
            print("Detected browsers:")
            for key, path in found.items():
                print(f"  {key:10s} -> {DISPLAY_NAMES[key]:15s} ({path})")
        if not args.browser:
            print("\nPass --browser <key> to launch one, e.g. --browser opera-gx")
            return

    if args.browser not in found:
        print(f"'{args.browser}' was not found automatically on this system.")
        print("You can still launch it manually with:")
        print(f'  "<path-to-{args.browser}-executable>" --remote-debugging-port={args.port} '
              f'--user-data-dir="<a-new-empty-folder>"')
        sys.exit(1)

    profile_dir = args.profile_dir or str(Path(tempfile.gettempdir()) / f"devtools-mcp-profile-{args.browser}")
    launch_browser(found[args.browser], args.port, profile_dir)

    print()
    print("Claude Desktop / Claude Code MCP config for this session:")
    print(json.dumps({"mcpServers": mcp_config_snippet(args.port)}, indent=2))

    if args.configure_claude_desktop:
        print()
        config_path = find_claude_desktop_config(args.config_path)
        configure_claude_desktop(args.port, config_path)


if __name__ == "__main__":
    main()
