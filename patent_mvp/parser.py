from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable
import xml.etree.ElementTree as ET

from patent_mvp.models import Claim, PatentDocument
from patent_mvp.text_utils import clean_text

_DEP_RE = re.compile(r"\bclaim(?:s)?\s+(\d+)\b", re.IGNORECASE)


def is_target_cpc(cpc_codes: Iterable[str], prefix: str) -> bool:
    upper_prefix = prefix.upper()
    return any(code.upper().startswith(upper_prefix) for code in cpc_codes)


def parse_claim_dependency(claim_text: str) -> tuple[bool, list[str]]:
    deps = _DEP_RE.findall(claim_text)
    return len(deps) > 0, deps


def _texts(root: ET.Element, path: str) -> list[str]:
    return [clean_text("".join(e.itertext())) for e in root.findall(path) if clean_text("".join(e.itertext()))]


def parse_patent_xml(xml_path: Path) -> list[PatentDocument]:
    tree = ET.parse(xml_path)
    docs: list[PatentDocument] = []
    for patent in tree.findall(".//us-patent-grant"):
        pub = clean_text("".join((patent.findtext(".//publication-reference//doc-number") or "").split()))
        date = clean_text((patent.findtext(".//publication-reference//date") or ""))
        title = clean_text("".join(patent.find(".//invention-title").itertext())) if patent.find(".//invention-title") is not None else ""
        abstract_el = patent.find(".//abstract")
        abstract = clean_text("".join(abstract_el.itertext())) if abstract_el is not None else ""

        summary_paras = _texts(patent, ".//description/summary//p")
        desc_paras = [
            clean_text("".join(p.itertext()))
            for p in patent.findall(".//description//p")
            if clean_text("".join(p.itertext())) and p not in patent.findall(".//description/summary//p")
        ]

        claims: list[Claim] = []
        for cl in patent.findall(".//claims//claim"):
            claim_num = clean_text(cl.attrib.get("num", str(len(claims) + 1)))
            claim_text = clean_text("".join(cl.itertext()))
            is_dep, deps = parse_claim_dependency(claim_text)
            claims.append(Claim(claim_num=claim_num, text=claim_text, is_dependent=is_dep, depends_on=deps))

        cpc_codes = [clean_text("".join(c.itertext())) for c in patent.findall(".//classification-cpc-text") if clean_text("".join(c.itertext()))]
        citations = [clean_text("".join(c.itertext())) for c in patent.findall(".//citation//doc-number") if clean_text("".join(c.itertext()))]

        docs.append(
            PatentDocument(
                publication_number=pub,
                grant_date=date,
                title=title,
                abstract=abstract,
                summary_paragraphs=summary_paras,
                description_paragraphs=desc_paras,
                claims=claims,
                cpc_codes=cpc_codes,
                citations=citations,
                raw={
                    "publication_number": pub,
                    "grant_date": date,
                    "title": title,
                    "abstract": abstract,
                    "cpc_codes": cpc_codes,
                    "citations": citations,
                },
            )
        )
    return docs
