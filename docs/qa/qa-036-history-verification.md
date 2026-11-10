# QA-036 — independent history search verification

Date: 2026-11-10. Branch: `codex/delivery-history`.
Profile: `main`, seed: `20261110`.

## Confirmed cause and fix

The original `history_checks()` reproduced `expected=1713, actual=255` for
`/protected/client-delivery-history`, search `LOAD Клиент 00000`, June 2026.
Independent manifest inspection found 255 text matches and 1458 extra phone
matches caused by extracting `00000` from the mixed text query.

The verifier now permits phone matching only when every stripped query character
is an ASCII digit or one of ` +().-`. Text membership remains case insensitive
and includes current cards and historical snapshots. The verifier does not import
the production search helper or use API responses to calculate expectations.
Pagination failures include endpoint, supplied search/date/type/cancellation
filters, page offset, and expected/actual values. Production API and SQL are unchanged.

## Validation

- Ruff formatting and lint: PASS for both changed Python files.
- Regression/load tooling: 71 passed.
- Full `tests/qa`: 157 passed, 16 skipped. Disposable database migration/reset
  tests were not enabled, in accordance with the task restrictions.
- Initial sandbox test attempt encountered existing pytest temporary-file ACL
  errors; the completed runs used elevated access and the required local venv,
  TEMP/TMP, and `--basetemp=.codex-tmp\pytest`.
- LOAD `check -Profile main`: PASS (database identity, marker, revision, API).
- Repeated `verify -Profile main`: FAIL on the separate mismatch below.

## Separate unresolved mismatch

The corrected client endpoint search passed its total, every page's membership
and order, and unique-ID checks (255 results). The next document endpoint check
failed immediately:

```text
/protected/delivery-history filters={'search': 'LOAD Клиент 00000', 'date_from': '2026-06-01', 'date_to': '2026-06-30', 'document_type': 'delivery_route_sheet'} offset=0/total: expected=255, actual=0
```

Recorded verification timestamp (UTC): `2026-11-10T08:19:13.587867+00:00`.
Machine-readable local diagnostic: `.codex-tmp/load/verification.json`.

This result establishes a new discrepancy between independently expected document
membership and the API; its cause has not been investigated or attributed to the
backend. Verification stopped at this failure. Later search cases and remaining
full integrity checks have not completed. No benchmarks or report command were run.
No seeding, reset, initialization, migrations, or PostgreSQL data changes were performed.
The complete load validation is not successful. Further investigation of the
separate document-history mismatch is required before measurements.
