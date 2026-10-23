
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

The evaluator first validates the answer-key rubric, reads the matching course
paper only if that rubric is incomplete, then fills missing allocations from the
administrator scheme. It never divides marks equally by default. Question IDs and
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
