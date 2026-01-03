"""
Why Report Generation Module

This module generates natural language explanations for ranking changes
using AI (LLM) or rule-based fallback logic. It implements a hierarchical
approach prioritizing free APIs over paid ones, with guaranteed fallback.

LLM Provider Hierarchy:
    1. Groq (Primary): Free tier, llama-3.3-70b model, fast inference
    2. Claude (Secondary): Paid tier, high quality, used when Groq unavailable
    3. Rule-based (Fallback): Deterministic logic, always available

Fault-Tolerance Strategy:
    - Each LLM call wrapped in try-except with specific error handling
    - API key validation before attempting calls
    - Graceful degradation: Groq failure → Claude → Rules
    - Clear separation of LLM calls ensures one failure doesn't affect others
    - Rule-based fallback guarantees report generation even without API access

Error Handling Philosophy:
    - Non-blocking: LLM failures don't crash the pipeline
    - Informative: Log messages indicate which method succeeded/failed
    - Resilient: Always return a valid report (via fallback)

TODO - Future Enhancements:
    - Add report quality scoring to compare LLM vs rule-based outputs
    - Implement caching for similar ranking patterns
    - Add multi-language support (Japanese, Korean)
    - Implement scheduling for periodic analysis runs
    - Add alerting system for critical ranking drops (e.g., >5 positions)
    - Add CSV/Excel export functionality for reports
    - Implement internationalization (i18n) framework
"""

import os
import json
from datetime import datetime
from src.models import ProductSnapshot, WhyReport
from sqlalchemy.orm import Session


def compute_image_diff_score(prev: ProductSnapshot, curr: ProductSnapshot) -> dict:
    """
    Detect product thumbnail changes using perceptual hashing (pHash).
    
    Args:
        prev: Previous product snapshot
        curr: Current product snapshot
    
    Returns:
        Dictionary with change detection results:
            - changed: Boolean indicating if image changed significantly
            - score: Change score (0-100, higher = more different)
            - distance: Hamming distance between pHash values (bit count)
    
    Algorithm:
        1. Convert hex pHash strings to integers
        2. XOR the integers to find differing bits
        3. Count set bits (Hamming distance)
        4. Threshold: >10 bits = changed (see detector.py for rationale)
        5. Score: (distance / 64) * 100 = percentage difference
    
    Notes:
        - Returns {"changed": False, "score": 0, "distance": 0} if pHash missing
        - 64-bit pHash allows fine-grained similarity detection
        - Threshold of 10 bits balances sensitivity vs noise
        - Useful for detecting A/B testing, product updates, packaging changes
    """
    if not prev.image_phash or not curr.image_phash:
        return {"changed": False, "score": 0, "distance": 0}
    
    try:
        prev_hash = int(prev.image_phash, 16)
        curr_hash = int(curr.image_phash, 16)
        distance = bin(prev_hash ^ curr_hash).count('1')
        changed = distance > 10  # Threshold: >10 bits indicates meaningful change
        score = min(distance / 64.0 * 100, 100)
        
        return {"changed": changed, "score": round(score, 1), "distance": distance}
    except Exception as e:
        print(f"Image diff calculation failed: {e}")
        return {"changed": False, "score": 0, "distance": 0}


def build_prompt(prev: ProductSnapshot, curr: ProductSnapshot, evidence: dict) -> str:
    """
    Generate common prompt for LLM analysis.
    
    Creates a structured prompt containing all relevant ranking change data
    for LLM processing. Used by both Groq and Claude implementations.
    
    Args:
        prev: Previous snapshot
        curr: Current snapshot  
        evidence: Scored ranking drivers from score_drivers()
    
    Returns:
        Formatted prompt string in Korean
    
    Prompt Structure:
        - Product identification (title, ASIN)
        - Time window
        - Change metrics (rank, price, reviews, rating, image)
        - Analysis request with specific output format
    """
    delta_rank = curr.rank - prev.rank
    delta_price = curr.price - prev.price
    delta_review = curr.review_count - prev.review_count
    delta_rating = curr.rating - prev.rating
    
    img_diff = evidence.get("image_diff", {})
    img_changed = img_diff.get("changed", False)
    
    return f"""Amazon 제품 랭킹 변동 분석:

제품: {curr.title}
ASIN: {curr.product_id}
기간: {prev.captured_at.strftime('%m/%d %H:%M')} → {curr.captured_at.strftime('%m/%d %H:%M')}

변화:
- 랭킹: #{prev.rank} → #{curr.rank} (Δ {delta_rank:+d})
- 가격: ${prev.price:.2f} → ${curr.price:.2f} (Δ ${delta_price:+.2f})
- 리뷰: {prev.review_count:,} → {curr.review_count:,} (Δ {delta_review:+,d})
- 평점: {prev.rating:.1f} → {curr.rating:.1f} (Δ {delta_rating:+.1f})
- 썸네일: {"변경" if img_changed else "유지"}

요청:
1. 랭킹 변동 주요 원인 2가지
2. 영향도 (HIGH/MID/LOW)
3. 긴급 대응 필요 여부
4. 액션 아이템 1-2개

150자 이내 한국어로 간결하게.
예: "랭킹 3→9 (+6) | 원인: 가격 인하 $5 (HIGH) + 리뷰 증가 +50 (MID) | 대응: 경쟁사 가격 모니터링 강화"
"""


