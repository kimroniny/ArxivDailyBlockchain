#!/usr/bin/env python3
"""Fetch newly submitted blockchain papers from arXiv for a target date."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from blockchain_common import (
    ARXIV_BLOCKCHAIN_KEYWORDS as BLOCKCHAIN_KEYWORDS,
    GATE_KEYWORDS,
    format_arxiv_citation,
    normalize_space,
    passes_gate_filter,
    request_feed,
    resolve_target_date,
)
from webhook_utils import WEBHOOK_URL, send_papers_to_webhook

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def parse_entry(entry: ET.Element) -> dict[str, Any]:
    paper_id_url = entry.findtext("atom:id", default="", namespaces=ATOM_NS).strip()
    arxiv_id = paper_id_url.rsplit("/", maxsplit=1)[-1] if paper_id_url else ""
    title = normalize_space(entry.findtext("atom:title", default="", namespaces=ATOM_NS))
    summary = normalize_space(entry.findtext("atom:summary", default="", namespaces=ATOM_NS))
    published = entry.findtext("atom:published", default="", namespaces=ATOM_NS).strip()
    updated = entry.findtext("atom:updated", default="", namespaces=ATOM_NS).strip()
    published_date = published[:10] if len(published) >= 10 else ""
    published_year = published_date[:4] if published_date else ""
    authors = [
        normalize_space(author.findtext("atom:name", default="", namespaces=ATOM_NS))
        for author in entry.findall("atom:author", ATOM_NS)
    ]
    categories = [cat.attrib.get("term", "").strip() for cat in entry.findall("atom:category", ATOM_NS)]
    doi = entry.findtext("arxiv:doi", default="", namespaces=ATOM_NS).strip()
    journal_ref = entry.findtext("arxiv:journal_ref", default="", namespaces=ATOM_NS).strip()
    comment = entry.findtext("arxiv:comment", default="", namespaces=ATOM_NS).strip()

    pdf_url = ""
    for link in entry.findall("atom:link", ATOM_NS):
        href = link.attrib.get("href", "").strip()
        title_attr = link.attrib.get("title", "").strip().lower()
        if title_attr == "pdf" or href.endswith(".pdf"):
            pdf_url = href
            break

    citation = format_arxiv_citation(authors, title, published_year, arxiv_id)
    return {
        "arxiv_id": arxiv_id,
        "title": title,
        "url": paper_id_url,
        "pdf_url": pdf_url,
        "authors": authors,
        "abstract": summary,
        "published": published,
        "updated": updated,
        "published_date": published_date,
        "categories": categories,
        "doi": doi or None,
        "journal_ref": journal_ref or None,
        "comment": comment or None,
        "citation": citation,
    }


def build_search_query(keywords: list[str]) -> str:
    """Build arXiv search query with OR logic for multiple keywords."""
    quoted_terms = []
    for kw in keywords:
        if " " in kw:
            quoted_terms.append(f'all:"{kw}"')
        else:
            quoted_terms.append(f"all:{kw}")
    return " OR ".join(quoted_terms)


def fetch_papers_for_keyword(
    target_date: date, keyword: str, seen_ids: set[str]
) -> list[dict[str, Any]]:
    """Fetch papers for a single keyword, skipping already seen arxiv_ids."""
    target_iso = target_date.isoformat()
    papers: list[dict[str, Any]] = []
    per_page = 100
    start = 0
    max_pages = 5

    if " " in keyword:
        search_term = f'all:"{keyword}"'
    else:
        search_term = f"all:{keyword}"

    for _ in range(max_pages):
        params = {
            "search_query": search_term,
            "start": start,
            "max_results": per_page,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        url = f"{ARXIV_API_URL}?{urllib.parse.urlencode(params)}"
        try:
            data = request_feed(url)
        except Exception:
            break
        root = ET.fromstring(data)
        entries = root.findall("atom:entry", ATOM_NS)
        if not entries:
            break

        should_stop = False
        for entry in entries:
            paper = parse_entry(entry)
            paper_date = paper["published_date"]
            arxiv_id = paper["arxiv_id"]
            if paper_date == target_iso:
                if arxiv_id and arxiv_id not in seen_ids:
                    seen_ids.add(arxiv_id)
                    papers.append(paper)
            elif paper_date and paper_date < target_iso:
                should_stop = True
                break

        if should_stop:
            break
        start += per_page

    return papers


def fetch_papers_for_date(
    target_date: date, keywords: list[str] | None = None, gate_keywords: list[str] | None = None
) -> tuple[list[dict[str, Any]], list[str]]:
    """Fetch papers for all keywords, deduplicating by arxiv_id.
    
    Returns a tuple of (papers, keywords_used).
    """
    if keywords is None:
        keywords = BLOCKCHAIN_KEYWORDS
    if gate_keywords is None:
        gate_keywords = GATE_KEYWORDS

    seen_ids: set[str] = set()
    all_papers: list[dict[str, Any]] = []

    for keyword in keywords:
        papers = fetch_papers_for_keyword(target_date, keyword, seen_ids)
        all_papers.extend([paper for paper in papers if passes_gate_filter(paper, gate_keywords)])
        time.sleep(0.5)

    all_papers.sort(key=lambda p: p["published"], reverse=True)
    return all_papers, keywords


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch arXiv blockchain papers by target publication date."
    )
    parser.add_argument(
        "--date",
        help="Target date in YYYY-MM-DD format. Defaults to yesterday in UTC.",
    )
    parser.add_argument(
        "--output-dir",
        default="data",
        help="Output directory for generated JSON files (default: data).",
    )
    parser.add_argument(
        "--webhook-url",
        default=WEBHOOK_URL,
        help="Webhook URL used to send each fetched paper.",
    )
    args = parser.parse_args()

    target_date = resolve_target_date(args.date)
    papers, keywords_used = fetch_papers_for_date(target_date=target_date)

    payload = {
        "date": target_date.isoformat(),
        "query": {
            "source": "arXiv API",
            "keywords": keywords_used,
            "keyword_count": len(keywords_used),
            "gate_keywords": GATE_KEYWORDS,
            "gate_keyword_count": len(GATE_KEYWORDS),
            "sort_by": "submittedDate desc",
        },
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "paper_count": len(papers),
        "papers": papers,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{target_date.isoformat()}_arxiv_blockchain.json"
    output_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved {len(papers)} paper(s) to {output_file}")
    success, failed = send_papers_to_webhook(papers, webhook_url=args.webhook_url)
    print(f"Webhook delivery complete: success={success}, failed={failed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
