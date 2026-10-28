"""tokenize_written against conformance/written.expected.json, and its invariant on each case.
Run: python3 python/test_written.py (or pytest), with bcv_tokenize.py beside it."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bcv_tokenize import tokenize, strip_marks  # noqa: E402
from bcv_written import tokenize_written  # noqa: E402

CASES = json.load(open(os.path.join(HERE, "..", "conformance", "written.expected.json"), encoding="utf-8"))


def test_cases():
    for c in CASES:
        t, w = tokenize(c["input"]), tokenize_written(c["input"])
        assert t == c["tokens"], (c["name"], t)
        assert w == c["written"], (c["name"], w)
        assert [strip_marks(x) for x in w] == t, c["name"]


if __name__ == "__main__":
    test_cases()
    print("ok", len(CASES))
