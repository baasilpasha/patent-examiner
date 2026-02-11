from __future__ import annotations

import json
import logging
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from patent_mvp.models import PatentRecord
from patent_mvp.text_utils import normalize_text

LOGGER = logging.getLogger(__name__)
DEP_RE = re.compile(r"\b(claim|claims)\s+\d+", re.IGNORECASE)


def _collect_texts(elem: ET.Element, tag: str) -> list[str]:
    out: list[str] = []
    for node in elem.findall(f".//{tag}"):
        text = normalize_text(" ".join(t for t in node.itertext()))
        if text:
            out.append(text)
    return out


def parse_claim(text: str, claim_num: str | None) -> dict[str, object]:
    clean = normalize_text(text)
    dep = bool(DEP_RE.search(clean))
    return {"claim_num": claim_num, "text": clean, "is_independent": not dep}


def parse_patent_xml(xml_bytes: bytes) -> list[PatentRecord]:
    patents: list[PatentRecord] = []
    root = ET.fromstring(xml_bytes)
    docs = [root] if root.tag.endswith("us-patent-grant") else root.findall(".//us-patent-grant")

    for doc in docs:
        pub_num = normalize_text("".join(doc.findtext(".//publication-reference/document-id/doc-number", default="")))
        if not pub_num:
            continue
        title = normalize_text(doc.findtext(".//invention-title", default=""))
        grant_date = normalize_text(doc.findtext(".//publication-reference/document-id/date", default="")) or None
        abstract = normalize_text(" ".join(_collect_texts(doc, "abstract/p")))

        summary = _collect_texts(doc, "summary/p")
        description = [p for p in _collect_texts(doc, "description/p") if p not in summary]

        cpc_codes = [
            normalize_text(x.text or "")
            for x in doc.findall(".//classification-cpc/classification-cpc-text")
            if normalize_text(x.text or "")
        ]
        citations = [
            normalize_text(x.text or "")
            for x in doc.findall(".//references-cited//doc-number")
            if normalize_text(x.text or "")
        ]

        claims: list[dict[str, object]] = []
        for claim in doc.findall(".//claims/claim"):
            claim_num = claim.attrib.get("num")
            text = normalize_text(" ".join(t for t in claim.itertext()))
            if text:
                claims.append(parse_claim(text, claim_num))

        patents.append(
            PatentRecord(
                publication_number=pub_num,
                grant_date=grant_date,
                title=title,
                abstract=abstract,
                summary_paragraphs=summary,
                description_paragraphs=description,
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
