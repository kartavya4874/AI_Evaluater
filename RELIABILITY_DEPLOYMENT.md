# Reliability implementation and deployment

This working tree preserves upload → evaluate → review → verify → export. Workspace & progress handles inputs and execution; Review results shows saved active results and feedback. Changes have been checked offline, not deployed to DGX or benchmarked with real examination papers.

## Implemented safeguards

- MongoDB stores jobs, attempts, preparation operations and upload receipts. The worker supervisor restarts after coordinator errors. Transient transport failures retry with backoff, with at most five job recoveries; exhausted failures remain visible without fabricated marks.
- Publication checks a per-sheet execution token, ownership, expiry, input version and cancellation flag in one conditional update. A recovered worker fences its predecessor. Saved completed attempts can be reconciled after interruption. Manual/pinned results remain protected.
- OCR saves each successful page and renders one missing page at a time. Shared answer keys and question papers reuse extraction within the exam/course. Cache references prevent deleting another sheet's shared entry; explicit clearing changes the selected sheet's cache generation so its next run obtains fresh data.
- Grading extracts a source-backed question rubric, maps the complete student text, grades individual questions, and totals validated scores in Python. Optional rules are checked against the source. Missing, conflicting, unreadable or oversized material requires review. Arbitrary text truncation is not accepted as a grade. Model output truncation retries with larger supported budgets, then becomes review-required.
- One renewable coordinator lease controls a bounded evaluation pool. Administrator concurrency settings are 1–5; start conservatively and measure GPU capacity. The inference gate is shared with synchronous single-sheet calls. Course scheduling avoids simply draining one course before another.
- Folder upload uses an immutable manifest and checksum-verified individual files, avoiding a single multipart request containing thousands of files. Retrying the same folder resumes accepted files. Defaults allow up to 20,000 files, 100 MiB per file and 50 GiB per session; storage must support that capacity. Upload preparation and evaluation across all filtered pages are durable operations.
- Workspace list responses use server pagination and compact summaries. Details and attempt history load on demand. Polling discards stale responses. Active results, queued jobs, review-required failures and preparation progress have distinct UI states.
- Process-local legacy batch execution returns HTTP 410. Earlier saved results remain accessible; synchronous single-sheet evaluation remains available. Docker includes required API modules and a separate worker service; worker readiness is exposed at `/api/ready`.

## User documentation and single-sheet access

The signed-in navigation includes a User guide page at `/guide`, with printing/PDF support. Administrators also have an Evaluate one sheet link to the existing `/evaluate` form. Assigned uploaders can evaluate one sheet through its workspace checkbox; that durable path is recommended for long papers.

## Delete controls

As an administrator, select sheets and use **Delete selected data** in the workspace/results interface:

1. Cache only: keep marks/history and force fresh extraction on the next evaluation.
2. Marks/history only: keep the sheet and valid cached extraction.
3. Cache and marks/history: keep the sheet available for evaluation.
4. Remove sheet: remove its workspace record, jobs, attempts and cache references.

The UI explains each scope and requires typing `DELETE`. Queued, running or management-locked sheets cannot be deleted. Cancel and let active work settle first. **Original uploaded PDFs and audit history are retained**; this is not a full source-file erasure feature. Deleting an entry does not automatically re-evaluate it. Results/verification exports still use only eligible active verified results.

## Startup and deployment

Deploy frontend, API and worker from the same revision. Back up MongoDB and source uploads first. Do not run old and new worker code concurrently against the same database.

For local development, install `backend/requirements.txt` and run `python app.py` from backend; it starts the embedded worker. Run `npm start` from frontend. Gunicorn does not start the embedded worker: run `python worker.py` as a separate supervised service. The example in `systemd/ai-evaluater-worker.service.example` needs installation-specific interpreter and directory paths.

Production requires `APP_ENV=production`, a strong `JWT_SECRET_KEY`, administrator configuration and the existing MongoDB/vLLM connections. Use `backend/.env.example` as a reference without overwriting real credentials. Worker and API must share the same database and source paths. Existing access/course assignments remain enforced.

`compose.yaml` provides API and worker services sharing persistent upload directories. Its API port is bound to loopback for the existing reverse proxy. In containers, `localhost` means that container: configure reachable MongoDB and model URLs, using `host.docker.internal` only when the host service is reachable there. Compose does not create or reconfigure MongoDB, vLLM, Nginx or a frontend host. Docker was unavailable locally, so the image smoke check is included in CI but has not been run here.

