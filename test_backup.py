import tempfile
import unittest
import subprocess
from pathlib import Path

from backup import ROOT, backup, backup_system


class BackupTests(unittest.TestCase):
    def test_fastfetch_images_are_excluded_and_config_uses_bonsai(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "source"
            images = home / ".config/fastfetch/pngs"
            images.mkdir(parents=True)
            (images / "torii.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00")
            (images / "loli.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00")
            config = images.parent / "config1.jsonc"
            config.write_text('{"logo":{"source":"~/.config/neofetch/pngs/loli.png"}}')
            destination = root / "snapshot"
            copied, _ = backup(home, destination)
            self.assertFalse(any(name.endswith(".png") for name in copied))
            self.assertIn("~/.config/linux-rice/fastfetch/bonsai.txt", (destination / ".config/fastfetch/config1.jsonc").read_text())

    def test_keeps_configuration_but_excludes_credentials_and_application_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "source"
            config = home / ".config" / "kitty"
            config.mkdir(parents=True)
            (config / "kitty.conf").write_text(f"font_size 12\ninclude {home}/colours.conf\n")
            (config / "private.conf").write_text("password=never-copy-this")
            (config / "auth.conf").write_text('api_key = "never-copy-this"')
            (config / "history").write_text("private commands")
            (config / "subtitles").mkdir()
            (config / "subtitles" / "movie.srt").write_text("personal viewing data")
            (home / ".config" / "gh").mkdir()
            (home / ".config" / "gh" / "hosts.yml").write_text("private data")
            output = root / "snapshot"
            copied, _ = backup(home, output)
            self.assertEqual(copied, [".config/kitty/kitty.conf"])
            self.assertIn("{{HOME}}/colours.conf", (output / copied[0]).read_text())

    def test_system_snapshot_includes_sddm_and_keymap_without_autologin(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            system = root / "source"
            config = system / "etc/sddm.conf.d/theme.conf"
            config.parent.mkdir(parents=True)
            config.write_text("[Theme]\nCurrent=sample\n[Autologin]\nUser=someone\nSession=hyprland\n")
            keymap = system / "etc/vconsole.conf"
            keymap.write_text("KEYMAP=us\n")
            theme = system / "usr/share/sddm/themes/sample/Main.qml"
            theme.parent.mkdir(parents=True)
            theme.write_text('import QtQuick\nTextInput { passwordCharacter: "*" }\n')
            destination = root / "snapshot"
            files = backup_system(root / "home", destination, system)
            self.assertIn("etc/vconsole.conf", files)
            self.assertIn("usr/share/sddm/themes/sample/Main.qml", files)
            text = (destination / "etc/sddm.conf.d/theme.conf").read_text()
            self.assertIn("Current=sample", text)
            self.assertNotIn("someone", text)
            self.assertNotIn("Autologin", text)

    def test_external_symlinks_and_binary_files_are_not_copied(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "source"
            config = home / ".config" / "kitty"
            config.mkdir(parents=True)
            outside = root / "outside"
            outside.write_text("outside selected configuration")
            (config / "external.conf").symlink_to(outside)
            (config / "binary").write_bytes(b"\x00\xff")
            self.assertEqual(backup(home, root / "snapshot")[0], [])

    def test_restore_is_dry_run_by_default_and_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            target = home / ".config" / "kitty" / "kitty.conf"
            target.parent.mkdir(parents=True)
            target.write_text("previous configuration\n")
            command = ["python3", str(ROOT / "restore.py"), "--home", str(home)]
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
            self.assertEqual(target.read_text(), "previous configuration\n")
            subprocess.run(command + ["--apply"], check=True, stdout=subprocess.DEVNULL)
            self.assertNotEqual(target.read_text(), "previous configuration\n")
            saved = list((home / ".local/state/dotfiles-backups").glob("*/.config/kitty/kitty.conf"))
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0].read_text(), "previous configuration\n")
            self.assertNotIn("{{HOME}}", target.read_text())


if __name__ == "__main__":
    unittest.main()
