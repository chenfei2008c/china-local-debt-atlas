import unittest

from scripts.pdf_layout_text import TOKEN_RE, _content_numbers


class PdfLayoutTextTests(unittest.TestCase):
    def test_pdf_text_position_regex_accepts_lowercase_td_operator(self):
        match = TOKEN_RE.search("-7520 -480 Td")

        self.assertIsNotNone(match)
        self.assertEqual(match.group(6), "-7520")
        self.assertEqual(match.group(7), "-480")

    def test_pdf_content_array_resolves_indirect_stream_reference(self):
        objects = {
            10: b"<</Length 0>>stream\nBT ET\nendstream",
            11: b"\n[ 10 0 R ]\n",
        }

        self.assertEqual(_content_numbers(objects, 11), [10])


if __name__ == "__main__":
    unittest.main()
