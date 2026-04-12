#!/usr/bin/env python3
"""Fetch newly submitted blockchain papers from arXiv for a target date."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

BLOCKCHAIN_KEYWORDS = [
    # Core blockchain terms
    "blockchain",
    "distributed ledger",
    "DLT",
    # Consensus mechanisms
    "proof of work",
    "proof of stake",
    "PoW consensus",
    "PoS consensus",
    "Byzantine fault tolerance",
    "BFT consensus",
    "PBFT",
    # Cryptocurrencies and tokens
    "cryptocurrency",
    "Bitcoin",
    "Ethereum",
    "smart contract",
    "token economy",
    "tokenization",
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
    "liquidity pool",
    "yield farming",
    "automated market maker",
    "AMM",
    # NFT and digital assets
    "NFT",
    "non-fungible token",
    "digital asset",
    # Layer 2 and scaling
    "layer 2",
    "rollup",
    "zero knowledge proof",
    "zk-SNARK",
    "zk-STARK",
    "ZKP",
    "state channel",
    "sidechain",
    "sharding",
    # Privacy and security
    "ring signature",
    "homomorphic encryption blockchain",
    "Merkle tree",
    "hash chain",
    # DAOs and governance
    "DAO",
    "decentralized autonomous organization",
    "on-chain governance",
    # Cross-chain
    "cross-chain",
    "interoperability blockchain",
    "atomic swap",
    "bridge protocol",
    # Mining and validators
    "mining pool",
    "validator node",
    "staking",
    # Identity and credentials
    "self-sovereign identity",
    "SSI",
    "decentralized identity",
    "DID",
    "verifiable credential",
]


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def request_feed(url: str, retries: int = 3, sleep_seconds: float = 2.0) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            if attempt < retries:
                time.sleep(sleep_seconds * attempt)
    assert last_error is not None
    raise last_error


def build_bibtex_key(first_author: str, published_year: str, arxiv_id: str) -> str:
    author_token = re.sub(r"[^A-Za-z0-9]", "", first_author.split()[-1]) or "author"
    id_token = re.sub(r"[^A-Za-z0-9]", "", arxiv_id)
    return f"{author_token}{published_year}{id_token}"


def format_citation(authors: list[str], title: str, year: str, arxiv_id: str) -> dict[str, str]:
    author_text = ", ".join(authors)
    text_citation = f"{author_text} ({year}). {title}. arXiv:{arxiv_id}"
    bibtex_key = build_bibtex_key(authors[0] if authors else "author", year, arxiv_id)
    bibtex = (
        f"@article{{{bibtex_key},\n"
        f"  title={{{title}}},\n"
        f"  author={{{author_text}}},\n"
        f"  journal={{arXiv preprint arXiv:{arxiv_id}}},\n"
        f"  year={{{year}}}\n"
        f"}}"
    )
    return {"text": text_citation, "bibtex": bibtex}


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

    citation = format_citation(authors, title, published_year, arxiv_id)
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
    target_date: date, keywords: list[str] | None = None
) -> tuple[list[dict[str, Any]], list[str]]:
    """Fetch papers for all keywords, deduplicating by arxiv_id.
    
    Returns a tuple of (papers, keywords_used).
    """
    if keywords is None:
        keywords = BLOCKCHAIN_KEYWORDS

    seen_ids: set[str] = set()
    all_papers: list[dict[str, Any]] = []

    for keyword in keywords:
        papers = fetch_papers_for_keyword(target_date, keyword, seen_ids)
        all_papers.extend(papers)
        time.sleep(0.5)

    all_papers.sort(key=lambda p: p["published"], reverse=True)
    return all_papers, keywords


def resolve_target_date(date_input: str | None) -> date:
    if date_input:
        return datetime.strptime(date_input, "%Y-%m-%d").date()
    return (datetime.now(timezone.utc) - timedelta(days=1)).date()


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
    args = parser.parse_args()

    target_date = resolve_target_date(args.date)
    papers, keywords_used = fetch_papers_for_date(target_date=target_date)

    payload = {
        "date": target_date.isoformat(),
        "query": {
            "source": "arXiv API",
            "keywords": keywords_used,
            "keyword_count": len(keywords_used),
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
