#!/usr/bin/env python3
"""Fetch blockchain/cryptocurrency related papers from IACR ePrint Archive for a target date."""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from blockchain_common import (
    EPRINT_BLOCKCHAIN_KEYWORDS as BLOCKCHAIN_KEYWORDS,
    GATE_KEYWORDS,
    format_eprint_citation,
    matches_keywords,
    normalize_space,
    passes_gate_filter,
    request_feed,
    resolve_target_date,
)
from webhook_utils import WEBHOOK_URL, send_papers_to_webhook

EPRINT_RSS_URL = "https://eprint.iacr.org/rss/rss.xml"

DC_NS = "http://purl.org/dc/elements/1.1/"

def parse_pubdate(pubdate_str: str) -> tuple[str, str]:
    """Parse RSS pubDate and return (date_iso, full_timestamp)."""
    if not pubdate_str:
        return "", ""
    try:
        dt = datetime.strptime(pubdate_str, "%a, %d %b %Y %H:%M:%S %z")
        return dt.strftime("%Y-%m-%d"), dt.isoformat()
    except ValueError:
        return "", pubdate_str

def parse_item(item: ET.Element, keywords: list[str]) -> dict[str, Any] | None:
    """Parse an RSS item and return paper dict if it matches keywords."""
    title = normalize_space(item.findtext("title", default=""))
    description = normalize_space(item.findtext("description", default=""))
    link = item.findtext("link", default="").strip()
    guid = item.findtext("guid", default="").strip()
    pubdate_str = item.findtext("pubDate", default="").strip()
    category = item.findtext("category", default="").strip()

    eprint_id = ""
    if link:
        match = re.search(r"/(\d{4}/\d+)(?:\.pdf)?$", link)
        if match:
            eprint_id = match.group(1)

    authors: list[str] = []
    for creator in item.findall(f"{{{DC_NS}}}creator"):
        if creator.text:
            authors.append(normalize_space(creator.text))

    license_url = ""
    rights_elem = item.find(f"{{{DC_NS}}}rights")
    if rights_elem is not None and rights_elem.text:
        license_url = rights_elem.text.strip()

    pdf_url = ""
    enclosure = item.find("enclosure")
    if enclosure is not None:
        pdf_url = enclosure.attrib.get("url", "").strip()

    if not matches_keywords(title, description, keywords):
        return None

    published_date, published_full = parse_pubdate(pubdate_str)
    published_year = published_date[:4] if published_date else ""

    citation = format_eprint_citation(authors, title, published_year, eprint_id)

    return {
        "eprint_id": eprint_id,
        "title": title,
        "url": link or guid,
        "pdf_url": pdf_url,
        "authors": authors,
        "abstract": description,
        "published": published_full,
        "published_date": published_date,
        "category": category,
        "license": license_url or None,
        "citation": citation,
    }


def fetch_papers_for_date(
    target_date: date, keywords: list[str] | None = None, gate_keywords: list[str] | None = None
) -> tuple[list[dict[str, Any]], list[str]]:
    """Fetch ePrint papers for a specific date that match blockchain keywords.

    Returns a tuple of (papers, keywords_used).
    """
    if keywords is None:
        keywords = BLOCKCHAIN_KEYWORDS
    if gate_keywords is None:
        gate_keywords = GATE_KEYWORDS

    target_iso = target_date.isoformat()

    print(f"Fetching ePrint RSS feed...")
    data = request_feed(
        EPRINT_RSS_URL,
        timeout=60,
        headers={"User-Agent": "ArxivDailyBlockchain/1.0 (research tool)"},
    )
    root = ET.fromstring(data)

    channel = root.find("channel")
    if channel is None:
        return [], keywords

    papers: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for item in channel.findall("item"):
        paper = parse_item(item, keywords)
        if paper is None:
            continue

        paper_date = paper.get("published_date", "")
        eprint_id = paper.get("eprint_id", "")

        if paper_date == target_iso:
            if eprint_id and eprint_id not in seen_ids:
                if passes_gate_filter(paper, gate_keywords):
                    seen_ids.add(eprint_id)
                    papers.append(paper)

    papers.sort(key=lambda p: p.get("published", ""), reverse=True)
    return papers, keywords

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch IACR ePrint blockchain/crypto papers by target publication date."
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
    print(f"Fetching ePrint papers for {target_date}...")

    papers, keywords_used = fetch_papers_for_date(target_date=target_date)

    payload = {
        "date": target_date.isoformat(),
        "query": {
            "source": "IACR ePrint Archive",
            "keywords": keywords_used,
            "keyword_count": len(keywords_used),
            "gate_keywords": GATE_KEYWORDS,
            "gate_keyword_count": len(GATE_KEYWORDS),
            "filter": "keyword match in title/abstract",
        },
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "paper_count": len(papers),
        "papers": papers,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{target_date.isoformat()}_eprint_blockchain.json"
    output_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved {len(papers)} paper(s) to {output_file}")
    success, failed = send_papers_to_webhook(papers, webhook_url=args.webhook_url)
    print(f"Webhook delivery complete: success={success}, failed={failed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
