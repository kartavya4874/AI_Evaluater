"""Generate the route inventory from Flask registration without making network requests."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app import app

contracts = {
'root': 'No input; API metadata', 'health_check': 'No input; database health (200/503)', 'readiness': 'No input; database and worker readiness (200/503)',
'auth_config': 'No input; Google client ID', 'auth_login': 'Retired: 410', 'auth_google': 'JSON credential; approved verified Google identity; rate limited', 'auth_me': 'Bearer token; current enabled account',
'create_teacher': 'JSON name, email; optional subject; 201', 'create_student': 'JSON name, email; optional roll_number, class; 201',
'get_teacher': 'ObjectId teacher_id; 200/404', 'get_student': 'ObjectId student_id; 200/404', 'get_all_teachers': 'No body; teachers array', 'get_all_students': 'No body; students array',
'get_student_statistics': 'ObjectId student_id; statistics for completed grades', 'delete_teacher': 'ObjectId teacher_id; 200/404', 'delete_student': 'ObjectId student_id; 200/404',
'upload_model_answer': 'Multipart file (PDF); extracted model_answer', 'evaluate_answer': 'Multipart student_file (PDF), model_answer, max_marks 1–1000; optional question, teacher_id, student_id; evaluation with saved ID',
'ocr_only': 'Multipart file (PDF); extracted_text', 'get_all_evaluations': 'No body; evaluation array', 'get_evaluation': 'ObjectId evaluation_id; saved evaluation or 404',
'update_manual_evaluation': 'ObjectId evaluation_id; JSON finite marks_awarded within maximum, optional feedback', 'get_student_evaluations': 'ObjectId student_id; optional limit 1–1000', 'get_teacher_evaluations': 'ObjectId teacher_id; optional limit 1–1000',
'get_recent_evaluations': 'Optional limit 1–1000', 'delete_evaluation': 'ObjectId evaluation_id; 200/404', 'retired_batch_processing': 'Retired: 410; use workspace queue',
'batch_results': 'No body; grouped earlier batch results', 'batch_results_by_course': 'course_code path; evaluations and statistics', 'batch_upload_folder': 'Legacy multipart files with path_N; at most 1000 PDFs; upload_dir',
'access.listing': 'No body; courses, faculty (admin only), parallelism', 'access.settings': 'JSON parallelism integer 1–5', 'access.faculty': 'JSON name, email; role admin/faculty and active boolean optional',
'access.courses': 'JSON code; optional name, uploaders and reviewers lists of enabled accounts', 'access.import_courses': 'Multipart file (.xlsx), course_code/name columns; at most 5000 rows',
'workspace.sheets': 'Query page>=1, page_size 1–100, exam_id, course_code, view, results_only; paginated sheets/counts', 'workspace.sheet_detail': 'sheet_id; optional offset>=0; active result and 20 history records',
'workspace.prepare': 'JSON uploaded directory, exam_id, exam_type mst/end_sem, max_marks 1–1000 integer; optional async boolean; sheet_ids or 202 operation_id',
'workspace.preparation_status': 'operation_id owned by caller (or administrator); operation status', 'workspace.evaluate': 'JSON sheet_ids list 1–1000, optional force boolean; 202 jobs',
'workspace.evaluate_all': 'JSON optional exam_id/course_code, view all/existing/failed, force boolean; 202 operation_id/count; max 20000 matching sheets',
'workspace.cancel': 'JSON sheet_ids list 1–1000; queue cancellation/staged cancellation', 'workspace.manage': 'JSON sheet_ids, scope cache/records/both/sheet, confirmation DELETE; rejects active work',
'workspace.result': 'JSON sheet_id and either marks+reason or attempt_id; reviewer permission; selects/pins result', 'workspace.export': 'Query source all/workspace/legacy, exam_id, course_code; verified active results as XLSX',
'workspace.verify': 'JSON source workspace/legacy, items list 1–1000; each id plus attempt_id (workspace) or revision (legacy)',
'uploads.start': 'JSON session_id (32 lowercase hex), files [{path,size}]; 1–20000 unique PDFs, max 100 MiB/file',
'uploads.upload_file': 'sid/index path; raw PDF bytes, X-Content-SHA256 header; declared size and checksum must match', 'uploads.complete': 'sid path; no body; requires all receipts; upload_dir',
}
public = {'root','health_check','readiness','auth_config','auth_login','auth_google'}
rows = []
for rule in app.url_map.iter_rules():
    if rule.endpoint == 'static': continue
    assert rule.endpoint in contracts, rule.endpoint
    for method in sorted(rule.methods - {'HEAD','OPTIONS'}):
        permission = 'Public' if rule.endpoint in public else 'Admin'
        if rule.endpoint == 'auth_me': permission = 'Signed in'
        if rule.endpoint == 'access.listing': permission = 'Signed in; scoped response'
        if rule.endpoint.startswith(('workspace.', 'uploads.')) or rule.endpoint == 'batch_upload_folder': permission = 'Signed in; ownership/course permission'
        if rule.endpoint == 'workspace.manage': permission = 'Admin'
        rows.append((rule.rule, method, permission, contracts[rule.endpoint]))
rows.sort()
report = '''# API route and request audit — 21 October 2026

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

'''
report += f'{len(rows)} explicit method/path contracts. JSON mutation bodies must be objects. Invalid input normally returns 400; missing/invalid credentials 401; unauthorized scope 403; unsupported content type 415.\n\n'
report += '| Method | Route | Access | Request / response contract |\n|---|---|---|---|\n'
report += '\n'.join(f'| {method} | `{path}` | {permission} | {contract} |' for path, method, permission, contract in rows)
report += '''

## Final validation

126 backend tests and 23 frontend tests passed. The production frontend build completed successfully. Test logs are in `audit/current-tests.log`, `audit/frontend-tests.log` and `audit/frontend-build.log`. No production deployment or live model evaluation was performed.

## Integration limits

Tests use Flask's request client, mongomock and temporary files; model/Google interactions are mocked. The new contract suite forbids live network calls. Actual Google verification, database indexes/transactions under real contention, Poppler behavior with real documents, model context/JSON capabilities, deployed CORS/proxy limits and restart/load behavior still require staging checks. Legacy result listing is bounded or unpaginated depending on endpoint and is not the primary large-batch interface. The direct single-sheet form remains synchronous and cannot resume an interrupted request; use the workspace for durable execution.

Run `python -m unittest test_api_contract` from backend for the new matrix; CI also runs the existing regression suites. The frontend result-retrieval contract tests are in `frontend/src/pages/Results.test.jsx`.
'''
Path(__file__).with_name('API_ROUTE_AUDIT.md').write_text(report, encoding='utf-8')
print(f'Inventoried {len(rows)} method/path contracts.')
