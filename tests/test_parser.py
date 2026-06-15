from unittest import TestCase

from packages.harness.parser import parse_json_blocks


class ParserTests(TestCase):
    def test_parse_json_block(self):
        text = '<ADVICE_REQUEST>{"reason":"x","packet":{}}</ADVICE_REQUEST>'
        self.assertEqual(parse_json_blocks(text, "ADVICE_REQUEST")[0]["reason"], "x")
