# T-3: F16 — 설정 해석 (`config.py`)

## 관련 문서
- spec: `docs/sdd/spec/2026-07-29-kompound-snapshot-hook.md` — F16(전문), "현재 환경 기준값" 표(참고용, 리터럴 금지)
- arch: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md` — §6.1(F16 설정 해석 확정), §3.2(모듈 계약 표 — `config` 행)

## 구현자
sdd-python-engineer

## 테스트 타입
단위 (monkeypatch env + tmp_path — arch §9.1 "설정 해석" 행)

## 완료 조건
- [ ] `resolve_config()`가 단일 진실 지점으로 존재하며, 다음 순서로 해석한다: ① 환경변수 → ② 설정 파일(②-a 프로젝트 → ②-b 홈) → ③ 자동 탐색 → ④ 코드 기본값. **키 단위 병합**이다(파일 전체 우선이 아님) — 스칼라 필드는 "가장 높은 우선순위에서 값이 존재하는 소스"를 채택, `prefix_map`은 dict 병합(낮은 우선순위→높은 우선순위 순, 값이 `null`이면 그 키 삭제).
- [ ] 환경변수 키 3종이 정확히 이 이름이다: `HARNESS_KOMPOUND_REPO`, `HARNESS_KOMPOUND_SCAN_ROOT`, `HARNESS_KOMPOUND_CONFIG`(설정 파일 경로 직접 지정 — 지정 시 ②의 탐색을 대체).
- [ ] 설정 파일 위치 2단계: `<project_root>/.claude/kompound-snapshot.config.json`(②-a, `.claude/state/` 밖) → `${CLAUDE_CONFIG_DIR:-~/.claude}/kompound-snapshot.json`(②-b, 주 저장소).
- [ ] 설정 파일 스키마가 arch §6.1의 JSON 스키마와 정확히 일치한다: `schema_version`(=1), `kompound_repo`, `scan_root`, `max_anchor_depth`(기본 5), `state_max_age_hours`(기본 24), `prefix_map`(dict, 값 `null` 허용).
- [ ] `DEFAULT_PREFIX_MAP`이 spec F4의 10종 매핑(`Marvelous`/`Marvelous_dev`/`Marvelous_feature`/`Marvelous_code_review`/`auto-fix-base`→`marvelous`, `CLOFab_Web`→`clofab`, `Marvelous_graphify`→`graphify`, `auto-fix-orchestrator`→`autofix`, `crash-ai-analysis`→`crashai`, `codegraph-clo`→`codegraph`, `ai-code-reviewer-action`→`aireview`, `moon-harness`→`harness`, `rein`→`rein`, `claude-slack-channel`→`slack`)을 코드 상수로 갖고, dict 병합의 최하위 소스로 참여한다. **이 상수 외에는 어떤 사용자 고유 절대경로 리터럴도 코드에 없어야 한다**(F16 정적 검사 대상 — `/Users/<user>/...` 패턴 0건).
- [ ] **③ 자동 탐색**: 후보 = `<project_root>` 부모 디렉토리의 직속 자식(1단계만). 각 후보를 "kompound 서명"(① `.git` 존재 ② `raw/` 존재 ③ `wiki/index.md` 존재 ④ `wiki/log.md` 존재)으로 검증. 서명 통과 후보가 정확히 1개면 채택, 0개/2개 이상이면 미해석. 채택되면 `scan_root` = 그 kompound의 부모 디렉토리(단, `/` 또는 홈 디렉토리 자체면 거부). 탐색 결과는 캐시하지 않는다.
- [ ] `kompound_repo` 미해석과 `scan_root` 미해석의 의미가 다르다: `kompound_repo` 미해석 → 기능 전체 **비활성**(`ok: false`류 신호). `scan_root` 미해석 → workspace 스코프만 불가(T1/T2가 쓰는 repo/worktree 스코프는 정상).
- [ ] 반환 dict에 `source` 맵(`{"kompound_repo": "env|project|home|discovery", "scan_root": "...", ...}`)이 포함된다 — 값의 출처가 항상 추적 가능해야 한다.
- [ ] `config.py`는 **미설정 안내 출력 여부를 판단하지 않는다** — "미설정"이라는 사실만 결과 dict로 반환한다(안내 1회 판정은 T-7 `runtime_state.py`의 단독 책임, M-18).
- [ ] `resolve_config()`가 예외를 던지지 않고 항상 구조화된 dict(`{"ok": bool, ...}`)를 반환한다(F13 fail-safe).
- [ ] 커스텀 `prefix_map`(11번째 repo 추가 등)이 설정으로 주입됐을 때 그 값이 `DEFAULT_PREFIX_MAP`과 병합되어 그대로 사용됨을 검증하는 테스트가 있다.
- [ ] 동일 실행 내에서 `resolve_config()`를 여러 번 호출해도 사용자 고유 정보를 캐시하지 않고 매번 동일한 입력에 동일한 출력을 낸다(순수성 — 안내 억제 상태는 이 모듈이 아니라 `runtime_state`가 소유하므로 여기엔 상태가 없다).

## 의존 태스크
T-2 (패키지 스켈레톤 + `fake_kompound_env` fixture)

**후속 관계**: T-4(scan/naming/dedup), T-8(registry/wiki_log), T-9(verify), T-11(cli) 전부가 `resolve_config()`의 반환 스키마를 계약으로 참조한다.

## 예상 변경 파일
- `hooks/lib/kompound_snapshot/config.py` — 신규
- `tests/test_kompound_snapshot_config.py` — 신규

## Steps
- [ ] `DEFAULT_PREFIX_MAP` 상수 정의(F4 10종)
- [ ] 환경변수 3종 읽기 함수 작성
- [ ] 설정 파일 로더(②-a, ②-b) 작성 — JSON 파싱 실패 시 예외를 던지지 않고 해당 소스를 "값 없음"으로 처리
- [ ] ③ 자동 탐색 알고리즘 구현(kompound 서명 4조건, 후보 0/1/2+개 분기)
- [ ] 키 단위 병합 로직 구현(스칼라: 최고 우선순위 non-null 채택 / `prefix_map`: dict 병합 + `null` 값 삭제)
- [ ] `source` 맵 조립 및 `resolve_config()` 최종 조립(fail-safe try/except 래핑)
- [ ] `tests/test_kompound_snapshot_config.py` 작성: env 우선순위, 파일 키 단위 병합(file-first-wins가 아님을 명시적으로 검증하는 케이스 필수 — J-10), 자동 탐색 0/1/2개 후보, 미해석 시 `kompound_repo`/`scan_root` 의미 분리, 커스텀 prefix_map 병합, `source` 맵 정확성
- [ ] `pytest tests/test_kompound_snapshot_config.py -v` GREEN 확인

## 검증 명령어
```bash
PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/test_kompound_snapshot_config.py -q
```

## 테스트 스코프
`tests/test_kompound_snapshot_config.py` (전체) — `pytest tests/test_kompound_snapshot_config.py -q` 또는 `pytest tests/ -k "kompound and config"`
