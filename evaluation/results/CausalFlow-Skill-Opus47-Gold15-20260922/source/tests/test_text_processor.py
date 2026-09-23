from __future__ import annotations

import unittest

from text_processor import parse_json_object


class ParseJsonObjectTests(unittest.TestCase):
    def test_accepts_valid_tool_arguments(self):
        self.assertEqual(
            parse_json_object('{"command": "echo ok"}'),
            {"command": "echo ok"},
        )

    def test_repairs_extra_backslash_in_shell_grouping(self):
        raw = r'{"command":"find /root \\\( -name \"*.pptx\" \\\)"}'
        self.assertEqual(
            parse_json_object(raw),
            {"command": r'find /root \( -name "*.pptx" \)'},
        )

    def test_rejects_plain_text_for_executable_arguments(self):
        with self.assertRaises(ValueError):
            parse_json_object("run the command now")


if __name__ == "__main__":
    unittest.main()
