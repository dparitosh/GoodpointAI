"""Embeddings service helper.

Goal: keep backend dependencies light.

We avoid heavy local ML libs (e.g., sentence-transformers) in the default runtime.
Instead, we optionally call a user-provided embeddings endpoint.

Expected response shape:
  {"embedding": [..floats..]}

Configure via environment variable:
  EMBEDDINGS_URL=http://host:port/embeddings
"""

from __future__ import annotations

import os
import logging
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)


def get_embedding_for_text(text: str, *, timeout_s: float = 10.0) -> Optional[List[float]]:
    """Get an embedding for `text` via EMBEDDINGS_URL.

    Returns None when not configured or when the service fails.
    """
    embeddings_url = (os.getenv("EMBEDDINGS_URL") or "").strip()
    if not embeddings_url:
        return None

    try:
        with httpx.Client(timeout=timeout_s) as client:
            resp = client.post(embeddings_url, json={"text": text})
            resp.raise_for_status()
            payload = resp.json()
            embedding = payload.get("embedding")
            if not isinstance(embedding, list) or not embedding:
                return None
            # Ensure all entries are floats
            try:
                return [float(x) for x in embedding]
            except Exception:  # pylint: disable=broad-exception-caught
                return None
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.debug("Embedding request failed: %s", exc)
        return None