def build_why_report_with_groq(prev: ProductSnapshot, curr: ProductSnapshot, evidence: dict) -> str:
    """
    Generate Why Report using Groq API (free tier, recommended).
    
    Args:
        prev: Previous snapshot
        curr: Current snapshot
        evidence: Ranking driver scores
    
    Returns:
        LLM-generated summary string, or None if generation fails
    
    Error Handling:
        - Validates API key before calling
        - Catches all exceptions (network, API errors, rate limits)
        - Returns None on failure (triggers fallback to Claude or rules)
        - Logs failure reason for debugging
    
    Configuration:
        - Model: llama-3.3-70b-versatile (fast, high quality)
        - Temperature: 0.3 (balanced creativity vs consistency)
        - Max tokens: 300 (sufficient for concise summaries)
    
    Notes:
        - Free tier has generous rate limits
        - Fast inference (~1-2 seconds)
        - Requires GROQ_API_KEY environment variable
        - Can be disabled via USE_GROQ=false
    """
    try:
        from groq import Groq
        
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            raise ValueError("GROQ_API_KEY not configured")
        
        client = Groq(api_key=api_key)
        
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": build_prompt(prev, curr, evidence)}],
            temperature=0.3,
            max_tokens=300,
        )
        
        summary = completion.choices[0].message.content.strip()
        print(f"[SUCCESS] Groq LLM report generated ({len(summary)} chars)")
        return summary
        
    except Exception as e:
        print(f"[FAILED] Groq API call failed: {e}")
        return None


def build_why_report_with_claude(prev: ProductSnapshot, curr: ProductSnapshot, evidence: dict) -> str:
    """
    Generate Why Report using Claude API (paid tier, high quality).
    
    Args:
        prev: Previous snapshot
        curr: Current snapshot
        evidence: Ranking driver scores
    
    Returns:
        LLM-generated summary string, or None if generation fails
    
    Error Handling:
        - Validates API key before calling
        - Catches all exceptions independently from Groq
        - Returns None on failure (triggers rule-based fallback)
        - Logs failure reason for debugging
    
    Configuration:
        - Model: claude-sonnet-4-20250514 (latest, high quality)
        - Temperature: 0.3 (balanced creativity vs consistency)
        - Max tokens: 400 (allows for detailed analysis)
    
    Notes:
        - Paid API with usage-based billing
        - Higher quality than Groq but slower
        - Requires ANTHROPIC_API_KEY environment variable
        - Disabled by default (USE_CLAUDE=false)
    """
    try:
        from anthropic import Anthropic
        
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")
        
        client = Anthropic(api_key=api_key)
        
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            temperature=0.3,
            messages=[{"role": "user", "content": build_prompt(prev, curr, evidence)}]
        )
        
        summary = message.content[0].text.strip()
        print(f"[SUCCESS] Claude LLM report generated ({len(summary)} chars)")
        return summary
        
    except Exception as e:
        print(f"[FAILED] Claude API call failed: {e}")
        return None


