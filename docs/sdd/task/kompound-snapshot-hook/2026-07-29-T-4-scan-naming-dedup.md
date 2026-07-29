# T-4: F3/F4/F5/F12 — 스캔 · 네이밍 · dedup (`scan.py` / `naming.py` / `dedup.py`)

## 관련 문서
- spec: `docs/sdd/spec/2026-07-29-kompound-snapshot-hook.md` — F3(수집 스코프), F4(네이밍), F5(dedup), F12(미등록 프리픽스)
- arch: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md` — §5.4(수집·식별·네이밍 전체), §5.4.1(스캔), §5.4.2(repo_dir 도출), §5.4.3(네이밍), §5.4.4(dedup), §2.3(앵커 탐색 깊이 제한 성능 근거)

## 구현자
sdd-python-engineer

## 테스트 타입
스캔=통합(`fake_workspace`, arch §9.1), 네이밍/dedup=단위(순수 함수)

## 완료 조건

### 스캔 (`scan.py`, F3)
- [ ] 상수가 arch §5.4.1과 바이트 그대로 일치: `KINDS = {"spec":"spec","specs":"spec","arch":"arch","ui":"ui","api":"api","result":"result","development":"arch","context":"context"}`, `SKIP_DIRS = {".git","node_modules","build","ExternLib",".venv","venv"}`, `SKIP_NAMES = ("ORCHESTRATOR_STATE","HANDOFF","-GUIDE","DESIGN.md","test-guide-")`.
- [ ] **2단 스캔**: ① 앵커 탐색 — 스코프 루트에서 깊이 ≤ `max_anchor_depth`(기본 5, config에서 주입)까지만 순회해 `docs/sdd`/`Docs/sdd` 디렉토리를 찾는다(`SKIP_DIRS` 프루닝, `*/worktrees/*`는 프루닝하지 않음). ② 앵커 하위는 깊이 제한 없이 전수 순회(`SKIP_DIRS` 적용).
- [ ] kind 결정은 앵커부터 현재 디렉토리까지의 세그먼트를 **역순으로** 훑어 `KINDS`에 먼저 걸리는 값을 채택. 못 찾으면 대상 아님.
- [ ] `/task` 세그먼트가 경로에 있으면 스킵(`task/`·`tasks/` 동시 커버). 파일명이 `SKIP_NAMES` 부분 포함 시 스킵. `.md`가 아니면 스킵.
- [ ] 레코드 스키마: `{"kind","path","md5","mtime","repo_dir"}`. md5는 바이트 해시.
- [ ] 개별 파일/디렉토리 권한 오류는 예외를 던지지 않고 `errors[]`에 누적하며 스캔을 계속한다. `errors`가 비어있지 않으면 최종 verdict가 `scan_error`로 이어지도록 결과에 신호를 남긴다(실제 verdict 매핑은 T-11 cli.py 몫 — 이 태스크는 `errors[]` 필드 정확성까지만 책임진다).
- [ ] `task/`·`tasks/` 하위 md, `HANDOFF.md`, `ORCHESTRATOR_STATE*.md`가 스캔 결과에서 0건임을 검증하는 테스트가 있다(spec F3 Acceptance 그대로).
- [ ] 결과에 `anchors`(발견된 앵커 수) 카운트가 포함된다(§2.3 "조용한 미탐 방지" — `anchors=N depth_limit=D`).

### repo_dir 도출 (arch §5.4.2, F4/F12의 입력)
- [ ] 앵커에서 위로 올라가며: (1) 경로에 `worktrees` 세그먼트가 있으면 그 세그먼트의 **부모**를 repo 루트로 즉시 채택. (2) 아니면 `.git`(디렉토리 또는 `gitdir:` 파일)을 가진 첫 조상을 채택 — `gitdir:` 파일이면 내용을 파싱해 `/.git/worktrees/<name>` 접미사를 제거한 본체 repo 루트를 도출(파싱 실패 시 예외 없이 다음 규칙으로 폴백). (3) 둘 다 실패하면 스코프 루트 자신.
- [ ] `prefix_map` 조회 키는 채택된 repo 루트의 **디렉토리 이름**. 실패 시 `scan_root` 기준 상대경로의 선두 1세그먼트 → 선두 2세그먼트(`/` 결합) 순으로 완화 재조회.

### 네이밍 (`naming.py`, F4/F12)
- [ ] 출력 `raw/<project>-<feature>-<kind>.md`. `<project>` = `prefix_map[repo_dir]`(대소문자 등 부가 처리 없음, 정확 키 조회). 조회 실패 또는 값이 `null`이면 예외 없이 `{"unmapped": repo_dir}` 반환.
- [ ] `<kind>` = `KINDS` 매핑 결과.
- [ ] `<feature>` = 원본 파일명(stem)에서 날짜 프리픽스(`^\d{4}-\d{2}-\d{2}-`) 제거 + 접미사(`-spec`/`-dev`/`-result`) 제거.
- [ ] `<project>-<project>-...` 꼴이면 하나를 접는다(예: `codegraph-codegraph-internal-mcp-result` → `codegraph-internal-mcp-result`).
- [ ] 최소 10개 프리픽스 각각 + 중복 접기 케이스 1건 이상을 커버하는 pytest 케이스가 통과한다(spec F4 Acceptance).
- [ ] 미등록 repo 입력 시 예외 없이 `unmapped` 신호를 반환한다(F12 연동, spec F4 Acceptance).

### dedup (`dedup.py`, F5)
- [ ] `(kind, md5)`로 그룹핑. 그룹 내 경로 정렬 키는 정확히 `("worktrees" in x, len(x))`(참고 구현 동일) — non-worktree 우선, 짧은 경로 우선. 첫 번째를 canonical로 채택.
- [ ] 해시가 다른 main/worktree 쌍은 **별개 문서**로 취급하고 `mtime`이 더 최근인 것을 채택.
- [ ] (a) 동일 해시 3사본(main 1 + worktree 2) → non-worktree 선택 (b) 동일 해시 worktree 2사본만 → 짧은 경로 선택 (c) 해시가 다른 main/worktree 쌍 → 별개 문서 2건 반환 — 3케이스 전부 pytest로 검증(spec F5 Acceptance 그대로).

## 의존 태스크
T-2 (패키지 스켈레톤 + `fake_kompound_env`/`fake_workspace`), T-3 (config가 정의하는 `prefix_map`/`max_anchor_depth` 스키마 — 실제 import 의존은 없고 스키마 계약만 공유)

## 예상 변경 파일
- `hooks/lib/kompound_snapshot/scan.py` — 신규
- `hooks/lib/kompound_snapshot/naming.py` — 신규
- `hooks/lib/kompound_snapshot/dedup.py` — 신규
- `tests/test_kompound_snapshot_scan.py` — 신규
- `tests/test_kompound_snapshot_naming.py` — 신규
- `tests/test_kompound_snapshot_dedup.py` — 신규

## Steps
- [ ] `scan.py`: 상수 정의 + 앵커 탐색(깊이 제한) + 앵커 하위 전수 순회 + kind 결정 + 제외 규칙 + 레코드 생성 + `errors[]` 누적
- [ ] `scan.py`: `repo_dir` 도출 함수(§5.4.2 규칙 1~4, gitdir 파싱 포함)
- [ ] `naming.py`: prefix 조회 + kind 매핑 + feature 추출(정규식) + 프리픽스 중복 접기, `unmapped` 신호 경로
- [ ] `dedup.py`: `(kind, md5)` 그룹핑 + 정렬 키 + 해시 상이 시 mtime 비교
- [ ] `tests/test_kompound_snapshot_scan.py` 작성 — `fake_workspace` 트리(정상 케이스 + `task/`·`HANDOFF.md`·`ORCHESTRATOR_STATE.md` 제외 케이스 + 워크트리 문서 포함 케이스 + 권한 오류 시뮬레이션으로 `errors[]` 누적) + `repo_dir` 도출(일반 `.git` / `worktrees/` 세그먼트 / `gitdir:` 파일 파싱 / 완화 재조회) 커버
- [ ] `tests/test_kompound_snapshot_naming.py` 작성 — 10개 프리픽스 개별 + 중복 접기 + 미등록 케이스
- [ ] `tests/test_kompound_snapshot_dedup.py` 작성 — (a)(b)(c) 3케이스
- [ ] `pytest tests/test_kompound_snapshot_scan.py tests/test_kompound_snapshot_naming.py tests/test_kompound_snapshot_dedup.py -v` GREEN 확인

## 검증 명령어
```bash
PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/test_kompound_snapshot_scan.py tests/test_kompound_snapshot_naming.py tests/test_kompound_snapshot_dedup.py -q
```

## 테스트 스코프
`tests/test_kompound_snapshot_scan.py` + `tests/test_kompound_snapshot_naming.py` + `tests/test_kompound_snapshot_dedup.py` — 또는 `pytest tests/ -k "kompound and (scan or naming or dedup)"`
