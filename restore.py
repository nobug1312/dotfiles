#!/usr/bin/env python3
"""Restore a snapshot; existing files are backed up before replacement."""

import argparse
import json
import shutil
import socket
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write files; default is a dry run")
    parser.add_argument("--home", type=Path, default=Path.home())
    args = parser.parse_args()
    home = args.home.resolve()
    backup = home / ".local" / "state" / "dotfiles-backups" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    files = json.loads((ROOT / "manifest.json").read_text())["files"]
    for name in files:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Invalid snapshot path")
        source = ROOT / "home" / relative
        target = home / relative
        if not target.parent.resolve().is_relative_to(home):
            raise ValueError("Destination directory points outside home")
        if not args.apply:
            print(f"Would restore ~/{name}")
            continue
        if target.is_symlink() or target.exists():
            saved = backup / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink():
                saved.symlink_to(target.readlink())
                target.unlink()
            elif target.is_file():
                shutil.copy2(target, saved)
            else:
                raise ValueError(f"Destination is not a file: {name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        text = source.read_text().replace("{{HOME}}", str(home))
        text = text.replace("{{USER}}", home.name).replace("{{HOST}}", socket.gethostname())
        target.write_text(text)
        target.chmod(source.stat().st_mode & 0o777)
    if args.apply:
        print(f"Restored {len(files)} files. Previous files saved under {backup}")


if __name__ == "__main__":
    main()