Build the frontend for the deployment's existing public path. If using `/ai-evaluater`, set `PUBLIC_URL=/ai-evaluater` and `REACT_APP_BASENAME=/ai-evaluater` for the build. Serve it over HTTPS (or localhost) for browser upload checksum support. Ensure the proxy permits individual uploads up to the configured per-file limit.

Optional `VLLM_TOKENIZE_URL` enables exact request-context preflight. Confirm the existing server supports that endpoint before enabling it. Keep `VLLM_MAX_MODEL_LEN` consistent with the server; raising an application setting cannot increase actual model capacity. `VLLM_MAX_OUTPUT_TOKENS` defaults to 6000, within available context. No GPU/server changes were performed.

New persistence includes `sheets`, `attempts`, `jobs`, `workspace_cache`, `worker_leases`, `preparations`, `upload_sessions`, `upload_parts` and existing access/audit collections. Application startup creates its indexes. MongoDB must be available; production never silently falls back to an in-memory database.

The subsequent route audit is recorded in `audit/API_ROUTE_AUDIT.md`: 52 method/path contracts, frontend URL matching, request validation, permission checks and complete HTTP workflow tests.

## Validation performed

- 126 backend tests passed, including upload restart/idempotency, a 1,200-file manifest, bounded summary reads across 1,000 sheets, page recovery, publication/cancellation races, rubric validation, authorization and durable bulk submission replay.
- 23 frontend tests passed covering workspace/results behavior and management controls. The final production bundle compiled successfully (an existing Browserslist data-age notice remains).
- Run backend checks from `backend`: `python -m unittest test_workspace test_workspace_api test_reliability test_course_processor test_app_security test_multiuser test_worker test_parallel_gate test_scaling test_api_contract test_gemini utils.test_pdf_processor_enhancements` after installing `requirements-test.txt`.
- Run frontend checks from `frontend`: `npm test -- --watchAll=false --runInBand` and `npm run build`.

These database tests use mongomock, and model responses are mocked. They establish regression coverage, not measured production throughput or grading accuracy. The audit report and original probe JSON under `audit/` are historical pre-fix evidence; current regression tests supersede those probes.

## Remaining production validation and limits

Before unattended bulk use, validate representative real papers against teacher-approved scores, including long answers, diagrams, optional sections, blank pages and poor scans. On an isolated real MongoDB/model deployment, test worker termination, API restarts, temporary database/model outages, duplicate submissions and cancellation during grading. Run increasing 100/1,000/several-thousand-sheet batches and record throughput, queue delay, retries, review rate, CPU/RAM/GPU memory and disk usage. Confirm exports contain each eligible student once.

This remains a single coordinator with bounded threads, not a distributed worker fleet. Per-page rendering limits image memory, but model capacity still determines throughput. HTTP read timeouts do not guarantee server-side generation cancellation. Ambiguous rubric extraction intentionally stops for review; it cannot certify academic correctness. Native PDF text extraction may miss visual information on pages with an apparently usable text layer. Large Excel exports still build a workbook in memory.

Source-upload retention, abandoned-upload cleanup and disk quotas across all users need an explicit operational policy. Current session limits and free-space checks are not a global quota. Backups, monitoring and alerting require deployment configuration. No system can promise zero interruption; this implementation is designed to retain accepted work and surface failures safely, with real-server fault and load testing still required.


### Evaluation performance measurements

Independent questions now run with up to `QUESTION_GRADING_WORKERS` threads per
sheet (default 3, capped at 5; set 1 to compare sequential execution). All model
requests still use the shared inference capacity setting. Rubric extraction,
answer mapping, grading prompts, score validation, and optional-question rules
are unchanged. Results are assembled in rubric order.

Completed workspace attempts expose `performance` in their detail record:
`processing_seconds`, `extraction_seconds`, `grading_seconds`, `cache_hits`,
`cache_misses`, and `result_cache_hit`. Processing includes cache/database work
before saving, but excludes queue time and the final persistence/publication.
Extraction includes any OCR and preprocessing cache lookup; grading includes
inference queueing, model work and structured cache lookup. These are wall-clock
measurements, not GPU-only time. Historical attempts have no measurements.

Forced re-evaluation refreshes question scores while retaining cached OCR,
rubric extraction and answer mapping. For a fair speed comparison, use the same
papers and cache conditions, compare workers=1 and workers=3, and report median
and slow-tail processing times. Keep cold-cache and warm-cache runs separate.
Compare accuracy using teacher labels on the same held-out papers; the reported
8% relative baseline is not yet a measured benchmark. Teacher uploads do not
train the model automatically. Restart the backend and any standalone workers
to activate these changes.
