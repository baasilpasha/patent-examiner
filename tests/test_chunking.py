from patent_mvp.chunking import build_chunks
from patent_mvp.models import Claim, PatentDocument
from patent_mvp.text_utils import chunk_paragraph


def test_paragraph_chunk_overlap() -> None:
    text = " ".join(["token"] * 500)
    chunks = chunk_paragraph(text, max_chars=120, overlap=20)
    assert len(chunks) > 1
    assert len(chunks[0]) <= 120
    assert chunks[0][-10:] in chunks[1]


def test_build_chunks_claim_metadata() -> None:
    doc = PatentDocument(
        publication_number="US1",
        grant_date="20240101",
        title="t",
        abstract="abstract",
        summary_paragraphs=["summary"],
        description_paragraphs=["description"],
        claims=[
            Claim(claim_num="1", text="A system comprising a processor", is_dependent=False, depends_on=[]),
            Claim(claim_num="2", text="The system of claim 1, wherein...", is_dependent=True, depends_on=["1"]),
        ],
        cpc_codes=["G06F17/30"],
        citations=[],
        raw={},
    )
    chunks = build_chunks(doc)
    claim_chunks = [c for c in chunks if c.section_type == "CLAIM"]
    assert len(claim_chunks) == 2
    assert claim_chunks[1].is_dependent is True
