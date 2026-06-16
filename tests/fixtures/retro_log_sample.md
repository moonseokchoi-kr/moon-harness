# .harness/retro-log.md

<!-- append-only — 절대 수동 편집 금지 -->

## 2026-06-01 retro — 신규 4건 처리 / 적용 2 · 제안 1 · 폐기 1

### 적용 (프로젝트 티어, 자동)
- **docs/lessons-learned.md** ← state 파일 원자적 쓰기 실패 대비 rollback 추가
  - critic: UPHELD
  - 근거: ## 2026-05-30 — atomic-write / T-1
  - rollback:
    ```diff
    + always use atomic_write() — never json.dump directly to the target path
    ```

- **docs/pitfalls.md** ← 커서 없이 전체 LEARNING.md 재처리 방지
  - critic: NARROW
  - 근거: ## 2026-05-28 — cursor-engine / T-3
  - rollback:
    ```diff
    + cursor must be updated before re-reading LEARNING.md to avoid double-processing
    ```

### 제안 (하네스 티어, 승인 대기)
- `harness-proposals/2026-06-01-circuit-breaker.md` — 서킷브레이커 임계값 튜닝

### 폐기
- 타입 힌트 누락 경고 — 1회성: 단일 파일 수정으로 해소됨

---

## 2026-06-08 retro — 신규 5건 처리 / 적용 3 · 제안 1 · 폐기 1

### 적용 (프로젝트 티어, 자동)
- **docs/lessons-learned.md** ← PR 리뷰 코멘트 중복 처리 방지 키 추가
  - critic: UPHELD
  - 근거: ## 2026-06-05 — pr-dedup / T-7
  - rollback:
    ```diff
    + deduplicate review comments by (file, line, body) composite key
    ```

- **docs/pitfalls.md** ← atomic_write 사용 확인 (재발 교훈)
  - critic: UPHELD
  - 근거: ## 2026-05-30 — atomic-write / T-1
  - rollback:
    ```diff
    + confirmed: all state writes now go through atomic_write — no direct json.dump
    ```

- **docs/lessons-learned.md** ← 스킬 재사용 추적 필드 추가
  - critic: UPHELD
  - 근거: ## 2026-06-07 — skill-reuse / T-9
  - rollback:
    ```diff
    + add skill_calls field to pr-converge-state for reuse tracking
    ```

### 제안 (하네스 티어, 승인 대기)
- `harness-proposals/2026-06-08-memory-router.md` — 온디맨드 메모리 라우터 조정

### 폐기
- 로그 레벨 변경 — 중복: docs/pitfalls.md에 이미 기록됨

---

## 2026-06-15 retro — 신규 6건 처리 / 적용 3 · 제안 2 · 폐기 1

### 적용 (프로젝트 티어, 자동)
- **docs/lessons-learned.md** ← 재발 교훈: atomic_write 3번째 등장
  - critic: UPHELD
  - 근거: ## 2026-05-30 — atomic-write / T-1
  - rollback:
    ```diff
    + atomic_write recurrence confirmed across 3 retros — promoting to pitfalls
    ```

- **docs/pitfalls.md** ← pr-converge 서킷브레이커 임계값 문서화
  - critic: NARROW
  - 근거: ## 2026-06-12 — circuit-breaker-tuning / T-4
  - rollback:
    ```diff
    + document FIX_ATTEMPTS_THRESHOLD=3 and ITERATIONS_THRESHOLD=10 in pitfalls
    ```

- **docs/lessons-learned.md** ← 메트릭 cold_start 표기 방법
  - critic: UPHELD
  - 근거: ## 2026-06-14 — metrics-coldstart / T-11
  - rollback:
    ```diff
    + always set cold_start=true when data points < 5 to avoid false precision
    ```

### 제안 (하네스 티어, 승인 대기)
- `harness-proposals/2026-06-15-recurrence-anchor.md` — 재발률 앵커 자동화
- `harness-proposals/2026-06-15-skill-success-rate.md` — 스킬 성공률 집계 파이프라인

### 폐기
- indent 스타일 변경 — REFUTED: 벤치마크 점수 변화 없음
