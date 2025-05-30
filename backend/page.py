#!/usr/bin/env python3
"""
Data models for pages and split-page chunks using dataclasses.

Defines:
  - Page: holds full-page text with position and metadata.
  - SplitPage: holds a section of text derived from a Page.
"""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class Page:
    """
    Represents an original scraped page.

    Attributes:
        page_num: Index of the page in the document.
        offset: Character offset where this page's text begins.
        text: Full text content of the page.
        meta: Arbitrary metadata (e.g., url, title, category, images).
    """
    page_num: int
    offset: int
    text: str
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SplitPage:
    """
    Represents a text chunk derived from a Page.

    Attributes:
        page_num: Page index from which the chunk originates.
        text: Text content of the chunk.
        meta: Inherited metadata from the source page.
    """
    page_num: int
    text: str
    meta: Dict[str, Any] = field(default_factory=dict)
