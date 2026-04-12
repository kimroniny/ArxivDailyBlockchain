# ArxivDailyBlockchain

Blockchain Daily papers on arXiv - A tool to fetch and aggregate blockchain-related research papers from arXiv.

## Features

- Fetch blockchain papers for any specified date
- Save paper metadata as structured JSON
- Includes title, authors, abstract, PDF links, and citations
- Generates both text and BibTeX citation formats

## Quick Start

```bash
# Fetch papers for a specific date
python scripts/fetch_arxiv_blockchain_daily.py --date 2026-04-08

# Fetch papers for yesterday (default)
python scripts/fetch_arxiv_blockchain_daily.py
```

## Output Format

Papers are saved to `data/{date}_arxiv_blockchain.json` with comprehensive metadata including:

- Paper ID, title, and abstract
- Authors list
- PDF and abstract URLs
- arXiv categories
- Text and BibTeX citations

## Requirements

- Python 3.8+ (no external dependencies - uses only standard library)
