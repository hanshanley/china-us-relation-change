#!/usr/bin/env python3
"""Install or remove the per-user macOS private-corpus daily refresh."""

import argparse
import os
import plistlib
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LABEL = "com.hanshanley.weibo-refresh"


def configuration(root):
    return {
        "Label": LABEL,
        "ProgramArguments": [str(root / ".venv/bin/python"), str(root / "scripts/refresh_weibo.py"),
                             "--publish", "--push"],
        "WorkingDirectory": str(root),
        "EnvironmentVariables": {
            "PYTHONPATH": str(root / "src"),
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        },
        "StartCalendarInterval": [{"Hour": hour, "Minute": 35} for hour in (3, 9, 15, 21)],
        "RunAtLoad": False,
        "ProcessType": "Background",
        "StandardOutPath": str(root / "data/local/automation/refresh.stdout.log"),
        "StandardErrorPath": str(root / "data/local/automation/refresh.stderr.log"),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remove", action="store_true")
    parser.add_argument("--print", action="store_true", dest="print_only")
    args = parser.parse_args()
    config = configuration(ROOT)
    if args.print_only:
        sys.stdout.buffer.write(plistlib.dumps(config))
        raise SystemExit
    if sys.platform != "darwin":
        parser.error("This installer requires macOS; run refresh_weibo.py with your private scheduler elsewhere")
    path = Path.home() / "Library/LaunchAgents" / (LABEL + ".plist")
    target = f"gui/{os.getuid()}/{LABEL}"
    present = subprocess.run(["launchctl", "print", target], capture_output=True).returncode == 0
    if present:
        subprocess.run(["launchctl", "bootout", target], check=True)
    if args.remove:
        if path.exists():
            path.unlink()
        print("Removed only the Weibo refresh agent.")
    else:
        (ROOT / "data/local/automation").mkdir(parents=True, exist_ok=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(plistlib.dumps(config))
        subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(path)], check=True)
        subprocess.run(["launchctl", "print", target], check=True, stdout=subprocess.DEVNULL)
        print("Private Weibo refresh enabled at 03:35, 09:35, 15:35 and 21:35 local time; no immediate job was started.")
