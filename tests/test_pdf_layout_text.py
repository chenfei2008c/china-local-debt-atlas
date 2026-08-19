import unittest
from pathlib import Path

from scripts.pdf_layout_text import TOKEN_RE, _cmap, _content_numbers, extract_pdf_text


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

    def test_official_jinan_pdf_text_extracts_city_fiscal_values(self):
        path = Path("raw/province_fiscal/2025/official/jinan_2025_budget_report.pdf")
        self.assertTrue(path.exists())

        text = extract_pdf_text(path)

        self.assertIn("一般公共预算收入", text)
        self.assertIn("1093.35", text)
        self.assertIn("1407.49", text)
        self.assertIn("567.26", text)

    def test_cmap_decodes_surrogate_pair_in_bfrange(self):
        objects = {
            1: b"<</Length 0>>stream\n1 beginbfrange\n<0001><0001><dbc0ddb0>\nendbfrange\nendstream",
        }

        self.assertEqual(_cmap(objects, 1)[1], bytes.fromhex("dbc0ddb0").decode("utf-16-be"))


if __name__ == "__main__":
    unittest.main()
