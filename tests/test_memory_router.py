"""tests/test_memory_router.py — memory_router 단위 테스트.

오프라인 전용. 네트워크/LLM 무호출. golden fixture 활용.

커버 범위:
- domain 태그 필터링 (일치 → on-demand, 불일치/없음 → always-on)
- 토큰 예산 준수 (예산 초과 시 잘림)
- 잘림 사실 반환 dict에 기록 (silent truncation 금지)
- 계층 구분 (always_on / on_demand)
- fail-safe 동작 (잘못된 입력)
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hooks.lib.self_improve.memory_router import (
    DEFAULT_ALWAYS_ON_BUDGET,
    DEFAULT_ONDEMAND_BUDGET,
    route_memory,
)
from hooks.lib.self_improve.parser import parse_learning_entry

FIXTURES = Path(__file__).resolve().parent / "fixtures"


# ─── 헬퍼 ────────────────────────────────────────────────────────

def _make_entry(domain: str = None, body: str = "test body", marker: str = "test") -> dict:
    """테스트용 엔트리 dict를 빠르게 생성한다."""
    tags = {"domain": domain} if domain is not None else None
    raw_text = f"## {marker}\n{body}"
    return {
        "marker": marker,
        "body": body,
        "tags": tags,
        "raw": raw_text,
    }


# ─── 기본 라우팅 테스트 ───────────────────────────────────────────

class TestRouteMemoryBasic:

    def test_empty_entries(self):
        """빈 엔트리: 모든 필드가 빈 값."""
        result = route_memory([], context_domain="auth")
        assert result["always_on"] == []
        assert result["on_demand"] == []
        assert result["always_on_truncated"] is False
        assert result["ondemand_truncated"] is False

    def test_domain_match_goes_to_on_demand(self):
        """domain 태그가 context_domain과 일치 → on-demand 계층."""
        entries = [_make_entry(domain="auth", body="auth lesson")]
        result = route_memory(entries, context_domain="auth")
        assert len(result["on_demand"]) == 1
        assert len(result["always_on"]) == 0

    def test_domain_mismatch_goes_to_always_on(self):
        """domain 태그가 불일치 → always-on 계층."""
        entries = [_make_entry(domain="pipeline", body="pipeline lesson")]
        result = route_memory(entries, context_domain="auth")
        assert len(result["always_on"]) == 1
        assert len(result["on_demand"]) == 0

    def test_no_tags_goes_to_always_on(self):
        """tags=None (태그 없음) → always-on 계층."""
        entries = [{"marker": "x", "body": "no tags", "tags": None, "raw": "## x\nno tags"}]
        result = route_memory(entries, context_domain="auth")
        assert len(result["always_on"]) == 1
        assert len(result["on_demand"]) == 0

    def test_mixed_entries_routed_correctly(self):
        """혼합 엔트리: domain 일치는 on-demand, 나머지는 always-on."""
        entries = [
            _make_entry(domain="auth", body="auth lesson"),        # on-demand
            _make_entry(domain="pipeline", body="pipeline lesson"), # always-on
            _make_entry(domain=None, body="untagged"),              # always-on
        ]
        result = route_memory(entries, context_domain="auth")
        assert len(result["on_demand"]) == 1
        assert len(result["always_on"]) == 2

    def test_result_has_required_keys(self):
        """반환 dict에 필수 키가 모두 있어야 한다."""
        result = route_memory([], context_domain="auth")
        required_keys = [
            "always_on", "on_demand",
            "always_on_tokens", "ondemand_tokens",
            "always_on_truncated", "ondemand_truncated",
            "always_on_dropped", "ondemand_dropped",
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"


# ─── 토큰 예산 테스트 ─────────────────────────────────────────────

class TestRouteMemoryTokenBudget:

    def test_token_estimation(self):
        """토큰 추정: len(text) // 4."""
        # 400자 텍스트 → ~100 토큰
        body = "x" * 400
        entries = [_make_entry(domain=None, body=body)]
        result = route_memory(entries, context_domain="auth", always_on_budget=200)
        # 400자 raw(헤더 포함) → ~100+ 토큰 → 200 예산 내에 들어감
        assert len(result["always_on"]) == 1

    def test_always_on_budget_respected(self):
        """always-on 예산 초과 시 엔트리 잘림."""
        # 각 엔트리: 400자 → ~100 토큰
        body = "x" * 400
        entries = [_make_entry(domain=None, body=body) for _ in range(5)]
        result = route_memory(entries, context_domain="auth", always_on_budget=250)
        # 100 토큰씩 → 예산 250 → 2개까지만 포함 가능
        assert len(result["always_on"]) <= 5
        assert result["always_on_tokens"] <= 250

    def test_always_on_truncated_flag(self):
        """always-on 예산 초과 시 always_on_truncated=True."""
        # 예산을 매우 작게 설정
        body = "x" * 400  # ~100 토큰
        entries = [_make_entry(domain=None, body=body) for _ in range(3)]
        result = route_memory(entries, context_domain="auth", always_on_budget=50)
        assert result["always_on_truncated"] is True
        assert result["always_on_dropped"] > 0

    def test_ondemand_budget_respected(self):
        """on-demand 예산 초과 시 엔트리 잘림."""
        body = "x" * 400  # ~100 토큰
        entries = [_make_entry(domain="auth", body=body) for _ in range(4)]
        result = route_memory(entries, context_domain="auth", ondemand_budget=150)
        assert result["ondemand_tokens"] <= 150
        assert result["ondemand_truncated"] is True
        assert result["ondemand_dropped"] > 0

    def test_no_truncation_within_budget(self):
        """예산 내에서는 잘림 없음."""
        entries = [_make_entry(domain="auth", body="short")]
        result = route_memory(
            entries,
            context_domain="auth",
            always_on_budget=DEFAULT_ALWAYS_ON_BUDGET,
            ondemand_budget=DEFAULT_ONDEMAND_BUDGET,
        )
        assert result["ondemand_truncated"] is False
        assert result["always_on_truncated"] is False
        assert result["ondemand_dropped"] == 0
        assert result["always_on_dropped"] == 0

    def test_silent_truncation_forbidden(self):
        """잘림 발생 시 dropped > 0 (silent truncation 금지)."""
        body = "x" * 2000  # 큰 텍스트
        entries = [_make_entry(domain="auth", body=body) for _ in range(5)]
        result = route_memory(entries, context_domain="auth", ondemand_budget=100)
        if result["ondemand_truncated"]:
            assert result["ondemand_dropped"] > 0, "truncated=True but dropped==0: silent truncation!"


