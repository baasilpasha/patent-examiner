from pathlib import Path

from patent_mvp.parser import is_target_cpc, parse_claim_dependency, parse_patent_xml


def test_cpc_filter_matches_prefix() -> None:
    assert is_target_cpc(["H04L12/58", "G06F17/30"], "G06F")
    assert not is_target_cpc(["H04L12/58"], "G06F")


def test_claim_dependency_detection() -> None:
    indep, deps = parse_claim_dependency("1. A device comprising a processor.")
    assert indep is False
    assert deps == []

    dep, deps = parse_claim_dependency("2. The device of claim 1, wherein memory is encrypted.")
    assert dep is True
    assert deps == ["1"]


def test_fixture_parse_smoke() -> None:
    docs = parse_patent_xml(Path("tests/fixtures/sample_patent.xml"))
    assert len(docs) == 1
    doc = docs[0]
    assert doc.publication_number == "US12345678B2"
    assert doc.cpc_codes[0].startswith("G06F")
    assert len(doc.claims) == 2
