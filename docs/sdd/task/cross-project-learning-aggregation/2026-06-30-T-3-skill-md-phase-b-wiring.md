# T-3: SKILL.md Phase B 배선 텍스트 갱신

## 관련 문서
- spec: `docs/sdd/spec/2026-06-30-cross-project-learning-aggregation.md`
- arch: `docs/sdd/design/arch/2026-06-30-cross-project-learning-aggregation.md`

## 구현자
sdd-implementer

## 테스트 타입
이 태스크에서 변경되는 레이어와 테스트 방식:

| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| SKILL.md Phase B 절차 텍스트 | 검증(수동 diff 확인) | 코드 변경 없음 — 절차 서술 텍스트 수정. test-automator 스코프 없음 |
| Phase A/C/D 무변경 | 검증(수동 diff 확인) | 변경 금지 구역 명시 (F4 Acceptance) |

(arch §5.3(b) SKILL.md 절차 텍스트 변경 지점 기반. 결정적 로직 파일 변경 내용 포함 금지)

## 완료 조건
- [ ] `skills/self-improve/SKILL.md` Phase B(진단·클러스터 단계) 절차의 entries 출처 서술이 "로컬 `.harness/LEARNING.md`만" → "집계 로더(`learning_source.py`)로 로컬 LEARNING.md + (config의 `cross_project_store`가 가리키는) 교차-repo store `*.md`를 합쳐 읽기"로 갱신됨 (F4)
- [ ] Phase B의 `count_signals()` 호출 지점 설명이 "집계 로더로 합쳐진 entries를 `count_signals()`에 전달"로 정밀화됨 (F4, arch §5.3(b) L175 해당 문장)
- [ ] `store_dir` 미설정(config 없음) 시 로컬-only 동작이 기존과 동일함을 Phase B 설명에 명시 (F4)
- [ ] 갱신된 SKILL.md의 Phase B에 "집계 로더" 또는 동등한 표현과 `learning_source.py` 참조가 포함됨 (F4 Acceptance)
- [ ] SKILL.md의 다른 Phase(A, C, D) 절차가 변경되지 않음 (F4 Acceptance)
- [ ] SKILL.md 내에 결정적 로직 파일(recurrence.py, parser.py 등) 수정을 지시하는 내용 추가 없음 (F4 Acceptance)
- [ ] protected set 관련 arch §2 주의사항 준수 — "자동수정 금지"가 아닌 "사람 주도 SDD 편집"임이 수정 맥락에서 명확함 (arch §2 `> 📌`)

## 의존 태스크
없음 (T-1과 독립적 — 코드 의존 없음, Wave 1 병렬 실행 가능)

## 예상 변경 파일
- `skills/self-improve/SKILL.md` — Phase B 절차 텍스트 수정 (arch §5.3(b) 지정 위치: Phase A 문장 1 또는 Phase B 도입부, F16 섹션 `> 📌` 문장)

## Steps
- [ ] `skills/self-improve/SKILL.md` 현재 내용 확인 — arch §5.2에서 특정한 "Phase A L73" 및 "F16 섹션 L175 `> 📌`" 위치 파악
- [ ] Phase A/B 도입부의 entries 출처 서술 위치 특정 (현재 "로컬 `.harness/LEARNING.md`만" 서술 문장)
- [ ] 해당 문장을 arch §5.3(b) 지시에 따라 갱신: 집계 로더 언급 + `learning_source.py` 참조 + config 없으면 로컬-only 명시
- [ ] F16 섹션 `> 📌` `count_signals()` 호출 지점 문장 갱신: "합쳐진 entries를 전달" + "store 미설정 시 로컬 entries만(하위호환)" 추가
- [ ] Phase C, D, F17/F18/F19, 안전 규칙 절 변경 없음 재확인 (diff 확인)
- [ ] git diff로 변경 범위가 Phase B 관련 텍스트에만 국한됨 확인

## 검증 명령어
빌드 프로파일: fast-scoped — 이 태스크는 Python 코드 변경 없음. 텍스트 수정 검증은 git diff로 확인.

```bash
git diff skills/self-improve/SKILL.md
```

기존 테스트 회귀 검증(SKILL.md가 스크립트 테스트에 영향 없는지):

```bash
python3 -m pytest tests/test_self_improve_scripts.py -q
```
