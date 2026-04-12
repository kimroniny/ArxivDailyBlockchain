from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Sequence

WEBHOOK_URL = "https://www.kdocs.cn/chatflow/api/v2/func/webhook/3CFQc9h2RqjHFUMbY1KKJ73qi2I"


def post_paper_to_webhook(
    *,
    title: str,
    url: str,
    pdf_url: str,
    abstract: str,
    published_date: str,
    webhook_url: str = WEBHOOK_URL,
    retries: int = 3,
    sleep_seconds: float = 1.0,
) -> None:
    payload = {
        "title": title,
        "url": url,
        "pdf_url": pdf_url,
        "abstract": abstract,
        "published_date": published_date,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=20):
                return
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            if attempt < retries:
                time.sleep(sleep_seconds * attempt)

    assert last_error is not None
    raise last_error


def send_papers_to_webhook(
    papers: Sequence[dict[str, Any]], webhook_url: str = WEBHOOK_URL
) -> tuple[int, int]:
    success = 0
    failed = 0
    for paper in papers:
        try:
            post_paper_to_webhook(
                title=paper.get("title", ""),
                url=paper.get("url", ""),
                pdf_url=paper.get("pdf_url", ""),
                abstract=paper.get("abstract", ""),
                published_date=paper.get("published_date", ""),
                webhook_url=webhook_url,
            )
            success += 1
        except Exception:
            failed += 1
    return success, failed
