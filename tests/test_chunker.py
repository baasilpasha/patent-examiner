from patent_mvp.chunker import build_chunks, has_cpc_prefix
from patent_mvp.models import PatentRecord
from patent_mvp.text_utils import split_with_overlap


def make_patent() -> PatentRecord:
    return PatentRecord(
        publication_number="US1",
        grant_date="20250107",
        title="x",
        abstract="ab",
        summary_paragraphs=["s"],
        description_paragraphs=["d"],
        claims=[
            {"claim_num": "1", "text": "A device comprising...", "is_independent": True},
            {"claim_num": "2", "text": "The device of claim 1...", "is_independent": False},
        ],
        cpc_codes=["G06F 9/445"],
        citations=[],
    )


def test_cpc_prefix_filter() -> None:
    assert has_cpc_prefix(make_patent(), "G06F")
    assert not has_cpc_prefix(make_patent(), "A01B")


def test_build_chunks_claim_metadata() -> None:
    chunks = build_chunks(make_patent())
    claims = [c for c in chunks if c.section_type == "CLAIM"]
    assert len(claims) == 2
    assert claims[0].is_independent is True
    assert claims[1].is_independent is False


def test_split_with_overlap() -> None:
    text = "a" * 2500
    parts = split_with_overlap(text, max_chars=1200, overlap=150)
    assert len(parts) == 3
    assert parts[0][-150:] == parts[1][:150]
