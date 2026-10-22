# Evaluation data flow

## Navigation and responsibilities

- `/evaluate/single`: single evaluation; its saved record lives in `evaluations`.
- `/evaluate/batch`: resumable folder uploads, preparation, queueing and progress.
- `/results`: combined review of saved evaluations and active workspace attempts.
  `/batch-results` redirects here.
- `/manage-results`: administrator inventory of both stores, including failed and
  ungraded sheets; deletion and cache management belong here.
- `/teacher-comparison`: independent teacher labels and AI snapshots; uploading
  labels neither replaces scores nor verifies or trains the model.

## Persistent identities

Workspace sheets live in `sheets`, work state in `jobs`, and grading history in
`attempts`. The sheet's active attempt is authoritative only when completed and
its configuration matches the sheet. Previous single/batch results remain in
`evaluations`. Combined rows use `(source, id)` to avoid cross-store collisions.
The API joins these stores for display; it does not migrate or duplicate records.

Review uses `/api/workspace/results`; management uses `/api/workspace/inventory`.
They intentionally have different totals when sheets have no active result.
Workspace detail comes from `/api/workspace/sheets/<id>`; saved-result detail
comes from `/api/workspace/results/legacy/<id>`.

## State transitions

A successful grade becomes an active unverified result. Verification checks the
active attempt ID or saved-result revision before changing verification state.
Only verified marks enter the workbook. A manual revision creates/replaces the
reviewable result and requires verification again. Clearing workspace marks
removes attempts but retains the sheet for further evaluation and management.
Deleting the sheet removes it from inventory. Original uploaded files are retained.

Review reloads after mutations, including partial verification failures. Empty
out-of-range result pages move back to a valid page. A result removed between
listing and opening details produces an explicit refresh message. Management can
open failed/ungraded sheets to inspect their processing error and attempt history.
Storage failures show an error instead of pretending that the database is empty.

## Regression coverage

`test_workspace_api.py` exercises revision, verification, export, clearing marks
and deleting the sheet as one lifecycle. Other backend suites cover authorization,
route contracts, teacher comparisons, uploads and multiuser isolation. Frontend
suites cover mixed-store selections, partial failures, failed-sheet details,
outside-click dismissal, route redirects and unavailable addresses.

These tests use isolated fixtures; they do not establish the state of a running
production database or benchmark live inference accuracy/speed.
