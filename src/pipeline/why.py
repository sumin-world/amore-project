"""
Why Report generation with hierarchical LLM fallback.

Priority: Groq (free) → Claude (paid) → deterministic rules.
Each provider is isolated so one failure never blocks the next.
"""

import logging
import os
import json
from datetime import datetime

from sqlalchemy.orm import Session

from src.models import ProductSnapshot, WhyReport

logger = logging.getLogger(__name__)


# ── image diff ───────────────────────────────────────────────────────────

def compute_image_diff_score(prev: ProductSnapshot, curr: ProductSnapshot) -> dict:
    """Compare pHash fingerprints; >10-bit Hamming distance = meaningful change."""
    if not prev.image_phash or not curr.image_phash:
        return {"changed": False, "score": 0, "distance": 0}
    try:
        distance = bin(int(prev.image_phash, 16) ^ int(curr.image_phash, 16)).count("1")
        return {
            "changed": distance > 10,
            "score": round(min(distance / 64.0 * 100, 100), 1),
            "distance": distance,
        }
    except Exception:
        return {"changed": False, "score": 0, "distance": 0}


# ── common prompt ────────────────────────────────────────────────────────

def _build_prompt(prev: ProductSnapshot, curr: ProductSnapshot, evidence: dict) -> str:
    dr = curr.rank - prev.rank
    dp = curr.price - prev.price
    drev = curr.review_count - prev.review_count
    drat = curr.rating - prev.rating
    img = evidence.get("image_diff", {}).get("changed", False)

    return (
        f"E-commerce product ranking change analysis:\n\n"
        f"Product: {curr.title}\n"
        f"ID: {curr.product_id}\n"
        f"Window: {prev.captured_at:%m/%d %H:%M} → {curr.captured_at:%m/%d %H:%M}\n\n"
        f"Changes:\n"
        f"- Rank: #{prev.rank} → #{curr.rank} (Δ {dr:+d})\n"
        f"- Price: ${prev.price:.2f} → ${curr.price:.2f} (Δ ${dp:+.2f})\n"
        f"- Reviews: {prev.review_count:,} → {curr.review_count:,} (Δ {drev:+,d})\n"
        f"- Rating: {prev.rating:.1f} → {curr.rating:.1f} (Δ {drat:+.1f})\n"
        f"- Thumbnail: {'changed' if img else 'unchanged'}\n\n"
        f"Provide:\n"
        f"1. Top 2 causes of the ranking change\n"
        f"2. Impact level (HIGH / MID / LOW)\n"
        f"3. Whether urgent action is needed\n"
        f"4. 1-2 action items\n\n"
        f"Be concise (≤150 words). Use this format:\n"
        f'"Rank 3→9 (+6) | Cause: price cut $5 (HIGH) + review surge +50 (MID) '
        f'| Action: monitor competitor pricing"'
    )


# ── LLM providers ───────────────────────────────────────────────────────

def _try_groq(prev, curr, evidence) -> str | None:
    try:
        from groq import Groq

        key = os.getenv("GROQ_API_KEY", "").strip()
        if not key:
            return None
        resp = Groq(api_key=key).chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": _build_prompt(prev, curr, evidence)}],
            temperature=0.3,
            max_tokens=300,
        )
        text = resp.choices[0].message.content.strip()
        logger.info("Groq OK (%d chars)", len(text))
        return text
    except Exception as e:
        logger.warning("Groq failed: %s", e)
        return None


def _try_claude(prev, curr, evidence) -> str | None:
    try:
        from anthropic import Anthropic

        key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not key:
            return None
        msg = Anthropic(api_key=key).messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            temperature=0.3,
            messages=[{"role": "user", "content": _build_prompt(prev, curr, evidence)}],
        )
        text = msg.content[0].text.strip()
        logger.info("Claude OK (%d chars)", len(text))
        return text
    except Exception as e:
        logger.warning("Claude failed: %s", e)
        return None


# ── rule-based fallback ──────────────────────────────────────────────────

def _rule_fallback(prev: ProductSnapshot, curr: ProductSnapshot, evidence: dict) -> str:
    dr = curr.rank - prev.rank
    dp = curr.price - prev.price
    drev = curr.review_count - prev.review_count
    drat = curr.rating - prev.rating

    header = (
        f"Rank {prev.rank}→{curr.rank} (Δ {dr:+d})"
        if dr != 0
        else f"Rank stable at #{curr.rank}"
    )

    causes = []
    if abs(dp) > 1.5:
        causes.append(f"price {'cut' if dp < 0 else 'hike'} ${abs(dp):.2f}")
    if drev > 100:
        causes.append(f"review surge +{drev}")
    elif drev > 30:
        causes.append(f"review growth +{drev}")
    if abs(drat) >= 0.2:
        causes.append(f"rating {'up' if drat > 0 else 'down'} {abs(drat):.1f}")
    if evidence.get("image_diff", {}).get("changed"):
        causes.append("thumbnail changed")

    body = " + ".join(causes) if causes else "no significant drivers"
    urgency = " → urgent action needed" if dr > 3 else (" → monitor" if dr > 0 else "")

    return f"{header} | {body}{urgency}"


# ── public API ───────────────────────────────────────────────────────────

def build_why_report(
    prev: ProductSnapshot,
    curr: ProductSnapshot,
    evidence: dict,
) -> str:
    """Generate a Why Report: Groq → Claude → rules. Always returns a string."""
    if os.getenv("USE_GROQ", "true").lower() == "true":
        result = _try_groq(prev, curr, evidence)
        if result:
            return result

    if os.getenv("USE_CLAUDE", "false").lower() == "true":
        result = _try_claude(prev, curr, evidence)
        if result:
            return result

    logger.info("Using rule-based fallback")
    return _rule_fallback(prev, curr, evidence)


def upsert_report(
    db: Session,
    source: str,
    market: str,
    category: str,
    product_id: str,
    window_start: datetime,
    window_end: datetime,
    summary: str,
    evidence_json: str,
) -> None:
    """Insert or update a Why Report (deduplicated by product + time window)."""
    existing = db.query(WhyReport).filter(
        WhyReport.source == source,
        WhyReport.market == market,
        WhyReport.category == category,
        WhyReport.product_id == product_id,
        WhyReport.window_start == window_start,
    ).first()

    if existing:
        existing.window_end = window_end
        existing.summary = summary
        existing.evidence_json = evidence_json
        logger.info("Updated report for %s", product_id)
    else:
        db.add(
            WhyReport(
                source=source,
                market=market,
                category=category,
                product_id=product_id,
                window_start=window_start,
                window_end=window_end,
                summary=summary,
                evidence_json=evidence_json,
            )
        )
        logger.info("Inserted report for %s", product_id)

    db.commit()
