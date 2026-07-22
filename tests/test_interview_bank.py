from __future__ import annotations

import json
import re
from pathlib import Path


def test_question_bank_has_required_count_and_challenge_mode() -> None:
    text = Path("docs/INTERVIEW_QUESTION_BANK.md").read_text(encoding="utf-8")
    ids = re.findall(r"^### (Q\d{2}):", text, flags=re.MULTILINE)
    challenge_text = text.split("## Challenge Mode", maxsplit=1)[1]
    challenge_ids = re.findall(r"^### (Q\d{2}):", challenge_text, flags=re.MULTILINE)

    assert len(ids) >= 75
    assert len(challenge_ids) >= 15
    assert len(ids) == len(set(ids))


def test_question_answers_have_required_sections() -> None:
    text = Path("docs/INTERVIEW_QUESTION_BANK.md").read_text(encoding="utf-8")
    blocks = re.split(r"^### Q\d{2}:.*$", text, flags=re.MULTILINE)[1:]

    assert blocks
    for block in blocks[:75]:
        assert "Direct answer:" in block
        assert "Technical detail:" in block
        assert "Evidence:" in block
        assert "Limitation:" in block
        assert "Follow-up:" in block


def test_whiteboard_derivations_are_present() -> None:
    text = Path("docs/INTERVIEW_QUESTION_BANK.md").read_text(encoding="utf-8")

    for heading in [
        "Critical Fractile",
        "Pinball Loss",
        "Conformal Interval Adjustment",
        "Lead-Time Demand",
        "Stock Conservation",
        "Basic Service-Constrained Optimization",
    ]:
        assert heading in text


def test_flash_cards_reference_existing_question_ids() -> None:
    text = Path("docs/INTERVIEW_QUESTION_BANK.md").read_text(encoding="utf-8")
    ids = set(re.findall(r"^### (Q\d{2}):", text, flags=re.MULTILINE))
    cards = json.loads(Path("configs/interview_flash_cards.json").read_text(encoding="utf-8"))

    assert len(cards) >= 15
    assert {card["id"] for card in cards}.issubset(ids)
    assert all(card["front"] and card["back"] for card in cards)
