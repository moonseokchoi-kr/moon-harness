# LEARNING.md — 마커 경계 케이스 골든 픽스처

이 preamble은 파서가 무시해야 한다.

## 2026-06-10 — auth-refresh / T-12
<!-- tags: domain=auth, stage=구현, provenance_repo=moon-harness -->

Refresh tokens were being rotated twice on concurrent requests.
Single-flight the refresh call.

## 2026-06-11 — pr-feedback-dedup / T-7
<!-- tags: domain=pr-converge, stage=pr-converge, provenance_repo=marvelous -->

Reviewer left the same nit on three files; dedup by signal key before
re-dispatching the engineer.

## 2026-06-12 — type-narrowing / T-15
<!-- tags: domain=typing, stage=구현, provenance_repo=clo3d -->

TypeScript type narrowing was lost after an await boundary.
Use explicit type assertion after awaiting when narrowing is required.

## 2026-06-13 — multiline-pipeline / T-9
<!-- tags: domain=pipeline, stage=구현, provenance_repo=moon-harness -->

Multi-line entry body spanning several paragraphs.

- bullet one
- bullet two

Final line of the multiline entry.

## 2026-06-14 — last-entry / T-99
<!-- tags: domain=auth, stage=pr-converge, provenance_repo=marvelous -->

This is the LAST entry in the file. Used to verify that when
last_marker points here, get_new_entries returns an empty list.
