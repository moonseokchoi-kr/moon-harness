# T-8: F7/F10 — registry/index/log 카탈로그 갱신 (`registry.py` / `wiki_log.py`)

## 관련 문서
- spec: `docs/sdd/spec/2026-07-29-kompound-snapshot-hook.md` — F7(registry/index/log 갱신 범위), F10(동시 편집 충돌 양쪽 보존)
- arch: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md` — §6.3(F6/F7/F10 쓰기 형태 규율), §6.3.2(registry 표 탐색 3단·행/열 삽입 확정 — 사용자 승인), §6.3.3(카운트 문장 갱신 범위, 화이트리스트), §6.3.0(2단 커밋 경계 — 이 모듈은 (ii) 텍스트 변환만 책임지고 커밋은 T-10/T-5가 담당)

## 구현자
sdd-python-engineer

## 테스트 타입
통합 (골든 텍스트 in/out — arch §9.1 "카탈로그 갱신" 두 행)

## 완료 조건

### `registry.py` (F7)
- [ ] **표 탐색 3단**: ① 섹션 헤딩(`### …`)이 프로젝트명을 포함하는 표 → 그 표에 행 추가. ② 없으면 `프로젝트` 열을 가진 표에서 그 값이 **이미 존재하는** 행이 있으면 그 표에 행 추가(같은 프로젝트 행 그룹 바로 뒤). ③ ①②가 모두 실패할 때만 새 `### <프로젝트>` 섹션 + **7열 형상 (a)**(`feature|spec|arch|기타|result|기존 위키|home repo`) 표를 `## 결정과 근거` 바로 앞에 신설.
- [ ] **헤딩 매칭 규칙**: `prefix_map`의 키(repo 디렉토리명)와 값(프리픽스) 양쪽을 후보로 쓰고, 대소문자 무시 부분 일치. 모호 판정 기준은 **매칭된 섹션 개수**(후보 개수 아님) — 매칭 섹션이 2개 이상일 때만 모호로 실패 보고. 충돌 시 가장 긴 매칭 문자열을 가진 섹션 우선, 동률이면 실패 보고.
- [ ] 행 삽입 위치: 대상 표의 마지막 행 뒤(①·③) 또는 동일 프로젝트 행 그룹의 마지막 뒤(②). 기존 행 순서는 재정렬하지 않는다.
- [ ] `기존 위키` 열은 항상 `—`. `home repo` 열은 `repo_dir`(+ 워크트리 사본 있으면 ` + \`worktrees/<wt>\``).
- [ ] **없는 kind 열은 추가한다**(사용자 승인, 방향 반전) — 기존 행의 그 칸을 `—`로 채운다. **안전 조건 둘 다 만족할 때만**: (a) 추가할 kind가 6종(`spec`/`arch`/`ui`/`api`/`context`/`result`) 이내 (b) 대상 표 헤더 구조가 인지된 3형상 (a)/(b)/(c) 중 하나. 미충족 시 열을 추가하지 않고 `catalog_unparsed`류 실패 신호를 반환(raw는 영향 없음 — 이 모듈은 텍스트 변환만 하고 커밋하지 않으므로 "실패 시 아무 텍스트도 반환하지 않음"으로 충분).
- [ ] 열 삽입 위치는 형상 (a)의 열 순서(`기타`는 `arch` 뒤·`result` 앞) 기준 제자리. 헤더 구분선(`|---|:--:|…`)도 같은 위치에 정렬 표기 삽입.
- [ ] 열 추가는 **표 하나에 국한**(다른 프로젝트 표 무수정).
- [ ] **카운트 문장 갱신 — 화이트리스트 정규식 2종만**: ① `## 현재 상태` 아래 첫 문장(총 feature/raw + kind별 분해) ② `관련 문서`의 raw 총계 문장. 정규식에 매칭되지 않으면 무조건 불변(날짜 유무 무관). 매칭되더라도 날짜(`\d{4}-\d{2}-\d{2}`)를 포함하면 불변(날짜 규칙이 화이트리스트를 이긴다 — 보조 방어). 갱신 대상 2종에 매칭되는 형태를 찾지 못하면 추측하지 않고 실패 신호.
- [ ] 날짜가 박힌 과거 스냅샷 서술(`**2026-07-28 재스냅샷**: ...`)과 섹션별 산문 카운트(`8 feature 전부 spec·arch·result 완비...`)가 **바이트 단위로 불변**임을 검증하는 테스트가 있다.
- [ ] moon-harness처럼 통합 표에 행으로만 존재하는 프로젝트에 신규 feature를 주입했을 때, 신규 전용 표가 생성되지 않고 기존 통합 표에 행이 추가됨을 검증하는 테스트가 있다(§6.3.2 근거 1과 동일 구조).
- [ ] registry 외 다른 줄은 전부 바이트 단위 보존(허용 연산 3개: 행 추가/셀 `—`→링크/열거된 카운트 문장 갱신 외 어떤 변형도 없음).

