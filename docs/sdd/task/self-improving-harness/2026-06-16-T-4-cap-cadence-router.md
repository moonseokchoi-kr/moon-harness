# T-4: 상한/케이던스/서킷브레이커 엔진 + on-demand 메모리 라우터 + 학습사다리 라우터

## 관련 문서
- spec: `docs/sdd/spec/2026-06-16-self-improving-harness.md` — F4 (케이던스), F6 (서킷브레이커), F13 (5건 상한), F17 (학습사다리 L0~L4), F18 (on-demand 로드, 토큰 예산), F20 (결정적 로직)
- arch: `docs/sdd/design/arch/2026-06-16-self-improving-harness.md` — §3.1 (cap+cadence+circuit-breaker engine, on-demand memory router, ladder router), §5 (cadence mapping), §7 (on-demand memory, learning ladder)

## Wave
**Wave 1** (Phase 1 foundation)

## 구현자
sdd-python-engineer

## 테스트 타입

| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| cap + 서킷브레이커 엔진 | 단위 (pytest) | 임계값 경계, 상한 초과 시 트런케이션 |
| 케이던스 계산 | 단위 (pytest) | 300s 사용 안 함 검증 포함 |
| on-demand 메모리 라우터 | 단위 (pytest, golden fixture) | 토큰 예산 컴플라이언스 |
| 학습사다리 라우터 | 단위 (pytest) | L0→L4 매핑, 하네스 티어 L3+ 경계 |

## 완료 조건
- [ ] `check_circuit_breaker(state: dict) -> dict`: `fix_attempts[signal] >= 3` 또는 `iterations > 15` → `{"blocked": True, "reason": "..."}` 반환 (F6)
- [ ] `compute_cadence(status: str) -> int | None`: WORKING/WAITING → 270, NEEDS_HUMAN → 1200, CONVERGED/BLOCKED → None. 300 반환 절대 없음 (F4)
- [ ] `apply_cap(candidates: list, cap: int = 5) -> tuple[list, list]`: 상위 `cap`개 반환 + 초과분 별도 반환. 초과 시 `truncated=True` 플래그 포함 dict 반환 (F13)
- [ ] 6건 후보 → apply_cap 후 적용 5건 + 초과 1건이 반환 구조에 명시 (F13 Acceptance)
- [ ] `route_memory(entries: list[dict], context_domain: str, always_on_budget: int = 800, ondemand_budget: int = 500) -> dict`: domain 태그 필터링 → 토큰 예산 내 엔트리 선택 반환 (F18)
- [ ] `route_memory` 결과에 always-on/on-demand 레이어 구분 포함
- [ ] 토큰 예산 초과 시 엔트리를 잘라내고 잘린 사실을 반환 dict에 기록
- [ ] `get_next_ladder_rung(current_rung: str, recurrence_count: int) -> dict`: L0→L4 순서 매핑, 재발 시 현재 단계+1 제안 (F17). L3+ 는 `requires_human=True` 플래그 포함
- [ ] 런타임 코드에서 stdlib 외 import 없음
- [ ] `pytest tests/test_cap_cadence.py tests/test_memory_router.py tests/test_ladder.py` 네트워크 없이 통과

## 의존 태스크
- T-1 (state dict 구조 참조)
- T-2 (태그 파싱 함수 import)

## 예상 변경 파일
- `hooks/lib/self_improve/circuit_breaker.py` — check_circuit_breaker, compute_cadence
- `hooks/lib/self_improve/cap.py` — apply_cap (5건 상한, 트런케이션 보고)
- `hooks/lib/self_improve/memory_router.py` — route_memory (태그 필터 + 토큰 예산)
- `hooks/lib/self_improve/ladder.py` — LADDER_RUNGS 상수, get_next_ladder_rung
- `hooks/lib/self_improve/__init__.py` — 공개 API 추가
- `tests/test_cap_cadence.py`
- `tests/test_memory_router.py`
- `tests/test_ladder.py`

## Steps
- [ ] `circuit_breaker.py` 구현: `check_circuit_breaker`(fix_attempts 개별 신호 + iterations 전체), `compute_cadence`(status → interval, 300 미포함 명시적 어서션)
- [ ] `cap.py` 구현: `apply_cap` — 후보 리스트 슬라이싱, 초과분 반환, truncated 플래그
- [ ] `memory_router.py` 구현: entries에서 `domain` 태그 필터링 → 토큰 길이 추정(len(text)//4) → 예산 내 우선순위 선택
- [ ] `ladder.py` 구현: `LADDER_RUNGS = ["L0", "L1", "L2", "L3", "L4"]` + `get_next_ladder_rung` (재발 횟수 기반 에스컬레이션, L3+ requires_human=True)
- [ ] 단위 테스트 작성 (경계: fix_attempts=3 → BLOCKED, iterations=16 → BLOCKED, compute_cadence 300 미반환 어서션, apply_cap 초과 트런케이션, route_memory 예산 초과 시 잘림)
- [ ] `pytest tests/test_cap_cadence.py tests/test_memory_router.py tests/test_ladder.py -v` 통과 확인

## 검증 명령어
```bash
cd /Users/moon/workspace/moon-harness/worktrees/self-improving-harness
pytest tests/test_cap_cadence.py tests/test_memory_router.py tests/test_ladder.py -v
```
