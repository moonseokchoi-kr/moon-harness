---
name: git-worktree
description: "Use when starting isolated feature work that should not affect the current working directory — creates a git worktree with a dedicated branch"
---

# Git Worktree 생성

feature 브랜치 + worktree를 생성하여 격리된 작업 환경을 만든다.

## 사용 시점

- SDD Phase 3 진입 시 (sdd 스킬에서 호출)
- 독립적인 기능 작업이 현재 디렉토리에 영향을 주지 않아야 할 때

## 프로세스

1. **브랜치명 결정**: `feat/{feature-name}` (kebab-case)
2. **worktree 경로 결정**: `worktrees/{feature-name}`
   - 프로젝트 디렉토리의 부모 디렉토리에 생성
   - 이미 존재하면 사용자에게 알림
3. **생성**:
   ```bash
   git worktree add worktrees/{feature-name} -b feat/{feature-name}
   ```
4. **안전 검증**:
   - worktree 경로가 `.gitignore`에 포함되어 있는지 확인 (프로젝트 로컬인 경우)
   - 생성된 디렉토리에서 `git status`로 정상 상태 확인
5. **스냅샷 커밋** (CLAUDE.md 규칙):
   ```bash
   cd worktrees/{feature-name}
   git add -A
   git commit -m "snapshot: {feature-name} 작업 시작 전" --allow-empty
   ```

## 출력

컨트롤러에게 다음 정보를 반환:
- worktree 경로
- 브랜치명
- 생성 성공 여부

## 정리

worktree 정리는 이 스킬의 책임이 아니다. 호출자(sdd 스킬)가 Phase 3 완료 후 처리한다:
```bash
git worktree remove worktrees/{feature-name}
```

## 에러 처리

- 브랜치가 이미 존재: 사용자에게 기존 브랜치 사용 여부 확인
- 디스크 부족 / 경로 충돌: 에러 메시지와 함께 사용자에게 알림
- 생성 실패: 원인 로그 출력 후 수동 생성 가이드 제공
