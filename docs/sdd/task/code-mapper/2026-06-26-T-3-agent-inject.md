# T-3: sdd-implementer 최소 침습 단락 주입

## 관련 문서
- spec: `docs/sdd/spec/2026-06-26-code-mapper.md`
- arch: `docs/sdd/design/arch/2026-06-26-code-mapper.md`

## 구현자
`sdd-implementer`

## 테스트 타입
이 태스크에서 변경되는 레이어와 테스트 방식:

| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| 에이전트 주입 (`agents/sdd-implementer.md`) | 통합(수동 리뷰) | 주입 전/후 diff 검토: 단락 1개, 기존 섹션 원문 동일, 포인터만 |

(arch 문서의 테스트 전략 기반. test-automator가 이 정보를 참고하여 적합한 프레임워크로 RED 테스트 작성)

## 완료 조건

- [ ] `agents/sdd-implementer.md`에 정확히 1개의 신규 단락이 추가된다 (기존 내용 변경 없음)
- [ ] 주입 위치: `## 작업 순서` 섹션 직후, `## 커밋 규칙` 섹션 직전 (arch §9 지정)
- [ ] 주입 단락 제목: `## 구조적 컨텍스트 권고 (게이트 아님)`
- [ ] 주입 단락 내용이 다음 세 항목을 포함한다:
  1. codegraph MCP 가용 시 구조적 탐색 우선 사용 안내
  2. 낯선 심볼 편집 전 `/code-mapper`(또는 codegraph 직접 호출)로 실제 호출관계 구조적 컨텍스트 확보 권고 (의무·게이트 아님)
  3. `skills/code-mapper/SKILL.md` 포인터 (절차 본문 없이)
- [ ] 주입 단락에 `ephemeral`, 저장 금지 언급이 있다
- [ ] 기존 `## 입력`, `## 작업 순서`, `## 커밋 규칙`, `## 완료 판정`, `## 코드 조직`, `## 한계 인식` 섹션의 내용이 원문과 동일하다 (0 변경)
- [ ] 도달 범위가 `agents/sdd-implementer.md` 단일 파일로 한정된다 (다른 에이전트 파일 미변경)

## 의존 태스크
T-2 (`skills/code-mapper/SKILL.md` 존재해야 포인터 타겟이 유효함)

## 예상 변경 파일
- `agents/sdd-implementer.md` — 단락 1개 추가 (준-protected, 최소 침습)

## Steps
- [ ] `agents/sdd-implementer.md` 현재 내용 전체 읽기 및 `## 작업 순서` / `## 커밋 규칙` 섹션 경계 확인
- [ ] arch §9 제안 문구를 기반으로 주입 단락 초안 작성 (절차 본문 없이 SKILL.md 포인터만)
- [ ] `## 작업 순서` 섹션 직후에 단락 삽입 (Edit 도구로 정확한 위치 지정)
- [ ] 삽입 후 `## 커밋 규칙` 이하 기존 섹션이 원문과 동일한지 확인 (diff 검토)
- [ ] 다른 에이전트 파일에 변경이 없음을 확인

## 검증 명령어
빌드 프로파일: fast-scoped. 마크다운 변경이므로 pytest 스코프 없음. 회귀 방지용 전체 실행.

```bash
PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/ -q
```
