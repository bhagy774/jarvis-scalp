import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Patch os.chdir and requests BEFORE importing the module to prevent side effects
patcher_chdir = patch("os.chdir")
patcher_requests = patch("requests.get")
patcher_chdir.start()
mock_requests = patcher_requests.start()

# Add parent directory to path to find jarvis_full_test
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import jarvis_full_test

patcher_chdir.stop()
patcher_requests.stop()


class TestJarvisFullTest(unittest.TestCase):

    def setUp(self):
        # Reset the results list in jarvis_full_test before each test
        jarvis_full_test.results = []

    @patch("builtins.print")
    def test_section_formatting(self, mock_print):
        """Test that section formatting functions output correctly."""
        jarvis_full_test.section("TEST_TITLE")

        # Check that it printed multiple lines including the title
        self.assertTrue(mock_print.called)

        # Check if any of the printed calls contains the title
        title_printed = any("TEST_TITLE" in str(call_args) for call_args in mock_print.call_args_list)
        self.assertTrue(title_printed, "Title was not printed in section()")

    @patch("builtins.print")
    def test_test_function_success(self, mock_print):
        """Test the test() wrapper with a successful function."""
        def dummy_success():
            return "All good"

        result = jarvis_full_test.test("Dummy Success Test", dummy_success)

        self.assertTrue(result)
        self.assertEqual(len(jarvis_full_test.results), 1)
        self.assertEqual(jarvis_full_test.results[0][0], "PASS")
        self.assertEqual(jarvis_full_test.results[0][1], "Dummy Success Test")
        self.assertEqual(jarvis_full_test.results[0][2], "All good")

    @patch("builtins.print")
    def test_test_function_failure(self, mock_print):
        """Test the test() wrapper with a failing function."""
        def dummy_failure():
            raise ValueError("Something broke")

        result = jarvis_full_test.test("Dummy Failure Test", dummy_failure)

        self.assertFalse(result)
        self.assertEqual(len(jarvis_full_test.results), 1)
        self.assertEqual(jarvis_full_test.results[0][0], "FAIL")
        self.assertEqual(jarvis_full_test.results[0][1], "Dummy Failure Test")
        self.assertEqual(jarvis_full_test.results[0][2], "Something broke")

    def test_colors_defined(self):
        """Test that all required ANSI color constants are defined."""
        colors = ["R", "G", "Y", "C", "W", "DG", "BD", "RST"]
        for color in colors:
            self.assertTrue(hasattr(jarvis_full_test, color), f"Missing color constant {color}")

if __name__ == "__main__":
    unittest.main()
