#!/usr/bin/env python3
"""Azeroth Chronicles companion uploader.

Watches the AzerothChronicles SavedVariables file and uploads it to your Azeroth Chronicles server
after World of Warcraft writes it (on logout, /reload, or exit).

What it does NOT do: read game memory, inject into the client, touch any other file, or interact with
gameplay. It only reads one text file that the game itself writes to disk.

Standard library only (Python 3.11+). Usage:
    python azchron_companion.py setup --server https://chronicles.example.com --token act_...
    python azchron_companion.py upload        # one-off upload
    python azchron_companion.py watch         # keep running; upload whenever the file changes
    python azchron_companion.py status
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

CONFIG_PATH = Path(os.environ.get("AZCHRON_CONFIG", Path.home() / ".azeroth-chronicles-companion.json"))
SV_NAME = "AzerothChronicles.lua"
SETTLE_SECONDS = 5  # WoW writes SavedVariables in one go; wait until the file stops changing


@dataclass
class Config:
    server: str = ""
    token: str = ""
    savedvariables: list[str] = field(default_factory=list)
    last_upload_hash: dict[str, str] = field(default_factory=dict)
    last_success_at: str | None = None
    last_error: str | None = None

    @classmethod
    def load(cls) -> Config:
        if CONFIG_PATH.exists():
            return cls(**json.loads(CONFIG_PATH.read_text()))
        return cls()

    def save(self) -> None:
        CONFIG_PATH.write_text(json.dumps(asdict(self), indent=2))
        try:
            os.chmod(CONFIG_PATH, 0o600)  # contains the upload token
        except OSError:
            pass


def default_wow_roots() -> list[Path]:
    system = platform.system()
    if system == "Windows":
        drives = [Path(f"{d}:/") for d in "CDEFG"]
        subdirs = ["Program Files (x86)/World of Warcraft", "Program Files/World of Warcraft", "World of Warcraft",
                   "Games/World of Warcraft"]
        return [d / s / "_retail_" for d in drives for s in subdirs]
    if system == "Darwin":
        return [Path("/Applications/World of Warcraft/_retail_")]
    return [Path.home() / "Games/world-of-warcraft/drive_c/Program Files (x86)/World of Warcraft/_retail_"]


def find_savedvariables(roots: list[Path] | None = None) -> list[Path]:
    """Locate WTF/Account/<ACCOUNT>/SavedVariables/AzerothChronicles.lua for every account."""
    found: list[Path] = []
    for root in roots or default_wow_roots():
        account_dir = root / "WTF" / "Account"
        if account_dir.is_dir():
            found.extend(sorted(account_dir.glob(f"*/SavedVariables/{SV_NAME}")))
    return found


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def upload(cfg: Config, path: Path, *, force: bool = False, opener=urllib.request.urlopen) -> dict | None:
    """Upload one SavedVariables file if it changed since the last successful upload."""
    digest = file_hash(path)
    if not force and cfg.last_upload_hash.get(str(path)) == digest:
        return None
    req = urllib.request.Request(
        cfg.server.rstrip("/") + "/api/ingest/savedvariables",
        data=path.read_bytes(),
        method="POST",
        headers={"Authorization": f"Bearer {cfg.token}", "Content-Type": "text/plain; charset=utf-8",
                 "User-Agent": "azeroth-chronicles-companion/1.0"},
    )
    try:
        with opener(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        cfg.last_error = f"HTTP {exc.code}: {detail}"
        cfg.save()
        raise RuntimeError(cfg.last_error) from exc
    except urllib.error.URLError as exc:
        cfg.last_error = f"Server unreachable: {exc.reason}"
        cfg.save()
        raise RuntimeError(cfg.last_error) from exc
    cfg.last_upload_hash[str(path)] = digest
    cfg.last_success_at = datetime.now(UTC).isoformat(timespec="seconds")
    cfg.last_error = None
    cfg.save()
    return result


def _paths(cfg: Config) -> list[Path]:
    paths = [Path(p) for p in cfg.savedvariables] or find_savedvariables()
    return [p for p in paths if p.exists()]


def cmd_setup(args) -> int:
    cfg = Config.load()
    cfg.server = args.server or cfg.server
    cfg.token = args.token or cfg.token
    if args.path:
        cfg.savedvariables = [str(Path(p).expanduser()) for p in args.path]
    elif not cfg.savedvariables:
        cfg.savedvariables = [str(p) for p in find_savedvariables()]
    cfg.save()
    print(f"Saved configuration to {CONFIG_PATH}")
    print("Watching:", *(cfg.savedvariables or ["(nothing found — pass --path)"]), sep="\n  ")
    return 0


def cmd_upload(args) -> int:
    cfg = Config.load()
    if not cfg.server or not cfg.token:
        print("Run setup first (server URL and upload token).", file=sys.stderr)
        return 2
    paths = _paths(cfg)
    if not paths:
        print("No AzerothChronicles.lua SavedVariables file found. Log out of WoW once after installing the addon.")
        return 1
    rc = 0
    for p in paths:
        try:
            r = upload(cfg, p, force=args.force)
            if r is None:
                print(f"{p}: unchanged since last upload")
            else:
                print(f"{p}: {r['normalized']} new, {r['duplicates']} already known, {r['rejected']} rejected")
        except RuntimeError as exc:
            print(f"{p}: upload failed — {exc}", file=sys.stderr)
            rc = 1
    return rc


def cmd_watch(args) -> int:
    print("Watching for SavedVariables changes (Ctrl+C to stop). WoW writes them on logout or /reload.")
    mtimes: dict[Path, float] = {}
    while True:
        for p in _paths(Config.load()):
            m = p.stat().st_mtime
            if mtimes.get(p) == m:
                continue
            first = p not in mtimes
            mtimes[p] = m
            if first and not args.upload_on_start:
                continue
            time.sleep(SETTLE_SECONDS)
            if p.stat().st_mtime != m:
                continue  # still being written; next loop picks it up
            try:
                r = upload(Config.load(), p)
                if r:
                    print(f"[{datetime.now():%H:%M:%S}] uploaded {p.parent.parent.name}: {r['normalized']} new records")
            except RuntimeError as exc:
                print(f"[{datetime.now():%H:%M:%S}] upload failed: {exc}", file=sys.stderr)
        time.sleep(args.interval)
    return 0  # pragma: no cover


def cmd_status(_args) -> int:
    cfg = Config.load()
    print(f"Config:        {CONFIG_PATH}")
    print(f"Server:        {cfg.server or '(not set)'}")
    print(f"Token:         {(cfg.token[:8] + '…') if cfg.token else '(not set)'}")
    print(f"Last success:  {cfg.last_success_at or 'never'}")
    print(f"Last error:    {cfg.last_error or 'none'}")
    for p in _paths(cfg):
        print(f"File:          {p} (modified {datetime.fromtimestamp(p.stat().st_mtime):%Y-%m-%d %H:%M})")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup")
    s.add_argument("--server")
    s.add_argument("--token")
    s.add_argument("--path", nargs="*", help="explicit SavedVariables file(s)")
    u = sub.add_parser("upload")
    u.add_argument("--force", action="store_true")
    w = sub.add_parser("watch")
    w.add_argument("--interval", type=float, default=10.0)
    w.add_argument("--upload-on-start", action="store_true")
    sub.add_parser("status")
    args = ap.parse_args(argv)
    return {"setup": cmd_setup, "upload": cmd_upload, "watch": cmd_watch, "status": cmd_status}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
