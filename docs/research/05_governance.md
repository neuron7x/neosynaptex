# 05_governance

## Human Impact Assessment

Ця зміна підсилює контроль людини: рішення про merge базується на явних audit-артефактах, а не на неформальному консенсусі.

## Emergency Exit / Rollback

- Видалити додані six-file артефакти та audit-скрипти.
- Відкотити комітом `git revert <sha>`.

## CI Failure Mapping

- PRE-03: missing/empty six-file artifacts.
- MATH-01: відсутній або FAIL `dimension_check_report.json`.
- VAL-01: відсутній доказ red/green у PR.
