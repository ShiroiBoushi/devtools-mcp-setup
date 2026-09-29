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


def claude_desktop_config_path() -> Path:
    system = platform.system()
    if system == "Windows":
        return Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"
    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    else:
        # Unofficial/Linux community builds vary; this is the most common location.
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def configure_claude_desktop(port: int):
    config_path = claude_desktop_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if config_path.exists():
        backup_path = config_path.with_suffix(".json.bak")
        shutil.copy2(config_path, backup_path)
        print(f"Existing config backed up to: {backup_path}")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            print("WARNING: existing config file is not valid JSON. "
                  "Aborting so nothing gets overwritten — fix or remove it "
                  "manually, then re-run.")
            sys.exit(1)
    else:
        data = {}

    data.setdefault("mcpServers", {})
    data["mcpServers"].update(mcp_config_snippet(port))

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Updated: {config_path}")
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
    ap.add_argument("--print-config-only", action="store_true",
                     help="Just print the MCP config snippet for the given port; don't launch anything or touch any file.")
    args = ap.parse_args()

    if args.print_config_only:
        print(json.dumps({"mcpServers": mcp_config_snippet(args.port)}, indent=2))
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
        configure_claude_desktop(args.port)


if __name__ == "__main__":
    main()
