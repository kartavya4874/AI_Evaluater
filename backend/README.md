
# Backend configuration and recovery

## Administrator marking schemes

In Courses & accounts, load a course and examination type (MST or End Sem).
Upload an optional default question paper and enter fallback allocations in the
form, or import `.xlsx` columns in this order:
`question_id, max_marks, group, choose, selection`.
Leave optional-group fields blank for compulsory questions. Group members share
the same marks, choose count, and selection (`exact`, `best`, or `first`).
Excel imports are previews; Save marking scheme persists the validated form.
All totals must equal the configured examination maximum after choice rules.

Before student OCR, the evaluator prepares one shared marking scheme for each
course, examination session, and exam type. It first validates the answer-key
rubric, reads the matching course paper only if that rubric is incomplete, then
fills missing allocations from the administrator scheme. Extracted key answers
are retained while adding question-paper marks. Other sheets wait for this course
preparation; they do not start student OCR before the scheme passes. An unresolved
scheme blocks the course without repeating AI work for every sheet. Source changes,
administrator scheme revisions, or explicitly cleared cache trigger a new check.
Temporary connection failures are retried rather than cached as an invalid scheme.
It never divides marks equally by default. Question IDs and
exam maximum must match, and conflicting source allocations remain review errors.
Saved attempts record the allocation source and administrator scheme revision.
Existing results are retained; retry affected sheets after updating a scheme.
Sheets with no marks and a `needs_review` state appear in Review results.

Set deployment values in `backend/.env` or the process environment. Environment
variables take precedence over `.env`. See `.env.example` for documented defaults;
do not edit application code to tune a deployment. Restart the backend after
changing settings.

AI connection/upload, response, and tokenizer timeouts are configured separately
with `VLLM_CONNECT_TIMEOUT_SECONDS`, `VLLM_TIMEOUT_SECONDS`, and
`VLLM_TOKENIZE_TIMEOUT_SECONDS`. `VLLM_REQUEST_ATTEMPTS` and
`VLLM_RETRY_MIN_SECONDS` / `VLLM_RETRY_MAX_SECONDS` control transient request retries.

MongoDB selection, connection, socket and pool-wait timeouts use
`MONGO_SERVER_SELECTION_TIMEOUT_MS`, `MONGO_CONNECT_TIMEOUT_MS`,
`MONGO_SOCKET_TIMEOUT_MS`, and `MONGO_WAIT_QUEUE_TIMEOUT_MS`. These values are in
milliseconds; AI timeouts and `WORKER_RECOVERY_SECONDS` are in seconds.
All must be positive integers; retry maximum must not be below retry minimum.

Temporary service outages retain durable jobs and saved page work. Request retries
are bounded; the durable worker continues recovery after transient infrastructure
failures. A stop request must reach MongoDB before it can be confirmed. Never report
success or substitute empty/zero marks when storage or AI requests fail.

Run regression checks before loading changes:

```powershell
cd backend
.\venv\Scripts\python.exe -m unittest discover -p "test_*.py"
```


Stabilization run policy (2026-10-23): course preparation is persisted in MongoDB
`course_runs`. One sheet prepares the shared scheme; other sheets remain queued
without taking worker slots. Student OCR starts only after that prerequisite is
ready. Marks follow answer key, then the course question paper, then an explicit
administrator scheme for that course and exam type. No numeric fallback is invented.

`EVALUATION_RUN_TIMEOUT_SECONDS` (default 3600) is persisted at submission, includes
queue time, and survives recovery. `EVALUATION_MAX_RETRIES` (default 5) limits durable
retries and worker recoveries. Exhausted runs pause until an explicit user retry;
existing OCR is retained. `AI_JSON_REPAIR_ATTEMPTS`, `AI_TRUNCATION_ATTEMPTS`, and
`AI_INITIAL_OUTPUT_TOKENS` bound generation work. See `.env.example` for settings.
Pin `VLLM_MODEL_REVISION` and `VLLM_TOKENIZER_REVISION` to your deployed artifacts.
Cache identities include these values and a fingerprint of grading/OCR source code.
Changing the fingerprint deliberately recomputes old cached work on the next run.

Deadlines are checked between stages and constrain capacity waits and HTTP socket
timeouts. They cannot forcibly interrupt an already executing native PDF operation,
a slow-drip HTTP response, or guarantee cancellation of GPU work on the vLLM server.
A confirmed Stop prevents publication; its current blocking request can still take
time to return. Process isolation/server cancellation is a later hardening step.

Read `../docs/STABILIZATION_RELEASE_2026-10-23.md` before DGX rollout. This release
has local failure-recovery tests; it is not a teacher-calibrated accuracy benchmark.
