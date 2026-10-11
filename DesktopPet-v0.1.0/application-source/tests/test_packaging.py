import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from desktop_pet.config import runtime_directory, ROOT
from desktop_pet.startup import startup_command


class PackagingTests(unittest.TestCase):
    def test_frozen_data_outside_temporary_resources(self):
        with patch.dict(os.environ, {"LOCALAPPDATA": "C:/Users/Test/AppData/Local"}):
            with patch.dict(os.environ, {k: v for k, v in os.environ.items() if k != "DESKTOPPET_DATA_DIR"}, clear=True):
                with patch.object(sys, "frozen", True, create=True):
                    self.assertEqual(runtime_directory(), Path("C:/Users/Test/AppData/Local/DesktopPet"))

    def test_source_keeps_existing_settings_directory(self):
        with patch.dict(os.environ, {k: v for k, v in os.environ.items() if k != "DESKTOPPET_DATA_DIR"}, clear=True):
            with patch.object(sys, "frozen", False, create=True):
                self.assertEqual(runtime_directory(), ROOT / "runtime")

    def test_data_override_for_isolated_release_tests(self):
        with patch.dict(os.environ, {"DESKTOPPET_DATA_DIR": "E:/DesktopPet/work/test-data"}):
            self.assertEqual(runtime_directory(), Path("E:/DesktopPet/work/test-data").resolve())

    def test_frozen_startup_uses_real_exe_not_extraction_path(self):
        with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", "E:/My Pets/DesktopPet.exe"):
            command = startup_command(Path("C:/Temp/_MEI123"))
            self.assertEqual(command, '"E:\\My Pets\\DesktopPet.exe"')
            self.assertNotIn("_MEI", command)
            self.assertNotIn("python", command)

    def test_source_startup_still_works(self):
        with patch.object(sys, "frozen", False, create=True), patch.object(sys, "executable", "E:/Pet/.venv/Scripts/python.exe"):
            command = startup_command(Path("E:/Pet"))
            self.assertIn("pythonw.exe", command)
            self.assertIn("main.py", command)


if __name__ == "__main__":
    unittest.main()
