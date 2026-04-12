---
name: git-worktree
description: "Use when starting isolated feature work that should not affect the current working directory — creates a git worktree with a dedicated branch"
argument-hint: "[feature-name]"
context: fork
---

# Git Worktree 생성

feature 브랜치 + worktree를 생성하여 격리된 작업 환경을 만든다.

**인수**: `$ARGUMENTS` — feature 이름 (kebab-case). 예: `money-track-mvp`

## 사용 시점

- SDD Phase 2 진입 시 (sdd 스킬에서 호출) — Phase 2, 3, 4 모두 이 worktree 안에서 작업
- 독립적인 기능 작업이 현재 디렉토리에 영향을 주지 않아야 할 때

## 프로세스

1. **브랜치명**: `feat/$ARGUMENTS`
2. **worktree 경로**: `./worktrees/$ARGUMENTS`
   - **프로젝트 루트** 아래 `worktrees/` 디렉토리에 생성
   - `.claude/` 아래에 절대 생성하지 않는다 (설정 디렉토리, 권한 문제)
   - 이미 존재하면 사용자에게 알림
3. **생성**:
   ```bash
   git worktree add ./worktrees/$ARGUMENTS -b feat/$ARGUMENTS
   ```
4. **안전 검증**:
   - worktree 경로가 `.gitignore`에 포함되어 있는지 확인 (없으면 추가)
   - 생성된 디렉토리에서 `git status`로 정상 상태 확인
5. **스냅샷 커밋** (CLAUDE.md 규칙):
   ```bash
   cd ./worktrees/$ARGUMENTS
   git add -A
   git commit -m "snapshot: $ARGUMENTS 작업 시작 전" --allow-empty
   ```

## 출력

호출자에게 다음 정보를 반환:
- worktree 절대 경로: `{project-root}/worktrees/$ARGUMENTS`
- 브랜치명: `feat/$ARGUMENTS`
- 생성 성공 여부

## 정리

worktree 정리는 이 스킬의 책임이 아니다. 호출자(sdd 스킬)가 완료 후 처리한다:
```bash
git worktree remove ./worktrees/$ARGUMENTS
```

## 에러 처리

- 브랜치가 이미 존재: 사용자에게 기존 브랜치 사용 여부 확인
- 디스크 부족 / 경로 충돌: 에러 메시지와 함께 사용자에게 알림
- 생성 실패: 원인 로그 출력 후 수동 생성 가이드 제공
