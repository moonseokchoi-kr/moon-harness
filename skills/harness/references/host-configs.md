# Host Configurations — 멀티 호스트 설정

## 개요

같은 스킬 소스를 여러 AI 코딩 에이전트에서 사용할 수 있도록 호스트별 변환 규칙을 정의한다.
현재 지원: Claude Code, Codex. 추가 호스트는 요구 시 확장.

## 호스트별 차이점

| 항목 | Claude Code | Codex | Copilot |
|------|------------|-------|--------|
| 스킬 경로 | `~/.claude/skills/` | `~/.agents/skills/` | `~/.copilot/skills/` |
| 설정 파일 | `CLAUDE.md` | `AGENTS.md` | `COPILOT.md` |
| 도구 이름 | Bash tool | Exec tool | Exec tool |
| 훅 시스템 | `.claude/settings.json` | `.agents/config.json` (다를 수 있음) | `.copilot/settings.json` (다를 수 있음) |
| 에이전트 시스템 | Agent tool (subagent_type) | Codex 자체 에이전트 시스템 | Copilot 에이전트 시스템 (다를 수 있음) |

## 변환 규칙

setup.sh가 `--host codex`로 실행될 때 적용하는 변환:

### 경로 변환
```
.claude/     → .agents/
CLAUDE.md    → AGENTS.md
```

### 도구명 변환
```
"use the Bash tool"     → "use the Exec tool"
"use the Agent tool"    → "delegate to a sub-agent"
"Claude Code"           → "Codex"
```

### 프론트매터 변환
Codex는 SKILL.md의 frontmatter 중 name과 description만 사용:
```yaml
# Claude Code (전체 유지)
---
name: sdd
description: "full description..."
---

# Codex (name + description만)
---
name: sdd
description: "full description..."
---
```

### 훅 비호환

Codex의 훅 시스템이 Claude Code와 다를 수 있다.
setup.sh는 훅을 설치하지 않고, 대신 AGENTS.md에 규칙으로 기술한다:

```markdown
# Rules (Codex)
- .env 파일을 커밋하지 않는다
- rm -rf 실행 전 확인을 요청한다
- 세션 종료 시 docs/pitfalls.md와 docs/lessons-learned.md를 업데이트한다
```

## 새 호스트 추가

1. `references/host-configs.md`에 호스트 정보 추가
2. `scripts/setup.sh`의 case 문에 호스트 추가
3. 필요시 변환 로직 추가

gstack처럼 8개 호스트를 미리 만들지 않는다. **실제 사용자 요구가 있을 때만 추가.**
