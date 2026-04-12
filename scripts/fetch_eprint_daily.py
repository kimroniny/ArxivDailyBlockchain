#!/usr/bin/env python3
"""Fetch blockchain/cryptocurrency related papers from IACR ePrint Archive for a target date."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

EPRINT_RSS_URL = "https://eprint.iacr.org/rss/rss.xml"

BLOCKCHAIN_KEYWORDS = [
    # Core blockchain terms
    "blockchain",
    "distributed ledger",
    "DLT",
    # Consensus mechanisms
    "proof of work",
    "proof of stake",
    "PoW",
    "PoS",
    "Byzantine fault tolerance",
    "BFT",
    "PBFT",
    "consensus protocol",
    # Cryptocurrencies and tokens
    "cryptocurrency",
    "Bitcoin",
    "Ethereum",
    "smart contract",
    "token",
    "stablecoin",
    "CBDC",
    "central bank digital currency",
    # DeFi and Web3
    "decentralized finance",
    "DeFi",
    "Web3",
    "decentralized application",
    "dApp",
    "decentralized exchange",
    "DEX",
    "AMM",
    "automated market maker",
    # NFT and digital assets
    "NFT",
    "non-fungible token",
    # Layer 2 and scaling
    "layer 2",
    "rollup",
    "zero knowledge proof",
    "zero-knowledge proof",
    "zk-SNARK",
    "zk-STARK",
    "zkSNARK",
    "zkSTARK",
    "ZKP",
    "state channel",
    "sidechain",
    "sharding",
    # Privacy
    "ring signature",
    "Merkle tree",
    "hash chain",
    # DAOs and governance
    "DAO",
    "decentralized autonomous organization",
    "on-chain governance",
    # Cross-chain
    "cross-chain",
    "interoperability",
    "atomic swap",
    "bridge protocol",
    # Mining and validators
    "mining pool",
    "validator",
    "staking",
    # Identity
    "self-sovereign identity",
    "SSI",
    "decentralized identity",
    "DID",
    "verifiable credential",
    # Cryptographic primitives commonly used in blockchain
    "threshold signature",
    "multi-party computation",
    "MPC",
    "secure computation",
    "commitment scheme",
    "verifiable computation",
    "succinct argument",
    "SNARK",
    "STARK",
]

DC_NS = "http://purl.org/dc/elements/1.1/"


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def request_feed(url: str, retries: int = 3, sleep_seconds: float = 2.0) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "ArxivDailyBlockchain/1.0 (research tool)"},
            )
            with urllib.request.urlopen(req, timeout=60) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            if attempt < retries:
                time.sleep(sleep_seconds * attempt)
    assert last_error is not None
    raise last_error


def build_bibtex_key(first_author: str, published_year: str, eprint_id: str) -> str:
    author_token = re.sub(r"[^A-Za-z0-9]", "", first_author.split()[-1]) or "author"
    id_token = re.sub(r"[^A-Za-z0-9]", "", eprint_id)
    return f"{author_token}{published_year}eprint{id_token}"


def format_citation(authors: list[str], title: str, year: str, eprint_id: str) -> dict[str, str]:
    author_text = ", ".join(authors)
    text_citation = f"{author_text} ({year}). {title}. IACR ePrint:{eprint_id}"
    bibtex_key = build_bibtex_key(authors[0] if authors else "author", year, eprint_id)
    bibtex = (
        f"@misc{{{bibtex_key},\n"
        f"  title={{{title}}},\n"
        f"  author={{{author_text}}},\n"
        f"  howpublished={{Cryptology ePrint Archive, Paper {eprint_id}}},\n"
        f"  year={{{year}}},\n"
        f"  url={{https://eprint.iacr.org/{eprint_id}}}\n"
        f"}}"
    )
    return {"text": text_citation, "bibtex": bibtex}


def parse_pubdate(pubdate_str: str) -> tuple[str, str]:
    """Parse RSS pubDate and return (date_iso, full_timestamp)."""
    if not pubdate_str:
        return "", ""
    try:
        dt = datetime.strptime(pubdate_str, "%a, %d %b %Y %H:%M:%S %z")
        return dt.strftime("%Y-%m-%d"), dt.isoformat()
    except ValueError:
        return "", pubdate_str


def matches_keywords(title: str, abstract: str, keywords: list[str]) -> bool:
    """Check if title or abstract contains any of the keywords (case-insensitive)."""
    text = f"{title} {abstract}".lower()
    for kw in keywords:
        pattern = r"\b" + re.escape(kw.lower()) + r"\b"
        if re.search(pattern, text):
            return True
    return False


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

    citation = format_citation(authors, title, published_year, eprint_id)

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
    target_date: date, keywords: list[str] | None = None
) -> tuple[list[dict[str, Any]], list[str]]:
    """Fetch ePrint papers for a specific date that match blockchain keywords.

    Returns a tuple of (papers, keywords_used).
    """
    if keywords is None:
        keywords = BLOCKCHAIN_KEYWORDS

    target_iso = target_date.isoformat()

    print(f"Fetching ePrint RSS feed...")
    data = request_feed(EPRINT_RSS_URL)
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
                seen_ids.add(eprint_id)
                papers.append(paper)

    papers.sort(key=lambda p: p.get("published", ""), reverse=True)
    return papers, keywords


def resolve_target_date(date_input: str | None) -> date:
    if date_input:
        return datetime.strptime(date_input, "%Y-%m-%d").date()
    return (datetime.now(timezone.utc) - timedelta(days=1)).date()


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
    return 0


if __name__ == "__main__":
    sys.exit(main())
