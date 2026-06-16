"""skills/pr-converge/scripts/ — pr-converge 결정적 글루 스크립트.

이 패키지의 모든 모듈은:
- Python 3.9+ stdlib only (네트워크/LLM/gh 호출 절대 금지)
- hooks.lib.self_improve 코어를 import해 결정 로직 위임
- fail-safe: 예외를 raise하지 않고 구조화된 결과 반환

판단 로직(gh 관측, 코멘트 분류, 엔지니어 디스패치)은 skills/pr-converge/SKILL.md에서 담당.
결정적 로직(상태 전이, 중복 필터링, 패턴 감지, LEARNING append)은 이 패키지에서 담당.
"""
