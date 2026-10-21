"""tests/test_md_clean.py - unit tests for md_clean.py (python -m unittest tests.test_md_clean  or  python tests\test_md_clean.py)."""
import os, sys, unittest, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from md_clean import clean_markdown as c, clean_lines

class T(unittest.TestCase):
    def test_italic_bold(self):
        self.assertEqual(c("This is *really* important."), "This is really important.")
        self.assertEqual(c("This is **really** important."), "This is really important.")
        self.assertEqual(c("***wow*** and *so* **very** much"), "wow and so very much")
        self.assertEqual(c("*Being and Time* by Heidegger"), "Being and Time by Heidegger")
        self.assertEqual(c("**Bold start**, then plain."), "Bold start, then plain.")
        self.assertEqual(c("*one* *two* three"), "one two three")
        self.assertEqual(c("**_nested_** works"), "nested works")
    def test_underscore_emphasis_safe(self):
        self.assertEqual(c("It was _exactly_ that."), "It was exactly that.")
        self.assertEqual(c("It was __exactly__ that."), "It was exactly that.")
        self.assertEqual(c("(_really_) hmm"), "(really) hmm")
    def test_underscores_in_words_left_alone(self):
        for s in ["call do_the_thing now", "a_b_c", "CONSTANT_NAME_X", "trailing_ and _leading", "snake_case_"]:
            self.assertEqual(c(s), s)
        self.assertEqual(c("use snake_case here"), "use snake_case here")
        self.assertEqual(c("my_var_name = 3"), "my_var_name = 3")
        self.assertEqual(c("file_name.txt and other_file.txt"), "file_name.txt and other_file.txt")
    def test_literal_asterisk_math_code(self):
        self.assertEqual(c("2 * 3 = 6"), "2 * 3 = 6")
        self.assertEqual(c("3*4*5 is 60"), "3*4*5 is 60")
        self.assertEqual(c("a*b means a times b"), "a*b means a times b")
        self.assertEqual(c("x * y * z"), "x * y * z")
        self.assertEqual(c("2*3"), "2*3")
    def test_stray_marks(self):
        self.assertEqual(c("Well ** hmm"), "Well  hmm")
        self.assertEqual(c("*Hello there"), "Hello there")
        self.assertEqual(c("That is it*"), "That is it")
        self.assertEqual(c("run `ls -la` now"), "run ls -la now")
        self.assertEqual(c("stray ` tick"), "stray  tick")
        self.assertEqual(c("~~old~~ new"), "old new")
        self.assertEqual(c("see [the docs](https://example.com/x) ok"), "see the docs ok")
    def test_leading_markdown(self):
        self.assertEqual(c("# Heading text"), "Heading text")
        self.assertEqual(c("> quoted words"), "quoted words")
        self.assertEqual(c("- bullet words"), "bullet words")
        self.assertEqual(c("* bullet words"), "bullet words")
        self.assertEqual(c("1990 was a year"), "1990 was a year")
        self.assertEqual(c("-5 degrees"), "-5 degrees")
    def test_speaker_tags(self):
        self.assertEqual(c("**Host:** Welcome back"), "Host: Welcome back")
        self.assertEqual(c("*Guest2*: right"), "Guest2: right")
        self.assertEqual(c("Host: plain stays"), "Host: plain stays")
        L = [{"speaker": "Host", "text": "**Hi** there"}, {"speaker": "**Guest**", "text": "ok"}]
        new, n = clean_lines(L)
        self.assertEqual(n, 1); self.assertEqual(new[0], {"speaker": "Host", "text": "Hi there"}); self.assertEqual(new[1]["speaker"], "**Guest**")
        self.assertEqual(L[0]["text"], "**Hi** there")                      # input not mutated
    def test_nothing_else_changes(self):
        for s in ["Plain text, with punctuation... and 'quotes' \u2014 dashes? Yes!", "Caf\u00e9 na\u00efve \u00e5\u00f8\u00e6", "Heidegger's das Man isn't Dasein.", "50% of 3 * 4", "  spaced  out  "]:
            self.assertEqual(c(s), s)
    def test_cli_in_place(self):
        import subprocess
        cli = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "md_clean.py")
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            with open(p, "w") as f: json.dump([{"speaker": "Host", "text": "A *b* c"}, {"speaker": "Guest", "text": "plain"}], f)
            r = subprocess.run([sys.executable, cli, p], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(p) as f: self.assertEqual([l["text"] for l in json.load(f)], ["A b c", "plain"])
            self.assertTrue(os.path.exists(p[:-5] + ".pre_md.json"))
            r = subprocess.run([sys.executable, cli, p], capture_output=True, text=True)
            self.assertIn("nothing to strip", r.stdout)
if __name__ == "__main__": unittest.main(verbosity=2)
