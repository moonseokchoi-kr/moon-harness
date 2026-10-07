r"""hooks/lib/kompound_snapshot/verify.py — F8 검증 게이트 3종 (read-only).

설계 SSOT: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md`
(이하 "arch") §6.3.1(`snapshot_set_rule` — 이 모듈 계약의 전제, CRITICAL 대응)
· §5.2.4(3축 원칙) · §3.2(모듈 계약 표 `verify` 행). spec:
`docs/sdd/spec/2026-07-29-kompound-snapshot-hook.md` F8(S-7·S-8·S-9).

## 이 모듈이 하는 일 — 그리고 하지 않는 일

박제 실행((i) raw 복사) 후, 카탈로그 커밋((ii)) 전에 3개 게이트를 판정한다:

1. **링크 무결성** — registry가 가리키는 **스냅샷 집합 한정** wikilink가 실재
   raw 파일(``10. Raw Sources/**/<raw 이름>.md``)을 가리키는가.
2. **양방향 카운트 일치** — registry 스냅샷 링크 집합과 raw 스냅샷 파일
   집합의 **양방향 차집합이 정확히 0**인가(단순 개수 비교 아님).
3. **raw 레이아웃** — 스냅샷 raw가 전부 ``10. Raw Sources/<NN. 유형>/<도메인>/``
   바로 아래에 있고 도메인이 볼트 10종 중 하나인가(v1의 "flat 유지" 게이트를
   v2 2단 분류 규칙으로 대체 — 2026-10-07).

## v2 볼트 (2026-10-07)

모집단과 링크는 **raw 이름**(파일 stem, ``YYYY-MM-DD-<slug>``) 단위로 비교한다.
스냅샷 규칙 판정은 날짜 접두를 뗀 ``<slug>``에 적용한다. registry 링크는
Obsidian wikilink(``[[<raw 이름>]]``, 표 안에서는 ``[[<raw 이름>\|✓]]``)이며
frontmatter(``source:`` 목록)는 링크 추출 대상에서 제외한다 — 표 본문이 SSOT다.

이 모듈은 **판정만** 한다 — `verify_failed`(exit 50)가 T2 삭제를 차단해야
하는지는 정책이고, 그 정책은 이미 `report.blocks_deletion()`이 계산한다
(arch A-5, §5.2.4 축 3: 카탈로그 정합성 실패는 raw 소실과 무관하므로 경고
후 통과). 이 모듈은 그 정책을 재유도하지 않는다. 커밋 여부 결정·롤백도 이
모듈의 책임이 아니다(T-10 `apply.py`).

## `snapshot_set_rule` — 모집단의 정의 (arch §6.3.1, CRITICAL 대응)

SDD 스냅샷 집합 = slug가 ``<P>-<feature>-<kind>``인 raw (v1: ``raw/<P>-<feature>-<kind>.md``, v2: ``10. Raw Sources/**/YYYY-MM-DD-<P>-<feature>-<kind>.md``) where

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

from hooks.lib.kompound_snapshot import vault

__all__ = [
    "KINDS",
    "GATE_LINK_INTEGRITY",
    "GATE_BIDIRECTIONAL_COUNT",
    "GATE_FLAT_STRUCTURE",
    "GATE_RAW_LAYOUT",
    "snapshot_population_paths",
    "check_raw_layout",
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
GATE_RAW_LAYOUT = "raw_layout"
# v1 이름 호환 별칭 — v2에서 "flat 유지" 게이트는 "raw 레이아웃" 게이트로 대체됐다.
GATE_FLAT_STRUCTURE = GATE_RAW_LAYOUT

_REGISTRY_RELATIVE = vault.REGISTRY_RELATIVE

# Obsidian wikilink 대상 추출: `[[target]]`, `[[target|alias]]`, 표 안의
# `[[target\|alias]]`, `[[target#heading]]`. 대상만 캡처한다.
_WIKILINK_RE = re.compile(r"\[\[([^\]\|\\#\n]+)")


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


def _slug_filename(stem: str) -> str:
    return f"{vault.slug_of(stem)}.md"


def snapshot_population_paths(raw_root: PathLike, prefixes: Sequence[str]) -> Dict[str, Path]:
    """``{raw 이름(stem): Path}`` — `raw_root`(보통 ``<볼트>/10. Raw Sources``)
    아래 **재귀** 전체에서 slug가 `snapshot_set_rule`을 만족하는 raw. 날짜 접두
    (``YYYY-MM-DD-``)가 있는 파일만 대상이다(볼트 raw 명명 규칙). read-only."""
    out: Dict[str, Path] = {}
    try:
        root = Path(raw_root)
        if not root.is_dir():
            return out
        for path in _iter_md(root):
            stem = path.stem
            if stem == vault.slug_of(stem):
                continue  # 날짜 접두 없음 — 규칙 밖
            if matches_snapshot_rule(_slug_filename(stem), prefixes):
                out.setdefault(stem, path)
    except OSError:
        return out
    return out


def _iter_md(root: Path):
    for path in sorted(root.rglob("*.md")):
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        yield path


def snapshot_population(raw_root: PathLike, prefixes: Sequence[str]) -> Set[str]:
    """스냅샷 raw 이름(stem) 집합. :func:`snapshot_population_paths`의 키."""
    return set(snapshot_population_paths(raw_root, prefixes))


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    m = re.search(r"^---[ \t]*$", text[3:], re.MULTILINE)
    if not m:
        return text
    return text[3 + m.end():]


def extract_registry_raw_links(registry_text: str) -> Set[str]:
    """registry **본문**(frontmatter 제외)의 wikilink 대상 전부(스냅샷 집합 한정
    아님). 예외를 던지지 않는다."""
    try:
        if not registry_text:
            return set()
        body = _strip_frontmatter(registry_text)
        return {t.strip() for t in _WIKILINK_RE.findall(body) if t.strip()}
    except (TypeError, re.error):
        return set()


def snapshot_registry_links(registry_text: str, prefixes: Sequence[str]) -> Set[str]:
    """registry wikilink 중 날짜 접두가 있고 slug가 `snapshot_set_rule`을 만족하는
    raw 이름만(arch F8 게이트 (1)(2)의 검사 범위 한정 — S-8). 실재 여부는 보지
    않는다(게이트 (1)의 일)."""
    out: Set[str] = set()
    for name in extract_registry_raw_links(registry_text):
        if name == vault.slug_of(name):
            continue
        if matches_snapshot_rule(_slug_filename(name), prefixes):
            out.add(name)
    return out


def _all_raw_stems(kompound_repo: PathLike) -> Set[str]:
    return {p.stem for p in vault.iter_raw_files(kompound_repo)}


def _read_registry_text(kompound_repo: PathLike) -> str:
    """`<kompound_repo>/20. Wiki/24. Maps/SDD Spec Registry.md`를 읽는다. 부재/오류 시
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
        existing = _all_raw_stems(repo)

        broken = sorted(name for name in links if name not in existing)
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
        files = snapshot_population(repo / vault.RAW_ROOT, rule["prefixes"])

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


