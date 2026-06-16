# LEARNING.md — sample golden fixture

This preamble appears before the first entry header and must be ignored by the
parser.

## 2026-06-10 — auth-refresh / T-12
<!-- tags: domain=auth, stage=구현, provenance_repo=moon-harness -->

Refresh tokens were being rotated twice on concurrent requests. Single-flight
the refresh call.

## 2026-06-11 — pr-feedback-dedup / T-7
<!-- tags: domain=pr-converge, stage=pr-converge, provenance_repo=marvelous -->

Reviewer left the same nit on three files; dedup by signal key before
re-dispatching the engineer.

## 2026-06-12 — quick-note / T-3

This entry has NO tag metablock. The parser must still produce an entry with
tags=None and never raise.

## 2026-06-13 — multiline-pipeline / T-9
<!-- tags: domain=pipeline, stage=구현, provenance_repo=moon-harness -->

This is a multi-line entry body.

It spans several paragraphs.

- bullet one
- bullet two

Final line of the multiline entry.
