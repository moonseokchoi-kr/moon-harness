# moon-harness

AI 에이전트 전체 개발 라이프사이클(아이디어 → 구현 → 배포)을 구조화하는 Claude Code 플러그인.
SDD 파이프라인, 아이디어 워크샵, 자가개선 시스템(pr-converge + self-improve), enforcement 훅.

## 구성

| 디렉터리 | 내용 |
|----------|------|
| `skills/` | 스킬 (sdd, sdd-orchestrator, harness, idea-workshop, pr-converge, self-improve, git-worktree, …) |
| `agents/` | 서브에이전트 정의 (sdd-*, harness-improvement-critic, architect 등) |
| `hooks/` | bash enforcement 훅 + `hooks/lib/self_improve/` (결정적 코어 Python 패키지) |
| `benchmarks/` `evals/` | 자가개선 측정 substrate (fitness function + 라이브 eval) |
| `tests/` | 결정적 코어 오프라인 pytest 스위트 |
| `docs/sdd/` | SDD 사이클 산출물 (spec/design/task/result) |

## 빌드 / 테스트

```bash
# pytest는 homebrew python(3.14)에 설치됨 — Xcode python3엔 없음
PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/ -q
```

오프라인(`tests/`, 네트워크/LLM 무호출)과 라이브(`evals/`, claude -p)는 **비혼합**. `pytest tests/`는 `evals/`를 수집하지 않는다.

## 핵심 규칙

- **결정↔판단 분리**: 결정적 로직(상태머신·게이트·커서·케이던스·티어분류·재발률)은 `hooks/lib/self_improve/` Python **stdlib-only**(네트워크/LLM 무호출, fail-safe). 판단 로직(분류·클러스터링·critic 반박)만 SKILL/agent 프롬프트.
- **2티어 격리**: 프로젝트 티어(repo 안)=자동 / 하네스 티어(플러그인 skills·agents·hooks)=제안 + 사람 승인. 애매하면 하네스 티어.
- **protected set**: `self-improve`, `pr-converge`, `harness-improvement-critic`, 게이트 스크립트는 자동 생성/수정 금지(사람만).
- **벤치마크 = fitness function**: 하네스 변경은 점수↑ AND held-out 회귀0 일 때만 채택. 콜드스타트 시 채택 불가.
- **브랜치 prefix**: feature 작업 브랜치는 `feature/` 아래에 생성 (`feat/` 아님).
- **버전**: `.claude-plugin/plugin.json` 과 `marketplace.json` 의 버전을 항상 동기화.
- **git (병렬 작업)**: 공유 worktree 병렬 에이전트는 **소유 파일만 명시적 `git add`**(`-A`/`.` 금지) + **브랜치 전환 금지**. (근거: .harness/LEARNING.md)

## Lessons / 자가개선

이 repo는 자기 자신을 dogfood한다. SDD 사이클 중 발견된 raw 교훈은 아래 로그에 누적되고, self-improve 루프가 검증 후 반영한다.

# SDD Agent Learning Log (auto-loaded, raw)
@.harness/LEARNING.md
