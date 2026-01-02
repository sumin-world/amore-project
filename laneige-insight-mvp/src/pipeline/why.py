"""
Why 리포트 생성 모듈
- Groq (무료) 우선
- Claude (유료) 대안
- 룰 기반 폴백
"""

import os
import json
from datetime import datetime
from src.models import ProductSnapshot, WhyReport
from sqlalchemy.orm import Session


def compute_image_diff_score(prev: ProductSnapshot, curr: ProductSnapshot) -> dict:
    """썸네일 이미지 변경 감지 (pHash 기반)"""
    if not prev.image_phash or not curr.image_phash:
        return {"changed": False, "score": 0, "distance": 0}
    
    try:
        prev_hash = int(prev.image_phash, 16)
        curr_hash = int(curr.image_phash, 16)
        distance = bin(prev_hash ^ curr_hash).count('1')
        changed = distance > 10
        score = min(distance / 64.0 * 100, 100)
        
        return {"changed": changed, "score": round(score, 1), "distance": distance}
    except Exception as e:
        print(f"이미지 diff 계산 실패: {e}")
        return {"changed": False, "score": 0, "distance": 0}


def build_prompt(prev: ProductSnapshot, curr: ProductSnapshot, evidence: dict) -> str:
    """공통 프롬프트 생성"""
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
    """Groq API로 Why 리포트 생성 (무료!)"""
    try:
        from groq import Groq
        
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            raise ValueError("GROQ_API_KEY 없음")
        
        client = Groq(api_key=api_key)
        
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": build_prompt(prev, curr, evidence)}],
            temperature=0.3,
            max_tokens=300,
        )
        
        summary = completion.choices[0].message.content.strip()
        print(f"✅ Groq LLM 리포트 생성 ({len(summary)}자)")
        return summary
        
    except Exception as e:
        print(f"❌ Groq 호출 실패: {e}")
        return None


def build_why_report_with_claude(prev: ProductSnapshot, curr: ProductSnapshot, evidence: dict) -> str:
    """Claude API로 Why 리포트 생성"""
    try:
        from anthropic import Anthropic
        
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY 없음")
        
        client = Anthropic(api_key=api_key)
        
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            temperature=0.3,
            messages=[{"role": "user", "content": build_prompt(prev, curr, evidence)}]
        )
        
        summary = message.content[0].text.strip()
        print(f"✅ Claude LLM 리포트 생성 ({len(summary)}자)")
        return summary
        
    except Exception as e:
        print(f"❌ Claude 호출 실패: {e}")
        return None


def build_why_report_fallback(prev: ProductSnapshot, curr: ProductSnapshot, evidence: dict) -> str:
    """룰 기반 폴백"""
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
    
    if abs(delta_p) > 1.5:
        if delta_p < 0:
            causes.append(f"가격 인하 ${abs(delta_p):.2f}")
        else:
            causes.append(f"가격 인상 ${delta_p:.2f}")
    
    if delta_rev > 100:
        causes.append(f"리뷰 급증 +{delta_rev}건")
    elif delta_rev > 30:
        causes.append(f"리뷰 증가 +{delta_rev}건")
    
    if abs(delta_rating) >= 0.2:
        causes.append(f"평점 {'상승' if delta_rating > 0 else '하락'} {abs(delta_rating):.1f}")
    
    img_diff = evidence.get("image_diff", {})
    if img_diff.get("changed"):
        causes.append(f"썸네일 변경")
    
    if causes:
        summary = " | ".join(parts) + " - 원인: " + " + ".join(causes)
    else:
        summary = " | ".join(parts) + " - 특이사항 없음"
    
    if delta_r > 3:
        summary += " → 긴급 대응 필요"
    elif delta_r > 0:
        summary += " → 모니터링 강화"
    
    return summary


def build_why_report(prev: ProductSnapshot, curr: ProductSnapshot, evidence: dict) -> str:
    """
    메인 함수: Why 리포트 생성
    우선순위: Groq (무료) → Claude (유료) → Rule-based
    """
    
    # 1순위: Groq (무료)
    use_groq = os.getenv("USE_GROQ", "true").lower() == "true"
    if use_groq:
        result = build_why_report_with_groq(prev, curr, evidence)
        if result:
            return result
    
    # 2순위: Claude (유료)
    use_claude = os.getenv("USE_CLAUDE", "false").lower() == "true"
    if use_claude:
        result = build_why_report_with_claude(prev, curr, evidence)
        if result:
            return result
    
    # 3순위: Rule-based
    print("ℹ️  룰 기반 폴백 사용")
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
    """WhyReport 테이블에 저장"""
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
        print(f"  ↻ 리포트 업데이트: {product_id}")
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
        print(f"  + 리포트 생성: {product_id}")
    
    db.commit()
