# API route and request audit — 21 October 2026

## Scope and evidence

This inventory is generated from the registered root Flask application, excluding Flask's static-file handler and automatic HEAD/OPTIONS entries. Every private route is exercised with missing and invalid authentication. Every application route receives an unauthenticated browser preflight. Admin-only routes are tested with a faculty account. All literal frontend Axios API paths/methods are matched against Flask's routing table; retired calls remain only for compatibility with unused older screens.

The additional contract suite exercises valid GET response shapes, malformed JSON, wrong body shapes, incorrect content types, invalid IDs, numeric limits, invalid field types, missing records, storage outages and full mutation chains. Existing authentication, workspace, upload, authorization and concurrency tests supplement it. This is broad route/contract coverage, not an exhaustive proof of every possible field combination or live integration.

## Fixes from this audit

- JSON arrays/scalars/null and malformed bodies are rejected as client errors. Record IDs, limits, account fields, boolean flags and preparation parameters are checked before effects.
- Legacy API exceptions retain HTTP errors; database outages return JSON 503 without connection details. Missing teacher/student deletion targets return 404.
- Scanned single-sheet answer keys and OCR-only uploads use visual fallback with one-page rendering. Answer-key OCR preserves marking instructions. Temporary source files and images are cleaned up on failure. Cache writes are atomic, and answer-key/student caches have separate identities.
- Student statistics now aggregate the saved marks field and exclude failed/unfinished attempts. Manual grade changes retain prior question scores in the audit record and clear stale AI totals so corrected marks can be verified.
- The single-sheet result page now fetches persisted results by ID after refresh; lookup failures no longer claim successful completion. Direct OCR/evaluation browser timeouts allow up to 15 minutes; use the durable workspace for long work. A proxy can impose a shorter limit.
- Async preparation validates exam settings before accepting work; export rejects invalid source filters. Workspace worker status requires an actual lease owner.

## Route inventory

52 explicit method/path contracts. JSON mutation bodies must be objects. Invalid input normally returns 400; missing/invalid credentials 401; unauthorized scope 403; unsupported content type 415.

