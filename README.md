# Laneige INSIGHT MVP

**시장 인사이트 자동화 시스템**  
랭킹 스냅샷 → 변동 감지 → Why Report 생성 → ROI 시뮬레이션까지 자동화하는 마켓 인텔리전스 도구

> 제출/데모는 `DEMO_MODE=1`(샘플 스냅샷 기반)로 안전하게 시연하고,  
> 실서비스 전환 시에는 Keepa 등 **API 기반 수집**으로 교체하는 것을 전제로 설계했습니다.

---

## 시스템 구조도
```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   Laneige INSIGHT MVP (1-page)                               │
│                     Ranking Snapshot → Change Detection → Why Report → ROI (Demo Mode)       │
└──────────────────────────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────┐
│           Data Sources         │
│        (src/sources/)          │
│  - amazon_product  (ASIN)      │
│  - amazon_bestsellers (Top N)  │
│  - amazon_search (keyword)     │
└───────────────┬───────────────┘
                │  fetch(): ProductItem[]
                v
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                           Collector / Snapshot Ingestion (scripts/collect.py)                │
│  - optional keyword filter                                                                     │
│  - image download → pHash(64-bit)                                                              │
│  - ProductItem → ProductSnapshot                                                               │
│  - transaction commit (item-level skip on error)                                               │
│  - DEMO_MODE: live fetch disabled (use stored/sample snapshots)                                │
└───────────────────────────────┬──────────────────────────────────────────────────────────────┘
                                │ INSERT
                                v
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                         Database                                              │
│  ProductSnapshot                                                                              │
│   - source, market, category, product_id, captured_at, rank, price, rating, reviews, image_*  │
│   - INDEX (source, market, category, product_id, captured_at DESC)  → fast "latest 2" query   │
│                                                                                               │
│  WhyReport                                                                                    │
│   - window_start, window_end, summary_text, evidence_json                                     │
│   - UNIQUE (source, market, category, product_id, window_start, window_end)                   │
└───────────────────────────────┬──────────────────────────────────────────────────────────────┘
                                │ SELECT latest 2 snapshots / product
                                v
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                           Detector / Driver Scoring (scripts/analyze.py)                      │
│  get_recent_pair()                                                                              │
│   - per product: only latest 2 snapshots (max_gap_hours 적용)                                  │
│  score_drivers()                                                                               │
│   - Δrank, Δprice, Δreviews, Δrating, Δimage(pHash XOR-Hamming, threshold)                     │
│  outputs → evidence for Why Report + ROI                                                       │
└───────────────────────────────┬──────────────────────────────────────────────────────────────┘
                                │ build report (with evidence)
                                v
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                  Why Report Generator (src/pipeline/why.py)                   │
│  Priority: Groq → Claude → Rule-based fallback                                                  │
│  - external API failure-safe (pipeline never blocks)                                             │
│  - upsert_report(): insert/update per time window                                                │
└───────────────────────────────┬──────────────────────────────────────────────────────────────┘
                                │ SELECT snapshots + reports
                                v
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   Dashboard / ROI (Streamlit: app.py)                          │
│  Left: Snapshot table + product detail (latest vs previous)                                     │
│  Right: Why Report list + detail                                                                 │
│  ROI Simulator: Δrank → expected_loss / intervention_cost / expected_gain / ROI% (baseline)     │
│  Demo Event: synthetic Δrank input → immediate end-to-end test                                  │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 문제 정의

글로벌 커머스(Amazon, @COSME 등) 환경에서는 랭킹, 가격, 리뷰 등 핵심 지표가 실시간으로 급변합니다. 
변동이 발생한 구체적인 원인(Why)을 규명하고, 이에 따른 최적의 대응 전략과 예상 수익(Action/ROI)을 제시하는 '행동 가능한 인사이트(Actionable Insight)'를 신속하게 확보하는 것이 매우 중요합니다.

### 본 MVP의 자동화 범위
- 스냅샷 저장 (정형화된 제품 지표)
- 변동 감지 (순위/가격/리뷰/평점/이미지 등)
- Why Report (원인 추정 + 근거 요약: LLM 또는 룰 기반 fallback)
- ROI 시뮬레이션 (액션별 기대효과/우선순위)

---

## 핵심 기능

| 모듈 | 설명 |
|------|------|
| **Snapshot Collector** | 제품 상태를 주기적/수동으로 수집하여 DB 저장 |
| **Change Detector** | 최신 vs 이전 스냅샷 비교, 변화 이벤트 생성 |
| **Why Report** | 변화 요인을 텍스트로 요약 (LLM + 룰 기반 fallback) |
| **Dashboard** | Streamlit 기반 실시간 모니터링 UI |

---

## 프로젝트 구조
```
laneige-insight-mvp/
├── src/
│   ├── sources/           # 수집 소스 모듈
│   │   ├── amazon_product.py
│   │   └── amazon_keepa.py
│   ├── db.py              # SQLAlchemy 세션
│   └── models.py          # DB 모델
├── scripts/
│   ├── init_db.py         # DB 테이블 생성
│   ├── collect.py         # 수집 실행
│   └── analyze.py         # 변동 감지 + Why Report
├── app.py                 # Streamlit 대시보드
├── requirements.txt
├── .env                   # 환경변수
└── README.md
```

---

## 빠른 시작 (데모 모드)

### 1) 환경 설정
```bash
cd laneige-insight-mvp
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) 환경변수 설정
```bash
cat > .env << 'EOF'
DATABASE_URL=sqlite:///./app.db
DEMO_MODE=1
EOF
```