def check_raw_layout(
    kompound_repo: PathLike, prefix_map: Optional[Mapping[str, Optional[str]]] = None
) -> Dict[str, Any]:
    """게이트 (3) — 스냅샷 raw가 전부 ``10. Raw Sources/<유형>/<도메인>/<파일>``
    깊이에 있고 ``<도메인>``이 `vault.DOMAINS` 중 하나인가. `prefix_map`이 없으면
    기본 프리픽스(config.DEFAULT_PREFIX_MAP 값)로 모집단을 잡는다. 예외를 던지지
    않는다."""
    try:
        repo = Path(kompound_repo)
        if prefix_map is None:
            from hooks.lib.kompound_snapshot.config import DEFAULT_PREFIX_MAP

            prefix_map = DEFAULT_PREFIX_MAP
        rule = snapshot_set_rule(prefix_map)
        raw_root = repo / vault.RAW_ROOT
        offending: List[str] = []
        for stem, path in sorted(snapshot_population_paths(raw_root, rule["prefixes"]).items()):
            try:
                rel = path.relative_to(raw_root)
            except ValueError:
                offending.append(stem)
                continue
            if len(rel.parts) != 3 or rel.parts[1] not in vault.DOMAINS:
                offending.append(str(rel))
        ok = not offending
        detail = (
            "스냅샷 raw 전부 10. Raw Sources/<유형>/<도메인>/ 아래"
            if ok
            else f"레이아웃 위반(유형/도메인 2단 밖 또는 미등록 도메인): {offending}"
        )
        return {"gate": GATE_RAW_LAYOUT, "ok": ok, "detail": detail}
    except Exception as exc:  # noqa: BLE001 - fail-safe
        return {
            "gate": GATE_RAW_LAYOUT,
            "ok": False,
            "detail": f"내부 오류: {exc}",
        }


# v1 이름 호환 별칭.
check_flat_structure = check_raw_layout


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
        check_raw_layout(kompound_repo, prefix_map),
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
                {"gate": GATE_RAW_LAYOUT, "ok": False, "detail": f"내부 오류: {exc}"},
            ],
        }
