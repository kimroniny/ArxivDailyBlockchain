# AGENTS.md

## Cursor Cloud specific instructions

This repository (`ArxivDailyBlockchain`) aggregates blockchain-related papers from arXiv.

### Prerequisites

- Python 3.8 or later (uses only standard library, no external dependencies required)

### Running the Script

Fetch blockchain papers for a specific date:

```bash
python scripts/fetch_arxiv_blockchain_daily.py --date YYYY-MM-DD
```

Fetch papers for yesterday (default):

```bash
python scripts/fetch_arxiv_blockchain_daily.py
```

Specify output directory:

```bash
python scripts/fetch_arxiv_blockchain_daily.py --date 2026-04-08 --output-dir data
```

### Output

Papers are saved as JSON files in the `data/` directory with the naming pattern:
`{date}_arxiv_blockchain.json`

Each JSON file contains:
- `date`: Target date
- `query`: Query metadata (source, keyword, sort order)
- `generated_at_utc`: Timestamp of when the file was generated
- `paper_count`: Number of papers found
- `papers`: Array of paper objects with:
  - `arxiv_id`: Paper identifier
  - `title`: Paper title
  - `url`: Link to abstract page
  - `pdf_url`: Direct PDF link
  - `authors`: List of authors
  - `abstract`: Full abstract
  - `published`/`updated`: Timestamps
  - `categories`: arXiv categories
  - `doi`, `journal_ref`, `comment`: Optional metadata
  - `citation`: Text and BibTeX citation formats

### Testing

No automated tests exist yet. To verify the script works:

```bash
python scripts/fetch_arxiv_blockchain_daily.py --date 2026-04-08
cat data/2026-04-08_arxiv_blockchain.json
```
