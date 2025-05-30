#!/usr/bin/env python3
"""
Page text splitter for embedding preparation.

Based on Azure sample:
https://github.com/Azure-Samples/azure-search-openai-demo/
  blob/main/app/backend/prepdocslib/textsplitter.py

Provides:
  - TextSplitter (abstract base class)
  - SentenceTextSplitter: sentence- and token-aware splitting with overlap
  - SimpleTextSplitter: fixed-length splitting
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Generator

import tiktoken

from page import Page, SplitPage

# Configure module logger
logger = logging.getLogger(__name__)

# Constants
ENCODING_MODEL = "text-embedding-ada-002"
STANDARD_WORD_BREAKS = [
    ",", ";", ":", " ", "(", ")", "[", "]", "{", "}", "\t", "\n",
]

CJK_WORD_BREAKS = [
    "、", "，", "；", "：", "（", "）", "【", "】", "「", "」", "『", "』",
    "〔", "〕", "〈", "〉", "《", "》", "〖", "〗", "〘", "〙", "〚", "〛",
    "〝", "〞", "〟", "〰", "–", "—", "‘", "’", "‚", "‛", "“", "”",
    "„", "‟", "‹", "›",
]

STANDARD_SENTENCE_ENDINGS = [".", "!", "?"]
CJK_SENTENCE_ENDINGS = ["。", "！", "？", "‼", "⁇", "⁈", "⁉"]

DEFAULT_SECTION_LENGTH = 1000       # ~400-500 tokens (English)
DEFAULT_OVERLAP_PERCENT = 10        # 10% overlap

# Token encoder for embedding model
encoder = tiktoken.encoding_for_model(ENCODING_MODEL)


class TextSplitter(ABC):
    """Abstract base for page-splitting strategies."""

    @abstractmethod
    def split_pages(
        self,
        pages: list[Page]
    ) -> Generator[SplitPage, None, None]:
        """Yield SplitPage chunks from a list of Page objects."""
        ...


class SentenceTextSplitter(TextSplitter):
    """
    Splits pages by sentences and token count with overlap,
    ensuring sections fit within embedding limits.
    """

    def __init__(
        self,
        max_tokens_per_section: int = 500,
        max_section_length: int = DEFAULT_SECTION_LENGTH,
        overlap_percent: int = DEFAULT_OVERLAP_PERCENT,
        sentence_search_limit: int = 100,
    ):
        self.max_tokens_per_section = max_tokens_per_section
        self.max_section_length = max_section_length
        self.section_overlap = int(max_section_length * overlap_percent / 100)
        self.sentence_search_limit = sentence_search_limit
        self.sentence_endings = STANDARD_SENTENCE_ENDINGS + CJK_SENTENCE_ENDINGS
        self.word_breaks = STANDARD_WORD_BREAKS + CJK_WORD_BREAKS

    def split_page_by_max_tokens(
        self,
        page_num: int,
        text: str
    ) -> Generator[SplitPage, None, None]:
        """
        Recursively split `text` so each chunk ≤ max_tokens_per_section.
        """
        tokens = encoder.encode(text)
        if len(tokens) <= self.max_tokens_per_section:
            yield SplitPage(page_num=page_num, text=text)
            return

        # Attempt to split near middle at a sentence boundary
        length = len(text)
        center = length // 2
        boundary = length // 3
        split_pos = -1

        for offset in range(boundary):
            left = center - offset
            right = center + offset
            if left > 0 and text[left] in self.sentence_endings:
                split_pos = left + 1
                break
            if right < length and text[right] in self.sentence_endings:
                split_pos = right + 1
                break

        if split_pos < 0:
            # Fallback: half-split with small overlap
            mid = length // 2
            overlap = int(length * (DEFAULT_OVERLAP_PERCENT / 100))
            first = text[: mid + overlap]
            second = text[mid - overlap :]
        else:
            first = text[:split_pos]
            second = text[split_pos:]

        yield from self.split_page_by_max_tokens(page_num, first)
        yield from self.split_page_by_max_tokens(page_num, second)

    def split_pages(
        self,
        pages: list[Page]
    ) -> Generator[SplitPage, None, None]:
        """
        Join texts, chunk by max_section_length with overlap,
        then apply token-based splitting per chunk.
        """
        all_text = "".join(p.text for p in pages)
        if not all_text.strip():
            return

        total_len = len(all_text)
        if total_len <= self.max_section_length:
            yield from self.split_page_by_max_tokens(
                page_num=self._find_page(pages, 0),
                text=all_text
            )
            return

        start = 0
        while start < total_len:
            end = min(start + self.max_section_length, total_len)
            # Extend end to sentence boundary or word break
            cursor = end
            last_word_break = -1
            while (
                cursor < total_len
                and cursor - end < self.sentence_search_limit
                and all_text[cursor] not in self.sentence_endings
            ):
                if all_text[cursor] in self.word_breaks:
                    last_word_break = cursor
                cursor += 1
            if cursor < total_len and last_word_break > 0:
                end = last_word_break + 1
            else:
                end = cursor

            chunk = all_text[start:end]
            yield from self.split_page_by_max_tokens(
                page_num=self._find_page(pages, start),
                text=chunk
            )

            start = end - self.section_overlap

    @staticmethod
    def _find_page(pages: list[Page], offset: int) -> int:
        """Find page_num corresponding to cumulative text offset."""
        for i in range(len(pages) - 1):
            if pages[i].offset <= offset < pages[i + 1].offset:
                return pages[i].page_num
        return pages[-1].page_num


class SimpleTextSplitter(TextSplitter):
    """
    Splits pages into fixed-size chunks oblivious to content.
    """

    def __init__(
        self,
        max_object_length: int = DEFAULT_SECTION_LENGTH
    ):
        self.max_object_length = max_object_length

    def split_pages(
        self,
        pages: list[Page]
    ) -> Generator[SplitPage, None, None]:
        """
        Join texts and yield fixed-length sections of max_object_length.
        """
        all_text = "".join(p.text for p in pages)
        if not all_text.strip():
            return

        length = len(all_text)
        if length <= self.max_object_length:
            yield SplitPage(page_num=0, text=all_text)
            return

        for idx in range(0, length, self.max_object_length):
            chunk = all_text[idx : idx + self.max_object_length]
            yield SplitPage(page_num=idx // self.max_object_length, text=chunk)


# End of module