| Method | Route | Access | Request / response contract |
|---|---|---|---|
| GET | `/` | Public | No input; API metadata |
| GET | `/api/access` | Signed in; scoped response | No body; courses, faculty (admin only), parallelism |
| POST | `/api/access/courses` | Admin | JSON code; optional name, uploaders and reviewers lists of enabled accounts |
| POST | `/api/access/faculty` | Admin | JSON name, email; role admin/faculty and active boolean optional |
| POST | `/api/access/import` | Admin | Multipart file (.xlsx), course_code/name columns; at most 5000 rows |
| POST | `/api/access/settings` | Admin | JSON parallelism integer 1–5 |
| GET | `/api/auth/config` | Public | No input; Google client ID |
| POST | `/api/auth/google` | Public | JSON credential; approved verified Google identity; rate limited |
| POST | `/api/auth/login` | Public | Retired: 410 |
| GET | `/api/auth/me` | Signed in | Bearer token; current enabled account |
| POST | `/api/batch/process-courses` | Admin | Retired: 410; use workspace queue |
| GET | `/api/batch/results` | Admin | No body; grouped earlier batch results |
| GET | `/api/batch/results/<course_code>` | Admin | course_code path; evaluations and statistics |
| GET | `/api/batch/status` | Admin | Retired: 410; use workspace queue |
| POST | `/api/batch/stop` | Admin | Retired: 410; use workspace queue |
| GET | `/api/batch/stream` | Admin | Retired: 410; use workspace queue |
| POST | `/api/batch/upload-folder` | Signed in; ownership/course permission | Legacy multipart files with path_N; at most 1000 PDFs; upload_dir |
| POST | `/api/evaluate-answer` | Admin | Multipart student_file (PDF), model_answer, max_marks 1–1000; optional question, teacher_id, student_id; evaluation with saved ID |
| GET | `/api/evaluations` | Admin | No body; evaluation array |
| DELETE | `/api/evaluations/<evaluation_id>` | Admin | ObjectId evaluation_id; 200/404 |
| GET | `/api/evaluations/<evaluation_id>` | Admin | ObjectId evaluation_id; saved evaluation or 404 |
| PUT | `/api/evaluations/<evaluation_id>/manual` | Admin | ObjectId evaluation_id; JSON finite marks_awarded within maximum, optional feedback |
| GET | `/api/evaluations/recent` | Admin | Optional limit 1–1000 |
| GET | `/api/evaluations/student/<student_id>` | Admin | ObjectId student_id; optional limit 1–1000 |
| GET | `/api/evaluations/teacher/<teacher_id>` | Admin | ObjectId teacher_id; optional limit 1–1000 |
| GET | `/api/health` | Public | No input; database health (200/503) |
| POST | `/api/ocr-only` | Admin | Multipart file (PDF); extracted_text |
| GET | `/api/ready` | Public | No input; database and worker readiness (200/503) |
| GET | `/api/students` | Admin | No body; students array |
| POST | `/api/students` | Admin | JSON name, email; optional roll_number, class; 201 |
| DELETE | `/api/students/<student_id>` | Admin | ObjectId student_id; 200/404 |
| GET | `/api/students/<student_id>` | Admin | ObjectId student_id; 200/404 |
| GET | `/api/students/<student_id>/statistics` | Admin | ObjectId student_id; statistics for completed grades |
| GET | `/api/teachers` | Admin | No body; teachers array |
| POST | `/api/teachers` | Admin | JSON name, email; optional subject; 201 |
| DELETE | `/api/teachers/<teacher_id>` | Admin | ObjectId teacher_id; 200/404 |
| GET | `/api/teachers/<teacher_id>` | Admin | ObjectId teacher_id; 200/404 |
| POST | `/api/upload-model-answer` | Admin | Multipart file (PDF); extracted model_answer |
| POST | `/api/workspace/cancel` | Signed in; ownership/course permission | JSON sheet_ids list 1–1000; queue cancellation/staged cancellation |
| POST | `/api/workspace/evaluate` | Signed in; ownership/course permission | JSON sheet_ids list 1–1000, optional force boolean; 202 jobs |
| POST | `/api/workspace/evaluate-all` | Signed in; ownership/course permission | JSON optional exam_id/course_code, view all/existing/failed, force boolean; 202 operation_id/count; max 20000 matching sheets |
| GET | `/api/workspace/export` | Signed in; ownership/course permission | Query source all/workspace/legacy, exam_id, course_code; verified active results as XLSX |
| POST | `/api/workspace/manage` | Admin | JSON sheet_ids, scope cache/records/both/sheet, confirmation DELETE; rejects active work |
| GET | `/api/workspace/preparations/<operation_id>` | Signed in; ownership/course permission | operation_id owned by caller (or administrator); operation status |
| POST | `/api/workspace/prepare` | Signed in; ownership/course permission | JSON uploaded directory, exam_id, exam_type mst/end_sem, max_marks 1–1000 integer; optional async boolean; sheet_ids or 202 operation_id |
| POST | `/api/workspace/result` | Signed in; ownership/course permission | JSON sheet_id and either marks+reason or attempt_id; reviewer permission; selects/pins result |
| GET | `/api/workspace/sheets` | Signed in; ownership/course permission | Query page>=1, page_size 1–100, exam_id, course_code, view, results_only; paginated sheets/counts |
| GET | `/api/workspace/sheets/<sheet_id>` | Signed in; ownership/course permission | sheet_id; optional offset>=0; active result and 20 history records |
| POST | `/api/workspace/uploads` | Signed in; ownership/course permission | JSON session_id (32 lowercase hex), files [{path,size}]; 1–20000 unique PDFs, max 100 MiB/file |
| PUT | `/api/workspace/uploads/<sid>/<int:index>` | Signed in; ownership/course permission | sid/index path; raw PDF bytes, X-Content-SHA256 header; declared size and checksum must match |
| POST | `/api/workspace/uploads/<sid>/complete` | Signed in; ownership/course permission | sid path; no body; requires all receipts; upload_dir |
| POST | `/api/workspace/verify` | Signed in; ownership/course permission | JSON source workspace/legacy, items list 1–1000; each id plus attempt_id (workspace) or revision (legacy) |

## Final validation

126 backend tests and 23 frontend tests passed. The production frontend build completed successfully. Test logs are in `audit/current-tests.log`, `audit/frontend-tests.log` and `audit/frontend-build.log`. No production deployment or live model evaluation was performed.

## Integration limits

Tests use Flask's request client, mongomock and temporary files; model/Google interactions are mocked. The new contract suite forbids live network calls. Actual Google verification, database indexes/transactions under real contention, Poppler behavior with real documents, model context/JSON capabilities, deployed CORS/proxy limits and restart/load behavior still require staging checks. Legacy result listing is bounded or unpaginated depending on endpoint and is not the primary large-batch interface. The direct single-sheet form remains synchronous and cannot resume an interrupted request; use the workspace for durable execution.

Run `python -m unittest test_api_contract` from backend for the new matrix; CI also runs the existing regression suites. The frontend result-retrieval contract tests are in `frontend/src/pages/Results.test.jsx`.
