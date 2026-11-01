#!/usr/bin/env python3
"""Copy selected Linux configuration without application data or credentials."""

import argparse
import configparser
import json
import re
import shutil
import socket
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CONFIGS = (
    "hypr", "waybar", "waybar-jp", "kitty", "alacritty", "ghostty", "foot",
    "nvim", "micro", "rofi", "wlogout", "mako", "swaync", "btop", "cava",
    "fastfetch", "quickshell", "noctalia", "matugen", "wallust", "pypr",
    "niri", "uwsm", "nwg-look", "nwg-displays", "gtk-2.0", "gtk-3.0",
    "gtk-4.0", "Kvantum", "qt5ct", "qt6ct", "xsettingsd", "yazi",
    "zathura", "mpv", "rmpc", "fish", "swappy",
)
SHELL_FILES = (".zshrc", ".bashrc", ".bash_profile", ".bash_logout")
EXCLUDED = re.compile(
    r"(^|[/_.-])(cache|history|session|sessions|state|logs?|cookies?|"
    r"credentials?|secrets?|tokens?|accounts?|private|pre-restore|subtitles?|"
    r"node_modules|\.git)([/_.-]|$)|"
    r"\.(bak.*|save.*|old|swp|zwc|pyc|pem|key|sqlite.*|db|srt|ass|ssa|vtt|sub)$|"
    r"\(copy \d+\)|^\.initial_startup_done$|(^|/)fish_variables$",
    re.I,
)
SENSITIVE = re.compile(
    r"(?i)(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]+|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"https?://[^\s/\"']+:[^\s/\"']+@|"
    r"\b(?!passwordCharacter\b)[\w.-]*(?:password|passwd|api[_-]?key|token|secret|authorization|"
    r"email|username|account[_-]?id)[\w.-]*"
    r"[\"']?\s*[:=]\s*[\"']?[^\s\"',;}]+|"
    r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})"
)


def safe_text(path, home):
    try:
        if path.stat().st_size > 1_000_000:
            return None
        text = path.read_text(encoding="utf-8")
    except (UnicodeError, OSError):
        return None
    if "\x00" in text or SENSITIVE.search(text):
        return None
    text = text.replace(str(home), "{{HOME}}")
    text = re.sub(rf"\b{re.escape(home.name)}\b", "{{USER}}", text)
    return re.sub(rf"\b{re.escape(socket.gethostname())}\b", "{{HOST}}", text)


def backup(home, destination):
    home = home.resolve()
    candidates = [home / name for name in SHELL_FILES if (home / name).is_file()]
    for name in CONFIGS:
        directory = home / ".config" / name
        if directory.is_dir():
            candidates.extend(path for path in directory.rglob("*") if path.is_file())
    custom = home / ".oh-my-zsh" / "custom"
    if custom.is_dir():
        candidates.extend(path for path in custom.rglob("*") if path.is_file())
    bonsai = home / ".config/linux-rice/fastfetch/bonsai.txt"
    if bonsai.is_file() and not bonsai.is_symlink():
        candidates.append(bonsai)

    copied = []
    skipped = 0
    for path in sorted(set(candidates)):
        relative = path.relative_to(home)
        if EXCLUDED.search(relative.as_posix()):
            skipped += 1
            continue
        # Never follow links outside their selected configuration directory.
        boundary = home / ".config" / relative.parts[1] if relative.parts[0] == ".config" else home / ".oh-my-zsh" / "custom"
        if path.is_symlink() and not path.resolve().is_relative_to(boundary):
            skipped += 1
            continue
        text = safe_text(path, home)
        if text is None:
            skipped += 1
            continue
        if relative.parent == Path(".config/fastfetch") and relative.name in ("config1.jsonc", "config.jsonc.before-ricelin"):
            text = re.sub(r'"source"\s*:\s*"[^"]+"', '"source": "~/.config/linux-rice/fastfetch/bonsai.txt"', text, count=1)
            text = re.sub(r'"type"\s*:\s*"kitty"', '"type": "file"', text, count=1)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        target.chmod(0o755 if path.stat().st_mode & 0o111 else 0o644)
        copied.append(relative.as_posix())
    return copied, skipped


def backup_system(home, destination, system_root=Path("/")):
    paths = [
        "etc/sddm.conf", "etc/vconsole.conf",
        "etc/X11/xorg.conf.d/00-keyboard.conf",
    ]
    paths.extend(
        str(path.relative_to(system_root))
        for path in (system_root / "etc/sddm.conf.d").glob("*.conf")
    )
    theme = None
    for name in paths:
        if "sddm" not in name:
            continue
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(system_root / name)
        if parser.has_option("Theme", "Current"):
            theme = parser.get("Theme", "Current")
    if theme and re.fullmatch(r"[\w.-]+", theme):
        directory = system_root / "usr/share/sddm/themes" / theme
        paths.extend(
            str(path.relative_to(system_root))
            for path in directory.rglob("*")
            if path.is_file() and path.suffix in (".qml", ".conf", ".desktop", ".js")
        )
    copied = []
    for name in sorted(set(paths)):
        path = system_root / name
        if not path.is_file() or path.is_symlink():
            continue
        text = safe_text(path, home)
        if text is None:
            continue
        # Never distribute SDDM autologin identities or their settings.
        if "sddm" in name:
            text = re.sub(r"(?ims)^\[Autologin\][^\n]*\n.*?(?=^\[|\Z)", "", text)
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        copied.append(name)
    return copied


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home())
    args = parser.parse_args()
    destination = ROOT / "home"
    manifest = ROOT / "manifest.json"
    previous = json.loads(manifest.read_text())["files"] if manifest.exists() else []
    copied, skipped = backup(args.home, destination)
    for name in set(previous) - set(copied):
        target = destination / name
        if target.resolve().is_relative_to(destination.resolve()) and target.is_file():
            target.unlink()
    old_system = json.loads(manifest.read_text()).get("system_files", []) if manifest.exists() else []
    system_destination = ROOT / "system"
    system_files = backup_system(args.home.resolve(), system_destination)
    for name in set(old_system) - set(system_files):
        target = system_destination / name
        if target.resolve().is_relative_to(system_destination.resolve()) and target.is_file():
            target.unlink()
    manifest.write_text(json.dumps({"files": copied, "system_files": system_files}, indent=2) + "\n")
    if shutil.which("pacman"):
        packages = ROOT / "packages"
        packages.mkdir(exist_ok=True)
        for name, flags in (("native.txt", "-Qqen"), ("foreign.txt", "-Qqem")):
            result = subprocess.run(["pacman", flags], capture_output=True, text=True)
            if result.returncode == 0:
                (packages / name).write_text(result.stdout)
    print(f"Backed up {len(copied)} text configuration files; skipped {skipped} files.")
    print(f"Backed up {len(system_files)} system configuration files; system restore is manual.")
    print("Review the snapshot before sharing. Detection is conservative, not a security guarantee.")


if __name__ == "__main__":
    main()
