from __future__ import annotations

import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

ARXIV_BLOCKCHAIN_KEYWORDS = [
    "blockchain",
    "distributed ledger",
    "DLT",
    "proof of work",
    "proof of stake",
    "PoW consensus",
    "PoS consensus",
    "Byzantine fault tolerance",
    "BFT consensus",
    "PBFT",
    "cryptocurrency",
    "Bitcoin",
    "Ethereum",
    "smart contract",
    "token economy",
    "tokenization",
    "stablecoin",
    "CBDC",
    "central bank digital currency",
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
    "NFT",
    "non-fungible token",
    "digital asset",
    "layer 2",
    "rollup",
    "zero knowledge proof",
    "zk-SNARK",
    "zk-STARK",
    "ZKP",
    "state channel",
    "sidechain",
    "sharding",
    "ring signature",
    "homomorphic encryption blockchain",
    "Merkle tree",
    "hash chain",
    "DAO",
    "decentralized autonomous organization",
    "on-chain governance",
    "cross-chain",
    "interoperability blockchain",
    "atomic swap",
    "bridge protocol",
    "mining pool",
    "validator node",
    "staking",
    "self-sovereign identity",
    "SSI",
    "decentralized identity",
    "DID",
    "verifiable credential",
]

EPRINT_BLOCKCHAIN_KEYWORDS = [
    "blockchain",
    "distributed ledger",
    "DLT",
    "proof of work",
    "proof of stake",
    "PoW",
    "PoS",
    "Byzantine fault tolerance",
    "BFT",
    "PBFT",
    "consensus protocol",
    "cryptocurrency",
    "Bitcoin",
    "Ethereum",
    "smart contract",
    "token",
    "stablecoin",
    "CBDC",
    "central bank digital currency",
    "decentralized finance",
    "DeFi",
    "Web3",
    "decentralized application",
    "dApp",
    "decentralized exchange",
    "DEX",
    "AMM",
    "automated market maker",
    "NFT",
    "non-fungible token",
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
    "ring signature",
    "Merkle tree",
    "hash chain",
    "DAO",
    "decentralized autonomous organization",
    "on-chain governance",
    "cross-chain",
    "interoperability",
    "atomic swap",
    "bridge protocol",
    "mining pool",
    "validator",
    "staking",
    "self-sovereign identity",
    "SSI",
    "decentralized identity",
    "DID",
    "verifiable credential",
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

GATE_KEYWORDS = [
    "blockchain",
    "distributed ledger",
    "smart contract",
    "bitcoin",
    "ethereum",
    "cryptocurrency",
    "stablecoin",
    "cbdc",
    "decentralized finance",
    "defi",
    "dao",
    "rollup",
    "layer 2",
    "cross-chain",
    "sidechain",
    "validator",
    "staking",
    "byzantine",
    "pbft",
]


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def contains_any_keyword(text: str, keywords: Sequence[str]) -> bool:
    lowered = text.lower()
    for kw in keywords:
        pattern = r"\b" + re.escape(kw.lower()) + r"\b"
        if re.search(pattern, lowered):
            return True
    return False


def matches_keywords(title: str, abstract: str, keywords: Sequence[str]) -> bool:
    return contains_any_keyword(f"{title} {abstract}", keywords)


def passes_gate_filter(paper: Mapping[str, Any], gate_keywords: Sequence[str]) -> bool:
    searchable_text = f"{paper.get('title', '')} {paper.get('abstract', '')}"
    return contains_any_keyword(searchable_text, gate_keywords)


def request_feed(
    url: str,
    retries: int = 3,
    sleep_seconds: float = 2.0,
    timeout: int = 30,
    headers: Mapping[str, str] | None = None,
) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, headers=dict(headers or {}))
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            if attempt < retries:
                time.sleep(sleep_seconds * attempt)
    assert last_error is not None
    raise last_error


def resolve_target_date(date_input: str | None) -> date:
    if date_input:
        return datetime.strptime(date_input, "%Y-%m-%d").date()
    return (datetime.now(timezone.utc) - timedelta(days=1)).date()


def build_bibtex_key(
    first_author: str,
    published_year: str,
    paper_id: str,
    id_prefix: str = "",
) -> str:
    author_token = re.sub(r"[^A-Za-z0-9]", "", first_author.split()[-1]) or "author"
    id_token = re.sub(r"[^A-Za-z0-9]", "", paper_id)
    return f"{author_token}{published_year}{id_prefix}{id_token}"


def format_arxiv_citation(
    authors: Sequence[str], title: str, year: str, arxiv_id: str
) -> dict[str, str]:
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


def format_eprint_citation(
    authors: Sequence[str], title: str, year: str, eprint_id: str
) -> dict[str, str]:
    author_text = ", ".join(authors)
    text_citation = f"{author_text} ({year}). {title}. IACR ePrint:{eprint_id}"
    bibtex_key = build_bibtex_key(
        authors[0] if authors else "author", year, eprint_id, id_prefix="eprint"
    )
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