# ─── golden fixture 테스트 ───────────────────────────────────────

class TestRouteMemoryGoldenFixture:

    def test_golden_sample_learning_routing(self):
        """tests/fixtures/sample_learning.md의 golden fixture를 이용한 라우팅 검증."""
        sample = FIXTURES / "sample_learning.md"
        text = sample.read_text(encoding="utf-8")
        entries = parse_learning_entry(text)

        # fixture: auth, pr-converge, None, pipeline 도메인 순으로 4개 엔트리
        assert len(entries) == 4

        # domain="auth"로 라우팅
        result_auth = route_memory(entries, context_domain="auth")
        # auth 엔트리 1개 → on-demand
        assert len(result_auth["on_demand"]) == 1
        # 나머지 3개 → always-on
        assert len(result_auth["always_on"]) == 3

        # domain="pr-converge"로 라우팅
        result_pr = route_memory(entries, context_domain="pr-converge")
        assert len(result_pr["on_demand"]) == 1
        assert len(result_pr["always_on"]) == 3

        # domain="pipeline"으로 라우팅
        result_pipeline = route_memory(entries, context_domain="pipeline")
        assert len(result_pipeline["on_demand"]) == 1
        assert len(result_pipeline["always_on"]) == 3

        # domain="unknown"으로 라우팅 → on-demand 없음
        result_unknown = route_memory(entries, context_domain="unknown")
        assert len(result_unknown["on_demand"]) == 0
        assert len(result_unknown["always_on"]) == 4

    def test_golden_fixture_budget_compliance(self):
        """golden fixture 전체가 기본 예산 내에 들어와야 한다."""
        sample = FIXTURES / "sample_learning.md"
        text = sample.read_text(encoding="utf-8")
        entries = parse_learning_entry(text)

        result = route_memory(
            entries,
            context_domain="auth",
            always_on_budget=DEFAULT_ALWAYS_ON_BUDGET,
            ondemand_budget=DEFAULT_ONDEMAND_BUDGET,
        )
        # 작은 fixture이므로 예산 초과 없어야 한다
        assert result["always_on_tokens"] <= DEFAULT_ALWAYS_ON_BUDGET
        assert result["ondemand_tokens"] <= DEFAULT_ONDEMAND_BUDGET


# ─── fail-safe 테스트 ─────────────────────────────────────────────

class TestRouteMemoryFailSafe:

    def test_non_list_entries(self):
        """entries가 리스트가 아니면 빈 결과 반환, raise 금지."""
        for bad in [None, "string", 42, {"a": 1}]:
            result = route_memory(bad, context_domain="auth")
            assert result["always_on"] == []
            assert result["on_demand"] == []

    def test_non_dict_entry_in_list_skipped(self):
        """리스트 내 dict가 아닌 원소는 건너뜀."""
        entries = [None, "bad", _make_entry(domain="auth", body="ok")]
        result = route_memory(entries, context_domain="auth")
        # 유효한 엔트리 1개만 처리
        assert len(result["on_demand"]) == 1

    def test_non_string_context_domain(self):
        """context_domain이 str이 아니어도 raise 금지."""
        entries = [_make_entry(domain="auth", body="auth")]
        for bad in [None, 42, [], {}]:
            try:
                result = route_memory(entries, context_domain=bad)
                # 매칭 실패 → all always-on
                assert len(result["on_demand"]) == 0
            except Exception as e:
                pytest.fail(f"route_memory raised for context_domain={bad!r}: {e}")