### `wiki_log.py` (F7·F10)
- [ ] `index.md`: **Entries의 `sdd-spec-registry` 훅 문장 한 줄만** 교체(카운트 갱신). **최근 변경** 섹션에 이번 배치를 **prepend**. Entries의 다른 줄, `미해결 모순` 섹션은 무수정.
- [ ] `log.md`: **append-only**로 이번 배치 요약 1줄만 추가(AGENTS.md Bulk Ingest 규칙 — "배치 1건 = 로그 1줄").
- [ ] **F10 "양쪽 보존"**: `log.md`는 append-only, `index.md` 최근 변경은 prepend-only이므로 사람의 동시 편집과 병합 충돌이 나도 두 항목 모두 유실 없이 보존되는 형태다. 최소 1개의 통합 테스트로 "사람 편집이 선행한 텍스트 + 우리 항목"이 둘 다 남는지 확인(arch §9.1 M-17 근거 — 사람 편집 텍스트를 먼저 넣고 그 위에 우리 항목을 얹는 케이스).
- [ ] **F7 "배치 1건=1줄" + 카탈로그 재시도 시나리오**: (ii)가 실패했다가 다음 실행에서 성공하는 경우, `log.md`의 그 1줄이 raw 커밋 sha(들)와 카탈로그 커밋 sha를 **모두 열거**한다(`YYYY-MM-DD [snapshot] <총 N raw> — raw 커밋 <sha7>(날짜)·<sha7>(날짜) · 카탈로그 <sha7>(날짜) · 재시도 K회` 형태). 이 함수는 raw 커밋 sha 리스트 + 카탈로그 커밋 sha를 입력으로 받아 그 문자열을 조립하는 순수 함수로 구현한다(실제 재시도 판단/누적은 T-10 apply.py가 호출 시점에 전달).

## 의존 태스크
T-4 (naming — raw 파일명 규칙 `<project>-<feature>-<kind>.md`가 registry 링크 생성의 입력), T-3 (config — `prefix_map` 스키마)

## 예상 변경 파일
- `hooks/lib/kompound_snapshot/registry.py` — 신규
- `hooks/lib/kompound_snapshot/wiki_log.py` — 신규
- `tests/test_kompound_snapshot_registry.py` — 신규
- `tests/test_kompound_snapshot_wiki_log.py` — 신규
- `tests/fixtures/` 하위 registry 골든 텍스트(3형상) — 필요 시 추가(T-2가 이미 만든 `fake_kompound_env` 내장 registry와 공유 가능하면 재사용, 별도 골든이 필요하면 이 태스크에서 추가)

## Steps
- [ ] `registry.py`: 표 탐색(①②③) + 헤딩 매칭(대소문자 무시, 모호=매칭 섹션 개수 기준) 구현
- [ ] `registry.py`: 행 삽입(위치 규칙) + 셀 채우기(`기존 위키`=`—`, `home repo`=`repo_dir`) 구현
- [ ] `registry.py`: 없는 kind 열 추가(안전 조건 2개 검사 + 열 위치 + 구분선 삽입) 구현
- [ ] `registry.py`: 카운트 문장 화이트리스트 갱신(정규식 2종 + 날짜 보조 방어) 구현
- [ ] `wiki_log.py`: index.md 훅 문장 교체 + 최근변경 prepend, log.md append-only 조립(raw/카탈로그 두 시점 표기 포함)
- [ ] `tests/test_kompound_snapshot_registry.py` — ① 6열 표에 `ui` 열 추가 시 기존 행 `—` 채움 + 다른 열/줄 바이트 불변 ② 8열 통합표 기존 프로젝트 귀속(신설 안 함) ③ 진짜 새 프로젝트 ③단계 7열 신설 ④ 안전조건 미충족 → 실패신호 ⑤ 날짜 포함 줄 불변 ⑥ 산문 카운트 줄 불변 — 골든 텍스트 in/out 비교로 작성
- [ ] `tests/test_kompound_snapshot_wiki_log.py` — index prepend, log append, 동시 편집 2항목 보존, raw/카탈로그 두 시점 표기 문자열 조립
- [ ] `pytest tests/test_kompound_snapshot_registry.py tests/test_kompound_snapshot_wiki_log.py -v` GREEN 확인

## 검증 명령어
```bash
PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/test_kompound_snapshot_registry.py tests/test_kompound_snapshot_wiki_log.py -q
```

## 테스트 스코프
`tests/test_kompound_snapshot_registry.py` + `tests/test_kompound_snapshot_wiki_log.py` — 또는 `pytest tests/ -k "kompound and (registry or wiki_log)"`
