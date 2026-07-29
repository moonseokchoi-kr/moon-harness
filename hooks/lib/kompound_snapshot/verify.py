"""hooks/lib/kompound_snapshot/verify.py — F8 검증 게이트 3종 (read-only).

설계 SSOT: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md`
(이하 "arch") §6.3.1(`snapshot_set_rule` — 이 모듈 계약의 전제, CRITICAL 대응)
· §5.2.4(3축 원칙) · §3.2(모듈 계약 표 `verify` 행). spec:
`docs/sdd/spec/2026-07-29-kompound-snapshot-hook.md` F8(S-7·S-8·S-9).

## 이 모듈이 하는 일 — 그리고 하지 않는 일

박제 실행((i) raw 복사) 후, 카탈로그 커밋((ii)) 전에 3개 게이트를 판정한다:

1. **링크 무결성** — registry가 가리키는 **스냅샷 집합 한정** 링크가 실재
   파일을 가리키는가.
2. **양방향 카운트 일치** — registry 스냅샷 링크 집합과 raw 스냅샷 파일
   집합의 **양방향 차집합이 정확히 0**인가(단순 개수 비교 아님).
3. **flat 유지** — `raw/` 하위에 `assets/` 외 디렉토리가 없는가.

이 모듈은 **판정만** 한다 — `verify_failed`(exit 50)가 T2 삭제를 차단해야
하는지는 정책이고, 그 정책은 이미 `report.blocks_deletion()`이 계산한다
(arch A-5, §5.2.4 축 3: 카탈로그 정합성 실패는 raw 소실과 무관하므로 경고
후 통과). 이 모듈은 그 정책을 재유도하지 않는다. 커밋 여부 결정·롤백도 이
모듈의 책임이 아니다(T-10 `apply.py`).

## `snapshot_set_rule` — 모집단의 정의 (arch §6.3.1, CRITICAL 대응)

SDD 스냅샷 집합 = ``raw/<P>-<feature>-<kind>.md`` where

- ``P`` ∈ ``prefix_map.values()`` (설정 병합 후 유효 프리픽스 집합, `null`
  제거)
- ``kind`` ∈ ``{spec, arch, ui, api, context, result}``

실측(marvelous_kompound, 2026-07-29): kind 접미사만으로 세면 122건이 잡히지만
registry가 링크하는 SDD 문서는 117건이다. 초과 5건은 사람이 독립적으로
`/ingest`한 주제 문서가 우연히 kind 접미사로 끝난 것 — 프리픽스로 한정하면
정확히 117 = 117, 양방향 차집합 0으로 통과한다. **이 규칙 밖의 `raw/*.md`는
읽지도 쓰지도 않는다** — 규칙 밖 파일은 이 훅이 만든 것이 아니므로 게이트의
모집단에 들 이유가 없다(F12와 정의 일관).

## Fail-safe 규약

이 패키지 공통 규약을 따른다 — **예외를 밖으로 던지지 않는다.** 개별 게이트
함수는 내부 오류를 `{"gate": ..., "ok": False, "detail": "내부 오류: ..."}`
로 흡수한다(F11 "조용한 통과 금지" — 판정 불가를 조용히 통과로 두지 않고
실패로 드러낸다). 네트워크 호출 없음, git 상태를 보지 않는다(파일시스템만
읽는다 — dirty/divergence 판정은 `git_state.py`의 책임).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, Union

__all__ = [
    "KINDS",
    "GATE_LINK_INTEGRITY",
    "GATE_BIDIRECTIONAL_COUNT",
    "GATE_FLAT_STRUCTURE",
    "effective_prefixes",
    "matches_snapshot_rule",
    "snapshot_set_rule",
    "snapshot_population",
    "extract_registry_raw_links",
    "snapshot_registry_links",
    "check_link_integrity",
    "check_bidirectional_count",
    "check_flat_structure",
    "should_run_gates",
    "run_gates",
    "build_verify_report",
]

PathLike = Union[str, "Path"]

# ── F8 게이트(2)의 kind 집합 (arch §6.3.1 — canonical 6종, scan.py의 입력측
# 별칭(specs/development 등)과는 무관하다. raw 파일명은 naming.py가 이미
# canonical 값으로 정규화한 뒤라서 이 6종만 나타난다) ───────────────────────
KINDS: Tuple[str, ...] = ("spec", "arch", "ui", "api", "context", "result")

# ── 게이트 이름 (T-10이 참조하는 상수 — 문자열 리터럴 중복 방지) ───────────
GATE_LINK_INTEGRITY = "link_integrity"
GATE_BIDIRECTIONAL_COUNT = "bidirectional_count"
GATE_FLAT_STRUCTURE = "flat_structure"

_ALLOWED_RAW_SUBDIR = "assets"
_REGISTRY_RELATIVE = Path("wiki") / "sdd-spec-registry.md"

# registry 마크다운 링크 중 `../raw/<name>.md` 형태만 추출한다. 중첩 경로
# (`sub/dir-x.md`)가 캡처돼도 `matches_snapshot_rule`이 자연히 걸러낸다 —
# 유효 프리픽스에 `/`가 포함된 값이 없는 한 매칭될 수 없다.
_RAW_LINK_RE = re.compile(r"\]\(\.\./raw/([^)\s]+\.md)\)")


# ── snapshot_set_rule 계약 (arch §6.3.1) ────────────────────────────────────


def effective_prefixes(prefix_map: Optional[Mapping[str, Optional[str]]]) -> Tuple[str, ...]:
    """`prefix_map.values()`에서 `null`을 제거한, 정렬된 유일 프리픽스 튜플.

    `config.resolve_config()`이 반환하는 `prefix_map`은 이미 병합 시점에
    `null` 키를 제거한 상태이지만(F12 경로), 이 함수는 방어적으로도 다시
    한 번 `None`을 걸러낸다 — 호출자가 병합 전 원시 dict를 넘기는 경우까지
    안전하게 처리하기 위해서다. 예외를 던지지 않는다(`prefix_map`이
    `None`이거나 매핑이 아니어도 빈 튜플).
    """
    try:
        if not prefix_map:
            return ()
        return tuple(sorted({value for value in prefix_map.values() if value}))
    except (AttributeError, TypeError):
        return ()


def matches_snapshot_rule(filename: str, prefixes: Sequence[str]) -> bool:
    """`filename`(예: ``acme-widget-onboarding-spec.md``)이 `snapshot_set_rule`을
    만족하는가 — ``<P>-<feature>-<kind>.md`` where `P` ∈ `prefixes`, `kind` ∈
    `KINDS`, `feature`는 비어있지 않다.

    순수 함수. 예외를 던지지 않는다.
    """
    try:
        if not isinstance(filename, str) or not filename.endswith(".md"):
            return False
        stem = filename[: -len(".md")]
        for kind in KINDS:
            suffix = f"-{kind}"
            if not stem.endswith(suffix):
                continue
            remainder = stem[: -len(suffix)]
            for prefix in prefixes:
                head = f"{prefix}-"
                if remainder.startswith(head) and len(remainder) > len(head):
                    return True
        return False
    except (AttributeError, TypeError):
        return False


def snapshot_set_rule(prefix_map: Optional[Mapping[str, Optional[str]]]) -> Dict[str, Any]:
    """`snapshot_set_rule`(arch §6.3.1)을 재사용 가능한 형태로 캡슐화한다.

    반환: ``{"prefixes": Tuple[str, ...], "kinds": KINDS,
    "matches": Callable[[str], bool]}``. 게이트 함수들은 이 dict의
    ``matches``로 파일명 판정을 위임한다 — 규칙을 각자 재구현하지 않는다.
    `prefix_map`을 인자로 주입받는다(하드코딩 금지 — task 지시).
    """
    prefixes = effective_prefixes(prefix_map)

    def matches(filename: str) -> bool:
        return matches_snapshot_rule(filename, prefixes)

    return {"prefixes": prefixes, "kinds": KINDS, "matches": matches}


# ── 모집단 수집 (raw/ 실제 파일 · registry 링크) ────────────────────────────


def snapshot_population(raw_dir: PathLike, prefixes: Sequence[str]) -> Set[str]:
    """`raw_dir`(보통 `<kompound_repo>/raw`) 직속 자식 중 `snapshot_set_rule`을
    만족하는 파일명 집합을 반환한다(하위 디렉토리는 재귀하지 않는다 — 규칙
    자체가 flat 구조를 전제한다). read-only, 예외를 던지지 않는다.
    """
    population: Set[str] = set()
    try:
        directory = Path(raw_dir)
        if not directory.is_dir():
            return population
        for entry in directory.iterdir():
            try:
                if not entry.is_file():
                    continue
            except OSError:
                continue
            if matches_snapshot_rule(entry.name, prefixes):
                population.add(entry.name)
    except OSError:
        return population
    return population


def extract_registry_raw_links(registry_text: str) -> Set[str]:
    """registry 텍스트에서 ``[...](../raw/<name>.md)`` 형태 링크의 `<name>.md`
    전부를 추출한다(스냅샷 집합 한정 아님 — 전체 raw 링크). 예외를 던지지
    않는다.
    """
    try:
        if not registry_text:
            return set()
        return set(_RAW_LINK_RE.findall(registry_text))
    except (TypeError, re.error):
        return set()


def snapshot_registry_links(registry_text: str, prefixes: Sequence[str]) -> Set[str]:
    """registry가 가리키는 raw 링크 중 `snapshot_set_rule`을 만족하는 것만
    반환한다(arch F8 게이트 (1)(2)의 검사 범위 한정 — S-8). 링크가 가리키는
    파일이 실재하는지는 여기서 확인하지 않는다(그건 게이트 (1)의 일).
    """
    all_links = extract_registry_raw_links(registry_text)
    return {name for name in all_links if matches_snapshot_rule(name, prefixes)}


def _read_registry_text(kompound_repo: PathLike) -> str:
    """`<kompound_repo>/wiki/sdd-spec-registry.md`를 읽는다. 부재/오류 시
    빈 문자열(예외를 던지지 않는다 — read-only 게이트의 입력 실패는 각
    게이트가 스스로 "실패"로 보고한다)."""
    try:
        return (Path(kompound_repo) / _REGISTRY_RELATIVE).read_text(encoding="utf-8")
    except OSError:
        return ""


# ── 게이트 (1)(2)(3) ─────────────────────────────────────────────────────────


def check_link_integrity(
    kompound_repo: PathLike, prefix_map: Optional[Mapping[str, Optional[str]]]
) -> Dict[str, Any]:
    """게이트 (1) — registry의 **스냅샷 집합 한정** 링크가 실재 파일을
    가리키는가(arch S-8 — 스냅샷 집합 밖 링크가 깨져도 이 게이트는 실패하지
    않는다, C-1과 동일 구조의 함정 회피). 예외를 던지지 않는다.
    """
    try:
        repo = Path(kompound_repo)
        rule = snapshot_set_rule(prefix_map)
        registry_text = _read_registry_text(repo)
        links = snapshot_registry_links(registry_text, rule["prefixes"])
        raw_dir = repo / "raw"

        broken = sorted(name for name in links if not (raw_dir / name).is_file())
        ok = not broken
        detail = (
            f"prefixes={list(rule['prefixes'])}; 스냅샷 링크 {len(links)}건 중 "
            f"파일 부재 {len(broken)}건"
        )
        if broken:
            detail += f": {broken}"
        return {"gate": GATE_LINK_INTEGRITY, "ok": ok, "detail": detail}
    except Exception as exc:  # noqa: BLE001 - fail-safe, 판정 실패를 조용히 통과시키지 않는다
        return {
            "gate": GATE_LINK_INTEGRITY,
            "ok": False,
            "detail": f"내부 오류: {exc}",
        }


def check_bidirectional_count(
    kompound_repo: PathLike, prefix_map: Optional[Mapping[str, Optional[str]]]
) -> Dict[str, Any]:
    """게이트 (2) — registry 스냅샷 링크 집합과 raw 스냅샷 파일 집합의
    **양방향 차집합이 정확히 0**인가(spec S-7 — 단순 개수 비교가 아니다.
    누락 1건 + 유령 링크 1건이 상쇄돼 통과하는 것을 막는다). 예외를 던지지
    않는다.
    """
    try:
        repo = Path(kompound_repo)
        rule = snapshot_set_rule(prefix_map)
        registry_text = _read_registry_text(repo)
        links = snapshot_registry_links(registry_text, rule["prefixes"])
        files = snapshot_population(repo / "raw", rule["prefixes"])

        missing_links = sorted(files - links)  # raw엔 있지만 registry에 링크 없음(=이 훅의 존재 이유)
        ghost_links = sorted(links - files)  # registry엔 있지만 raw에 파일 없음
        ok = not missing_links and not ghost_links

        detail = (
            f"prefixes={list(rule['prefixes'])}; registry 스냅샷 링크 {len(links)}건, "
            f"raw 스냅샷 파일 {len(files)}건. "
            f"누락(파일→링크 없음) {len(missing_links)}건"
        )
        if missing_links:
            detail += f" {missing_links}"
        detail += f", 유령(링크→파일 없음) {len(ghost_links)}건"
        if ghost_links:
            detail += f" {ghost_links}"

        return {"gate": GATE_BIDIRECTIONAL_COUNT, "ok": ok, "detail": detail}
    except Exception as exc:  # noqa: BLE001 - fail-safe
        return {
            "gate": GATE_BIDIRECTIONAL_COUNT,
            "ok": False,
            "detail": f"내부 오류: {exc}",
        }


def check_flat_structure(kompound_repo: PathLike) -> Dict[str, Any]:
    """게이트 (3) — `raw/` 하위에 `assets/` 외 디렉토리가 없는가. `prefix_map`이
    필요 없다(순수 구조 검사). 예외를 던지지 않는다.
    """
    try:
        raw_dir = Path(kompound_repo) / "raw"
        offending: List[str] = []
        if raw_dir.is_dir():
            for entry in raw_dir.iterdir():
                try:
                    if entry.is_dir() and entry.name != _ALLOWED_RAW_SUBDIR:
                        offending.append(entry.name)
                except OSError:
                    continue
        offending.sort()
        ok = not offending
        detail = (
            "raw/ 하위 서브디렉토리 없음(assets/ 제외 허용)"
            if ok
            else f"raw/ 하위에 허용되지 않은 서브디렉토리: {offending}"
        )
        return {"gate": GATE_FLAT_STRUCTURE, "ok": ok, "detail": detail}
    except Exception as exc:  # noqa: BLE001 - fail-safe
        return {
            "gate": GATE_FLAT_STRUCTURE,
            "ok": False,
            "detail": f"내부 오류: {exc}",
        }


# ── 실행 여부 판단 / 실행 (분리 — T-10이 스킵을 결정할 수 있도록) ───────────


def should_run_gates(raw_stage: Optional[Mapping[str, Any]]) -> bool:
    """박제된 raw가 0건(신규 0 + 갱신 0)이면 게이트를 실행할 필요가 없다(spec
    F8 "박제 0건일 때 3개 게이트를 실행하지 않는다 — 갱신 대상이 없으므로
    게이트 스킵은 실패가 아니라 정상 종료다").

    이 함수는 **판단만** 한다 — 실제로 게이트를 부르지 않는 결정은 호출자
    (T-10 `apply.py`)가 한다. `raw_stage`는 `report._default_raw_stage()`와
    같은 모양(``{"new": [...], "updated": [...]}``)을 기대하지만, `None`이거나
    형상이 다르면 보수적으로 `True`(게이트 실행)를 반환한다 — "판정 불가 →
    안전 확인 쪽으로 실행"이 F11 fail-safe 정신과 일치한다.
    """
    try:
        if raw_stage is None:
            return True
        new = raw_stage.get("new") or []
        updated = raw_stage.get("updated") or []
        return bool(len(new) > 0 or len(updated) > 0)
    except (AttributeError, TypeError):
        return True


def run_gates(
    kompound_repo: PathLike, prefix_map: Optional[Mapping[str, Optional[str]]]
) -> List[Dict[str, Any]]:
    """게이트 (1)(2)(3)을 순서대로 실행해 arch §3.2 계약
    ``[{"gate", "ok", "detail"}] × 3``을 반환한다.

    항상 3개 게이트를 실행한다 — "박제 0건이면 스킵"의 판단은 이 함수의
    책임이 아니다(`should_run_gates()` 참조, T-10이 호출 전에 판단한다).
    이 함수 자체는 예외를 던지지 않는다(개별 게이트가 이미 자체 fail-safe).
    """
    return [
        check_link_integrity(kompound_repo, prefix_map),
        check_bidirectional_count(kompound_repo, prefix_map),
        check_flat_structure(kompound_repo),
    ]


def build_verify_report(
    kompound_repo: PathLike, prefix_map: Optional[Mapping[str, Optional[str]]]
) -> Dict[str, Any]:
    """게이트 3종 실행 결과 + **사용된 프리픽스 목록**을 함께 노출하는 조립
    리포트(arch §6.3.1 마지막 항목 — "경계가 보이지 않으면 카운트 불일치를
    진단할 수 없다").

    arch §3.2의 원 계약(``[{"gate","ok","detail"}] × 3``)은 ``gates`` 키
    아래 그대로 보존한다 — T-10은 이 함수 대신 `run_gates()`를 직접 써도
    무방하다(원 계약과 100% 동일). 이 함수는 그 위에 진단용 ``prefixes``
    필드만 얹는 편의 조립일 뿐이다. 예외를 던지지 않는다.
    """
    try:
        prefixes = list(effective_prefixes(prefix_map))
        gates = run_gates(kompound_repo, prefix_map)
        return {"prefixes": prefixes, "gates": gates}
    except Exception as exc:  # noqa: BLE001 - fail-safe
        return {
            "prefixes": [],
            "gates": [
                {"gate": GATE_LINK_INTEGRITY, "ok": False, "detail": f"내부 오류: {exc}"},
                {"gate": GATE_BIDIRECTIONAL_COUNT, "ok": False, "detail": f"내부 오류: {exc}"},
                {"gate": GATE_FLAT_STRUCTURE, "ok": False, "detail": f"내부 오류: {exc}"},
            ],
        }
