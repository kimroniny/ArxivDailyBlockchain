# AGENTS.md

## Cursor Cloud specific instructions

This repository (`ArxivDailyBlockchain`) aggregates blockchain-related papers from arXiv and IACR ePrint Archive.

### Prerequisites

- Python 3.8 or later (uses only standard library, no external dependencies required)

### Running the Scripts

#### arXiv Papers

Fetch blockchain papers from arXiv for a specific date:

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

#### IACR ePrint Papers

Fetch blockchain/cryptography papers from IACR ePrint Archive for a specific date:

```bash
python scripts/fetch_eprint_daily.py --date YYYY-MM-DD
```

Fetch papers for yesterday (default):

```bash
python scripts/fetch_eprint_daily.py
```

Specify output directory:

```bash
python scripts/fetch_eprint_daily.py --date 2026-04-08 --output-dir data
```

### Output

Papers are saved as JSON files in the `data/` directory with the naming patterns:
- arXiv: `{date}_arxiv_blockchain.json`
- ePrint: `{date}_eprint_blockchain.json`

#### arXiv JSON Structure

Each arXiv JSON file contains:
- `date`: Target date
- `query`: Query metadata (source, keywords list, keyword_count, sort order)
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

#### ePrint JSON Structure

Each ePrint JSON file contains:
- `date`: Target date
- `query`: Query metadata (source, keywords list, keyword_count, filter type)
- `generated_at_utc`: Timestamp of when the file was generated
- `paper_count`: Number of papers found
- `papers`: Array of paper objects with:
  - `eprint_id`: Paper identifier (e.g., "2026/123")
  - `title`: Paper title
  - `url`: Link to paper page
  - `pdf_url`: Direct PDF link
  - `authors`: List of authors
  - `abstract`: Full abstract
  - `published`/`published_date`: Timestamps
  - `category`: ePrint category
  - `license`: License URL
  - `citation`: Text and BibTeX citation formats

### Testing

No automated tests exist yet. To verify the scripts work:

```bash
# Test arXiv script
python scripts/fetch_arxiv_blockchain_daily.py --date 2026-04-08
cat data/2026-04-08_arxiv_blockchain.json

# Test ePrint script
python scripts/fetch_eprint_daily.py --date 2026-04-08
cat data/2026-04-08_eprint_blockchain.json
```
