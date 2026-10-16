"""Compliance guard (rules layer). Blocks requests for security-specific buy/sell
instructions and catches advice-like or promissory wording in answers.

The ML classifier and LLM judge layers (plan §3.6) sit behind this rules layer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_QUESTION_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "security-specific buy/sell request",
        re.compile(
            r"\b(should|shall|can|must)\s+(i|we|he|she|they|my client|the client|\w+)\s+"
            r"(buy|sell|invest in|exit|switch to|add|book)\b",
            re.I,
        ),
    ),
    (
        "stock tip request",
        re.compile(
            r"\b(which|what|best)\s+(stocks?|shares?|funds?|schemes?)\s+(should|to|will)\b", re.I
        ),
    ),
    (
        "return promise request",
        re.compile(
            r"\b(multibagger|target price|guaranteed returns?|sure[- ]shot|double my money)\b", re.I
        ),
    ),
)

_ANSWER_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "direct buy/sell instruction",
        re.compile(r"\b(you|the client|he|she|they)\s+should\s+(buy|sell|exit|invest in)\b", re.I),
    ),
    (
        "promise of returns",
        re.compile(
            r"\b(guarantee[ds]?|assured returns?|risk[- ]free returns?|will definitely)\b", re.I
        ),
    ),
)


@dataclass(frozen=True)
class GuardResult:
    allowed: bool
    reason: str | None = None


def check_question(question: str) -> GuardResult:
    for reason, pattern in _QUESTION_RULES:
        if pattern.search(question):
            return GuardResult(False, reason)
    return GuardResult(True)


def check_answer(text: str) -> GuardResult:
    for reason, pattern in _ANSWER_RULES:
        if pattern.search(text):
            return GuardResult(False, reason)
    return GuardResult(True)
