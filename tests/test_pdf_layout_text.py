import unittest

from scripts.pdf_layout_text import TOKEN_RE


class PdfLayoutTextTests(unittest.TestCase):
    def test_pdf_text_position_regex_accepts_lowercase_td_operator(self):
        match = TOKEN_RE.search("-7520 -480 Td")

        self.assertIsNotNone(match)
        self.assertEqual(match.group(6), "-7520")
        self.assertEqual(match.group(7), "-480")


if __name__ == "__main__":
    unittest.main()
