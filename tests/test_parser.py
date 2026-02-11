from pathlib import Path

from patent_mvp.parser import parse_claim, parse_patent_xml


def test_claim_independent_dependent_detect() -> None:
    c1 = parse_claim("1. A system comprising a processor", "1")
    c2 = parse_claim("2. The system of claim 1, wherein ...", "2")
    assert c1["is_independent"] is True
    assert c2["is_independent"] is False


def test_fixture_parse_smoke() -> None:
    xml = Path("tests/fixtures/sample_patent.xml").read_bytes()
    patents = parse_patent_xml(xml)
    assert len(patents) == 1
    p = patents[0]
    assert p.publication_number == "US1234567B2"
    assert p.cpc_codes[0].startswith("G06F")
    assert len(p.claims) == 2
