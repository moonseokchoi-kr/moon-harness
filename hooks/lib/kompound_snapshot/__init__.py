"""hooks.lib.kompound_snapshot — kompound 박제(snapshot) 결정적 코어 패키지.

`hooks/lib/self_improve/`의 형제 패키지다. SDD 사이클이 만든 spec/arch/ui/api
/context/result 문서를 marvelous_kompound(`raw/` + `wiki/sdd-spec-registry.md`
+ `wiki/index.md` + `wiki/log.md`)에 verbatim 박제하는 로직을 담는다.

설계 SSOT: docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md
(이하 "arch"로 인용) §3(모듈 분해) · §6(영속화/IO 경계) · §9.3(공용 fixture).

## Fail-safe 규약 (arch §1 원칙 2, CLAUDE.md 결정↔판단 분리)

이 패키지의 모든 공개 함수는 **예외를 밖으로 던지지 않는다.** 무엇이 잘못됐는지는
구조화된 결과 dict(예: ``{"ok": bool, ...}``)로 반환하고, 예상치 못한 예외는 최상위
`cli.main()`이 잡아 F11의 "스캔 실패"(``scan_error``) 신호로 변환한다. 이 패키지는
stdlib만 사용하며 네트워크/LLM 호출을 하지 않는다(F13). `git` 서브프로세스 호출은
예외다 — 로컬 상태 조회/커밋에 한하며 `fetch`/`pull`/`push`는 절대 하지 않는다(A3).

## 12모듈 구성 (arch §3.1 디렉토리 경계 — 각 모듈이 이 파일 아래에 추가된다)

| 모듈 | 책임 (arch §3.2 요약) |
|---|---|
| ``config`` | F16 설정 해석 — env → 프로젝트 파일 → 홈 파일 → 자동 탐색, 키 단위 병합. 단일 진입점 ``resolve_config()`` |
| ``scan`` | F3 앵커 탐색 · 포함/제외 · md5 수집 (read-only) |
| ``naming`` | F4 네이밍 변환 + F12 미등록 프리픽스 판정 (순수 함수) |
| ``dedup`` | F5 md5 그룹핑 · canonical 선택 (순수 함수) |
| ``apply`` | F6 멱등 적용 — (i) raw 복사 (ii) 카탈로그 갱신의 2단 트랜잭션 + 단계별 저널/롤백 |
| ``registry`` | F7 `sdd-spec-registry.md` 표 탐색 3단 · 행/열 외과적 수정 · 카운트 문장 갱신 |
| ``wiki_log`` | F7·F10 `index.md` prepend · `log.md` append (append/prepend-only) |
| ``verify`` | F8 검증 게이트 3종 (read-only) — ``snapshot_set_rule`` 전제 |
| ``git_state`` | F9 dirty/divergence 판정(네트워크 없이) · 커밋 · 배타 락 |
| ``wt_target`` | F2 Bash 명령 문자열 → 워크트리 경로 파싱 (순수 함수) |
| ``report`` | F11 verdict/종료 코드 분리 · human/JSON 리포트 — 종료 코드 표(arch §6.2)의 단일 진실 |
| ``runtime_state`` | T1 멱등·무장·안내 1회 판정 — 런타임 상태 값 6종(arch §5.1.2)의 단일 진실, `.claude/state/kompound-snapshot.json` |

**주의**: 종료 코드 표(0/10/20/30/40/45/50/55/60/70)와 런타임 상태 값 6종
(``PENDING``/``CATALOG_PENDING``/``DONE``/``SKIPPED_UNCONFIGURED``/``FAILED``/
``GIVEN_UP``)은 여러 모듈이 참조하지만 그 정의의 단일 진실은 각각 ``report``와
``runtime_state``다(위 표, arch §11 F1/F11 추적 행). 이 ``__init__.py``는 그
값들을 중복 정의하지 않는다 — 이 파일이 아직 어떤 모듈도 import하지 않기 때문이다.

## 현재 상태 (이 태스크 시점)

이 패키지에는 아직 하위 모듈이 없다. 위 표는 앞으로 추가될 모듈의 계약을
고정하는 참조 문서일 뿐이며, 이 파일은 아직 존재하지 않는 모듈을 import하지
않는다(순환 없음 · import 실패 없음). 공개 API 재노출(``from .config import
resolve_config`` 등, ``hooks/lib/self_improve/__init__.py`` 관례)은 모든
모듈이 갖춰진 뒤 T-11이 채운다.

## 의존 방향 (arch §4)

``kompound_snapshot`` → ``hooks.lib.self_improve.state_io`` (단방향, 원자적
write·ISO 시간 유틸 재사용). 역방향 의존은 없다 — ``self_improve``는 이
패키지를 절대 import하지 않는다.
"""

from __future__ import annotations

__all__: list[str] = []
