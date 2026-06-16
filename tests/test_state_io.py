"""tests/test_state_io.py — hooks.lib.self_improve.state_io 단위 테스트.

오프라인 전용. 네트워크/LLM 무호출. golden fixture는 tests/fixtures/ 사용.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# 리포지토리 루트를 sys.path에 추가해 `hooks.lib.self_improve` import 가능하게 함.
# (테스트가 어느 cwd에서 실행되든 동작하도록 보장)
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hooks.lib.self_improve import (  # noqa: E402
    SCHEMA_VERSION,
    atomic_write,
    check_schema_version,
    initial_pr_converge_state,
    initial_retro_state,
    load_state,
    load_state_checked,
    now_iso,
    parse_iso,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


# ─── 공개 API import 검증 ──────────────────────────────────────

def test_public_api_importable():
    import hooks.lib.self_improve as pkg

    for name in ("load_state", "atomic_write", "now_iso", "parse_iso"):
        assert hasattr(pkg, name)
    assert pkg.SCHEMA_VERSION == 1


# ─── load_state ────────────────────────────────────────────────

def test_load_state_success(tmp_path):
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"schema_version": 1, "x": 1}), encoding="utf-8")
    state = load_state(p)
    assert state == {"schema_version": 1, "x": 1}


def test_load_state_golden_pr_converge():
    state = load_state(FIXTURES / "pr_converge_state_v1.json")
    assert state is not None
    assert state["schema_version"] == 1
    assert state["status"] == "WORKING"
    assert isinstance(state["processed_comment_ids"], list)


def test_load_state_golden_retro():
    state = load_state(FIXTURES / "retro_state_v1.json")
    assert state is not None
    assert state["schema_version"] == 1
    assert "cumulative" in state


def test_load_state_file_not_found(tmp_path):
    assert load_state(tmp_path / "nope.json") is None


def test_load_state_parse_error(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text("{not valid json", encoding="utf-8")
    assert load_state(p) is None


def test_load_state_non_dict_returns_none(tmp_path):
    p = tmp_path / "list.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    assert load_state(p) is None


def test_load_state_does_not_raise(tmp_path):
    # 디렉토리를 넘겨도 raise 하지 않고 None
    assert load_state(tmp_path) is None


# ─── atomic_write ──────────────────────────────────────────────

def test_atomic_write_creates_file(tmp_path):
    p = tmp_path / "out.json"
    result = atomic_write(p, {"schema_version": 1, "a": 1})
    assert result["ok"] is True
    assert p.exists()
    assert json.loads(p.read_text(encoding="utf-8")) == {"schema_version": 1, "a": 1}


def test_atomic_write_creates_parent_dirs(tmp_path):
    p = tmp_path / "deep" / "nested" / "out.json"
    result = atomic_write(p, {"k": "v"})
    assert result["ok"] is True
    assert p.exists()


def test_atomic_write_overwrites(tmp_path):
    p = tmp_path / "out.json"
    atomic_write(p, {"v": 1})
    atomic_write(p, {"v": 2})
    assert json.loads(p.read_text(encoding="utf-8")) == {"v": 2}


def test_atomic_write_roundtrip(tmp_path):
    p = tmp_path / "rt.json"
    data = initial_pr_converge_state(pr="7", branch="feat/x")
    atomic_write(p, data)
    assert load_state(p) == data


def test_atomic_write_no_tmp_files_left(tmp_path):
    p = tmp_path / "out.json"
    atomic_write(p, {"v": 1})
    leftover = list(tmp_path.glob("*.tmp"))
    assert leftover == []


def test_atomic_write_no_partial_on_failure(tmp_path):
    # 직렬화 불가능한 값 → 실패하되 raise 하지 않고, 손상 파일/임시파일 안 남김
    p = tmp_path / "out.json"
    result = atomic_write(p, {"bad": {1, 2, 3}})  # set은 JSON 직렬화 불가
    assert result["ok"] is False
    assert "error" in result
    assert not p.exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_atomic_write_unicode_preserved(tmp_path):
    p = tmp_path / "u.json"
    atomic_write(p, {"msg": "한글 교훈 ✓"})
    assert load_state(p)["msg"] == "한글 교훈 ✓"


# ─── schema_version guard ──────────────────────────────────────

def test_check_schema_version_ok():
    res = check_schema_version({"schema_version": 1, "x": 1})
    assert res["ok"] is True
    assert res["state"]["x"] == 1


def test_check_schema_version_missing_state():
    res = check_schema_version(None)
    assert res["ok"] is False
    assert res["error"] == "missing_state"


def test_check_schema_version_missing_field():
    res = check_schema_version({"x": 1})
    assert res["ok"] is False
    assert res["error"] == "missing_field"


def test_check_schema_version_mismatch():
    res = check_schema_version({"schema_version": 99})
    assert res["ok"] is False
    assert res["error"] == "version_mismatch"
    assert res["expected"] == 1
    assert res["found"] == 99


def test_check_schema_version_custom_expected():
    res = check_schema_version({"schema_version": 2}, expected=2)
    assert res["ok"] is True


def test_check_schema_version_does_not_raise():
    # 어떤 입력에도 raise 하지 않음
    for bad in (None, {}, {"schema_version": "x"}, {"schema_version": 0}):
        res = check_schema_version(bad)
        assert isinstance(res, dict)
        assert "ok" in res


def test_load_state_checked_success(tmp_path):
    p = tmp_path / "s.json"
    atomic_write(p, initial_retro_state())
    res = load_state_checked(p)
    assert res["ok"] is True


def test_load_state_checked_file_missing(tmp_path):
    res = load_state_checked(tmp_path / "nope.json")
    assert res["ok"] is False
    assert res["error"] == "missing_state"


def test_load_state_checked_version_mismatch(tmp_path):
    p = tmp_path / "old.json"
    atomic_write(p, {"schema_version": 0})
    res = load_state_checked(p)
    assert res["ok"] is False
    assert res["error"] == "version_mismatch"


# ─── 시간 유틸 ─────────────────────────────────────────────────

def test_now_iso_is_utc_parseable():
    s = now_iso()
    dt = parse_iso(s)
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.utcoffset() == timezone.utc.utcoffset(None)


def test_parse_iso_roundtrip():
    s = "2026-06-16T09:30:00+00:00"
    dt = parse_iso(s)
    assert dt == datetime(2026, 6, 16, 9, 30, 0, tzinfo=timezone.utc)


def test_parse_iso_z_suffix():
    dt = parse_iso("2026-06-16T09:30:00Z")
    assert dt == datetime(2026, 6, 16, 9, 30, 0, tzinfo=timezone.utc)


def test_parse_iso_invalid_returns_none():
    assert parse_iso("not a date") is None
    assert parse_iso("") is None


def test_parse_iso_non_string_returns_none():
    assert parse_iso(None) is None
    assert parse_iso(12345) is None


# ─── 초기값 생성 함수 ──────────────────────────────────────────

def test_initial_pr_converge_state_schema():
    s = initial_pr_converge_state(pr="42", branch="feat/x")
    assert s["schema_version"] == SCHEMA_VERSION
    assert s["pr"] == "42"
    assert s["branch"] == "feat/x"
    assert s["processed_comment_ids"] == []
    assert s["fix_attempts"] == {}
    assert s["iterations"] == 0
    assert s["status"] == "WORKING"
    assert s["escalations"] == []
    assert s["learning_entries_appended"] == []
    assert parse_iso(s["last_tick_at"]) is not None


def test_initial_pr_converge_state_keys_match_contract():
    # spec "상태 파일 계약" 키 집합과 정확히 일치
    expected_keys = {
        "schema_version", "pr", "branch", "processed_comment_ids",
        "fix_attempts", "iterations", "status", "last_tick_at",
        "escalations", "learning_entries_appended",
    }
    assert set(initial_pr_converge_state().keys()) == expected_keys


def test_initial_pr_converge_state_defaults_empty():
    s = initial_pr_converge_state()
    assert s["pr"] == ""
    assert s["branch"] == ""


def test_initial_retro_state_schema():
    s = initial_retro_state(last_processed_marker="## 2026-06-16 — x / T-1")
    assert s["schema_version"] == SCHEMA_VERSION
    assert s["last_processed_marker"] == "## 2026-06-16 — x / T-1"
    assert s["cumulative"] == {
        "applied_project": 0,
        "proposed_harness": 0,
        "dropped": 0,
    }
    assert parse_iso(s["last_retro_at"]) is not None


def test_initial_retro_state_keys_match_contract():
    expected_keys = {
        "schema_version", "last_processed_marker", "last_retro_at", "cumulative",
    }
    assert set(initial_retro_state().keys()) == expected_keys


def test_initial_retro_state_default_marker_empty():
    assert initial_retro_state()["last_processed_marker"] == ""


# ─── 초기값이 골든 픽스처와 구조적으로 호환되는지 ─────────────

def test_initial_pr_converge_matches_fixture_keys():
    fixture = load_state(FIXTURES / "pr_converge_state_v1.json")
    assert set(initial_pr_converge_state().keys()) == set(fixture.keys())


def test_initial_retro_matches_fixture_keys():
    fixture = load_state(FIXTURES / "retro_state_v1.json")
    assert set(initial_retro_state().keys()) == set(fixture.keys())
    assert set(initial_retro_state()["cumulative"].keys()) == set(
        fixture["cumulative"].keys()
    )


# ─── stdlib only 검증 (런타임 모듈에 외부 import 없음) ─────────

def test_state_io_imports_stdlib_only():
    src = (
        REPO_ROOT / "hooks" / "lib" / "self_improve" / "state_io.py"
    ).read_text(encoding="utf-8")
    forbidden = ("import requests", "import yaml", "import pydantic", "import aiohttp")
    for f in forbidden:
        assert f not in src