### 3) DB 초기화
```bash
python -m scripts.init_db
```

### 4) 데모 실행 (샘플 데이터 기반)

**방법 A: 자동 스크립트**
```bash
bash run_demo.sh
```

**방법 B: 수동 실행**
```bash
PYTHONPATH=. python scripts/analyze.py
streamlit run app.py --server.port 8502
```

브라우저에서 `http://localhost:8502` 접속

---

## 실시간 수집 (선택)

> **주의**: 외부 커머스 직접 크롤링은 캡차/약관 위반 가능성이 있습니다.  
> 실운영 전환 시 API 계약/정책 준수 전제 하에 collector만 교체하는 것을 권장합니다.

### Keepa API 사용 (선택)
```bash
cat >> .env << 'EOF'
KEEPA_API_KEY=YOUR_KEY
DEMO_MODE=0
EOF

set -a; source .env; set +a
PYTHONPATH=. python scripts/collect.py --source amazon_keepa
PYTHONPATH=. python scripts/analyze.py
streamlit run app.py --server.port 8502
```

### LLM 기반 Why Report (선택)
```bash
pip install groq

cat >> .env << 'EOF'
GROQ_API_KEY=YOUR_KEY
EOF

set -a; source .env; set +a
PYTHONPATH=. python scripts/analyze.py
```

> LLM 키가 없으면 룰 기반 fallback으로 동작합니다.

---

## 트러블슈팅

### `zsh: unknown file attribute: h`
**원인**: 터미널에 마크다운 링크 형태로 입력  
**해결**:
```bash
# 잘못된 예
streamlit run [app.py](http://app.py/)

# 올바른 예
streamlit run app.py
```

### Streamlit 포트가 8501/8502로 다름
사용 중인 포트 자동 회피가 정상 동작입니다. 포트를 고정하려면:
```bash
streamlit run app.py --server.port 8502
```

### `RuntimeError: DATABASE_URL empty`
`.env`에 `DATABASE_URL`이 있는지 확인:
```bash
cat > .env << 'EOF'
DATABASE_URL=sqlite:///./app.db
EOF
```

### `sqlite3.OperationalError: no such table: product_snapshots`
DB 초기화를 다시 실행:
```bash
python -m scripts.init_db
```

### `Playwright Executable doesn't exist`
(실시간 수집 사용 시)
```bash
python -m playwright install chromium
```

### `Saved 0 snapshots`
**원인**: DEMO_MODE/API키/정책 제한/차단  
**권장**: 제출(데모 버전)은 `DEMO_MODE=1`로 고정하고 샘플 데이터 기반 시연