"""The offline keyboard builder rejects invalid inputs before changing files."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "android/keyboard-build.sh"


class KeyboardBuildTests(unittest.TestCase):
    def test_missing_arguments_only_print_usage(self):
        result = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 64)
        self.assertIn("Usage:", result.stderr)

    def test_missing_source_does_not_create_build_or_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = dict(os.environ, BUILD_DIR=str(root / "build"))
            result = subprocess.run(["bash", str(SCRIPT), str(root / "absent"), str(root / "out")],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 66)
            self.assertEqual(list(root.iterdir()), [])

    def test_build_directory_cannot_be_the_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            (source / "CMakeLists.txt").write_text("# preserve this source\n")
            env = dict(os.environ, BUILD_DIR=str(source))
            result = subprocess.run(["bash", str(SCRIPT), str(source), str(root / "out")],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 64)
            self.assertFalse((root / "out").exists())
            self.assertEqual((source / "CMakeLists.txt").read_text(), "# preserve this source\n")


if __name__ == "__main__":
    unittest.main()