def build_why_report_fallback(prev: ProductSnapshot, curr: ProductSnapshot, evidence: dict) -> str:
    """
    Generate Why Report using rule-based logic (guaranteed fallback).
    
    This method always succeeds and provides basic ranking change analysis
    when LLM APIs are unavailable or fail. Uses deterministic rules to
    construct explanations based on evidence thresholds.
    
    Args:
        prev: Previous snapshot
        curr: Current snapshot
        evidence: Ranking driver scores
    
    Returns:
        Rule-based summary string (always succeeds, never returns None)
    
    Logic Rules:
        - Rank change detection with direction (up/down/stable)
        - Price change threshold: >$1.50 considered significant
        - Review growth thresholds: >100 "surge", >30 "increase"
        - Rating change threshold: >=0.2 stars considered significant
        - Image change detection via evidence dict
        - Urgency assessment: >3 ranks = urgent, >0 = monitor
    
    Output Format:
        "Ranking change: X→Y (Δ ±Z) - Causes: [cause1] + [cause2] → [Action]"
    
    Example:
        "랭킹 변동: 5→8 (Δ +3) - 원인: 가격 인하 $3.50 + 리뷰 증가 +45건 → 모니터링 강화"
    """
    delta_r = curr.rank - prev.rank
    delta_p = curr.price - prev.price
    delta_rev = curr.review_count - prev.review_count
    delta_rating = curr.rating - prev.rating
    
    parts = []
    
    if delta_r > 0:
        parts.append(f"랭킹 변동: {prev.rank}→{curr.rank} (Δ +{delta_r})")
    elif delta_r < 0:
        parts.append(f"랭킹 변동: {prev.rank}→{curr.rank} (Δ {delta_r})")
    else:
        parts.append(f"랭킹 유지: {curr.rank}")
    
    causes = []
    
    # Price change analysis
    if abs(delta_p) > 1.5:
        if delta_p < 0:
            causes.append(f"가격 인하 ${abs(delta_p):.2f}")
        else:
            causes.append(f"가격 인상 ${delta_p:.2f}")
    
    # Review growth analysis
    if delta_rev > 100:
        causes.append(f"리뷰 급증 +{delta_rev}건")
    elif delta_rev > 30:
        causes.append(f"리뷰 증가 +{delta_rev}건")
    
    # Rating change analysis
    if abs(delta_rating) >= 0.2:
        causes.append(f"평점 {'상승' if delta_rating > 0 else '하락'} {abs(delta_rating):.1f}")
    
    # Image change detection
    img_diff = evidence.get("image_diff", {})
    if img_diff.get("changed"):
        causes.append(f"썸네일 변경")
    
    # Construct summary
    if causes:
        summary = " | ".join(parts) + " - 원인: " + " + ".join(causes)
    else:
        summary = " | ".join(parts) + " - 특이사항 없음"
    
    # Add urgency assessment
    if delta_r > 3:
        summary += " → 긴급 대응 필요"
    elif delta_r > 0:
        summary += " → 모니터링 강화"
    
    return summary


def build_why_report(prev: ProductSnapshot, curr: ProductSnapshot, evidence: dict) -> str:
    """
    Main function: Generate Why Report with hierarchical fallback.
    
    Implements fault-tolerant report generation with clear separation
    of LLM calls to ensure one failure doesn't affect others.
    
    Args:
        prev: Previous snapshot
        curr: Current snapshot
        evidence: Ranking driver scores
    
    Returns:
        Summary string (guaranteed to return valid report via fallback)
    
    Execution Flow:
        1. Check USE_GROQ flag, attempt Groq if enabled
           - On success: return immediately
           - On failure: log error, continue to next option
        2. Check USE_CLAUDE flag, attempt Claude if enabled
           - On success: return immediately
           - On failure: log error, continue to fallback
        3. Execute rule-based fallback (always succeeds)
        4. Return fallback result
    
    Configuration (Environment Variables):
        - USE_GROQ: Enable Groq (default: "true")
        - USE_CLAUDE: Enable Claude (default: "false")
        - GROQ_API_KEY: Groq API credentials
        - ANTHROPIC_API_KEY: Claude API credentials
    
    Error Resilience:
        - Each LLM call isolated in separate function
        - Exceptions caught at function level, not propagated
        - Clear logging indicates which method succeeded
        - Fallback always available regardless of API status
    
    TODO:
        - Add report quality metrics to compare LLM vs rules
        - Implement caching for repeated patterns
        - Add A/B testing framework for prompt optimization
    """
    
    # Priority 1: Groq (free tier, recommended)
    use_groq = os.getenv("USE_GROQ", "true").lower() == "true"
    if use_groq:
        result = build_why_report_with_groq(prev, curr, evidence)
        if result:
            return result
    
    # Priority 2: Claude (paid tier, high quality)
    use_claude = os.getenv("USE_CLAUDE", "false").lower() == "true"
    if use_claude:
        result = build_why_report_with_claude(prev, curr, evidence)
        if result:
            return result
    
    # Priority 3: Rule-based fallback (always available)
    print("[INFO] Using rule-based fallback")
    return build_why_report_fallback(prev, curr, evidence)


def upsert_report(
    db: Session,
    source: str,
    market: str,
    category: str,
    product_id: str,
    window_start: datetime,
    window_end: datetime,
    summary: str,
    evidence_json: str
):
    """
    Save or update Why Report in database.
    
    Implements upsert logic (update if exists, insert if new) to avoid
    duplicate reports for the same time window.
    
    Args:
        db: Database session
        source: Data source identifier
        market: Market identifier
        category: Product category
        product_id: Product identifier
        window_start: Analysis window start time
        window_end: Analysis window end time
        summary: Generated report text
        evidence_json: JSON string of evidence scores
    
    Returns:
        None. Commits changes to database.
    
    Notes:
        - Uses window_start as unique key for upsert
        - Updates window_end, summary, evidence if report exists
        - Creates new report if no existing match
        - Logs operation type for debugging
        - Commits immediately after upsert
    """
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
        print(f"  [UPDATE] Report updated: {product_id}")
    else:
        new_report = WhyReport(
            source=source,
            market=market,
            category=category,
            product_id=product_id,
            window_start=window_start,
            window_end=window_end,
            summary=summary,
            evidence_json=evidence_json,
        )
        db.add(new_report)
        print(f"  [INSERT] Report created: {product_id}")
    
    db.commit()
