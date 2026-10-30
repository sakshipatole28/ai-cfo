"""Compliance guard (rules layer). Blocks requests for security-specific buy/sell
instructions and catches advice-like or promissory wording in answers.

The ML classifier and LLM judge layers (plan §3.6) sit behind this rules layer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Patterns that mark a QUESTION as a request for a buy/sell call or a tip.
_QUESTION_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        # "Should I buy / sell / exit …": a request for a recommendation.
        "security-specific buy/sell request",
        re.compile(
            r"\b(should|shall|can|must)\s+(i|we|he|she|they|my client|the client|\w+)\s+"
            r"(buy|sell|invest in|exit|switch to|add|book)\b",
            re.I,
        ),
    ),
    (
        # "Which stocks should …": a request for a tip.
        "stock tip request",
        re.compile(
            r"\b(which|what|best)\s+(stocks?|shares?|funds?|schemes?)\s+(should|to|will)\b", re.I
        ),
    ),
    (
        # Hype words such as multibagger or guaranteed returns.
        "return promise request",
        re.compile(
            r"\b(multibagger|target price|guaranteed returns?|sure[- ]shot|double my money)\b", re.I
        ),
    ),
)

# Patterns that mark generated TEXT as advice or a promise.
_ANSWER_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        # "the client should buy …": a direct instruction.
        "direct buy/sell instruction",
        re.compile(r"\b(you|the client|he|she|they)\s+should\s+(buy|sell|exit|invest in)\b", re.I),
    ),
    (
        # "guaranteed", "risk-free returns"…: a promise of returns.
        "promise of returns",
        re.compile(
            r"\b(guarantee[ds]?|assured returns?|risk[- ]free returns?|will definitely)\b", re.I
        ),
    ),
)


@dataclass(frozen=True)
# The outcome of a check.
class GuardResult:
    # True if the text may pass.
    allowed: bool
    # Which rule fired, if blocked.
    reason: str | None = None


# Is this question allowed? Blocks requests for security-specific advice.
def check_question(question: str) -> GuardResult:
    # Try each rule.
    for reason, pattern in _QUESTION_RULES:
        # A rule matched anywhere in the question…
        if pattern.search(question):
            # …so block it and say why.
            return GuardResult(False, reason)
    # No rule matched: allowed.
    return GuardResult(True)


# Is this generated text allowed? Blocks advice and promises.
def check_answer(text: str) -> GuardResult:
    # Try each rule.
    for reason, pattern in _ANSWER_RULES:
        # A rule matched…
        if pattern.search(text):
            # …so block it and say why.
            return GuardResult(False, reason)
    # Clean.
    return GuardResult(True)
