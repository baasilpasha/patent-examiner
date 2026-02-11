from __future__ import annotations

import json
import logging
import re
import zipfile
from pathlib import Path

from lxml import etree

from patent_mvp.models import PatentRecord
from patent_mvp.text_utils import normalize_text

LOGGER = logging.getLogger(__name__)
DEP_RE = re.compile(r"\b(claim|claims)\s+\d+", re.IGNORECASE)

def _xpath(node: etree._Element, expr: str) -> list[etree._Element | str]:
    return node.xpath(expr)


def _first_text(node: etree._Element, expr: str) -> str:
    values = _xpath(node, expr)
    if not values:
        return ""
    first = values[0]
    if isinstance(first, str):
        return normalize_text(first)
    return normalize_text(" ".join(first.itertext()))


def _texts(node: etree._Element, expr: str) -> list[str]:
    out: list[str] = []
    for item in _xpath(node, expr):
        if isinstance(item, str):
            text = normalize_text(item)
        else:
            text = normalize_text(" ".join(item.itertext()))
        if text:
            out.append(text)
    return out


def parse_claim(text: str, claim_num: str | None) -> dict[str, object]:
    clean = normalize_text(text)
    dep = bool(DEP_RE.search(clean))
    return {"claim_num": claim_num, "text": clean, "is_independent": not dep}


def _find_patent_docs(root: etree._Element) -> list[etree._Element]:
    if etree.QName(root).localname == "us-patent-grant":
        return [root]
    docs = [d for d in root.xpath("//*[local-name()='us-patent-grant']") if isinstance(d, etree._Element)]
    return docs


def parse_patent_xml(xml_bytes: bytes) -> list[PatentRecord]:
    patents: list[PatentRecord] = []
    root = etree.fromstring(xml_bytes)
    docs = _find_patent_docs(root)

    for doc in docs:
        pub_num = _first_text(doc, "(.//*[local-name()='publication-reference']//*[local-name()='document-id']//*[local-name()='doc-number']/text())[1]")
        if not pub_num:
            continue

        title = _first_text(doc, "(.//*[local-name()='invention-title']/text())[1]")
        grant_date = _first_text(doc, "(.//*[local-name()='publication-reference']//*[local-name()='document-id']//*[local-name()='date']/text())[1]") or None

        abstract = normalize_text(" ".join(_texts(doc, ".//*[local-name()='abstract']//*[local-name()='p']")))

        claim_nodes = _xpath(doc, ".//*[local-name()='claims']//*[local-name()='claim']")
        claims: list[dict[str, object]] = []
        for claim in claim_nodes:
            if not isinstance(claim, etree._Element):
                continue
            claim_num = claim.get("num") or _first_text(claim, "(.//*[local-name()='claim-num']/text())[1]") or None
            claim_text_parts = _texts(claim, ".//*[local-name()='claim-text']")
            claim_text = " ".join(claim_text_parts) if claim_text_parts else normalize_text(" ".join(claim.itertext()))
            if claim_text:
                claims.append(parse_claim(claim_text, claim_num))

        cpc_codes = _texts(doc, ".//*[local-name()='classification-cpc-text']/text()")

        citations = _texts(doc, ".//*[local-name()='references-cited']//*[local-name()='doc-number']/text()")

        summary_nodes = _xpath(
            doc,
            ".//*[local-name()='summary' or local-name()='summary-of-invention']//*[local-name()='p']",
        )
        summary_paragraphs = []
        summary_node_ids: set[int] = set()
        for node in summary_nodes:
            if isinstance(node, etree._Element):
                summary_node_ids.add(id(node))
                text = normalize_text(" ".join(node.itertext()))
                if text:
                    summary_paragraphs.append(text)

        description_nodes = _xpath(
            doc,
            ".//*[local-name()='description' or local-name()='detailed-description']//*[local-name()='p']",
        )
        description_paragraphs = []
        for node in description_nodes:
            if not isinstance(node, etree._Element):
                continue
            if id(node) in summary_node_ids:
                continue
            if node.xpath("ancestor::*[local-name()='summary' or local-name()='summary-of-invention']"):
                continue
            text = normalize_text(" ".join(node.itertext()))
            if text:
                description_paragraphs.append(text)

        patents.append(
            PatentRecord(
                publication_number=pub_num,
                grant_date=grant_date,
                title=title,
                abstract=abstract,
                summary_paragraphs=summary_paragraphs,
                description_paragraphs=description_paragraphs,
                claims=claims,
                cpc_codes=cpc_codes,
                citations=citations,
                raw_json={"publication_number": pub_num, "title": title},
            )
        )
    return patents


def parse_week_zip(zip_path: Path, parsed_dir: Path) -> list[PatentRecord]:
    parsed_dir.mkdir(parents=True, exist_ok=True)
    out: list[PatentRecord] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".xml"):
                continue
            patents = parse_patent_xml(zf.read(name))
            for p in patents:
                (parsed_dir / f"{p.publication_number}.json").write_text(json.dumps(p.__dict__, ensure_ascii=False, indent=2))
            out.extend(patents)
    LOGGER.info("Parsed %s patents from %s", len(out), zip_path)
    return out
