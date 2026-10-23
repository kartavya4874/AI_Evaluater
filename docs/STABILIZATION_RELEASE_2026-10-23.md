# First stabilization release

This release implements the first priority from the production readiness audit. It
keeps Flask, the existing worker and MongoDB; it does not introduce a new queue
service. It is implemented locally and has not been deployed to DGX.

## Changed behavior

- Course marking preparation is a durable MongoDB prerequisite. A single admitted
  sheet prepares it. Other sheets with the same inputs wait in the queue, leaving
  worker capacity available for other courses. Ready and blocked outcomes survive
  worker replacement. Fenced writes prevent an old preparation from becoming ready.
- Answer key allocations take priority. Missing allocations use the corresponding
  question paper, then an administrator scheme for the course and MST/end semester.
  Student OCR does not start before this validation. No marks are guessed.
- A run has a persisted deadline and finite durable retry/recovery budget. Automatic
  recovery retains its deadline and successful OCR pages. Exhaustion becomes
  `paused`, with an explicit retry action and visible Batch guidance.
- Invalid JSON/truncated model generation is a technical failure, distinct from a
  source requiring marking review. Technical course failures can be explicitly
  retried without changing the source.
- Numeric allocations must agree with a single explicit allocation in their source
  quote. Question identifiers must match whole identifiers rather than substrings.
  Ambiguous tables remain a review case; this conservative validator does not claim
  to understand every examination layout.
- Answer mapping rejects contradictory explicit question labels. A missing mapped
  answer requires an explicit unanswered indication across all excerpts before zero
  is awarded. The application's `Page 1:` header is accepted as administrative text.
  Explicit retries of failed/reviewed work regenerate answer mapping.
- Cache keys include a pipeline source fingerprint and configured model/tokenizer
  revisions. Existing successful results remain available; a new evaluation uses
  the current pipeline cache namespace.

## Configuration

All new limits use validated environment settings in `backend/.env.example`:

| Setting | Default | Meaning |
| --- | ---: | --- |
| `EVALUATION_RUN_TIMEOUT_SECONDS` | 3600 | Persisted submission-to-finish budget, including queue time |
| `EVALUATION_MAX_RETRIES` | 5 | Durable retries/recoveries before pausing |
| `AI_JSON_REPAIR_ATTEMPTS` | 2 | Total JSON generation attempts per structured call |
| `AI_TRUNCATION_ATTEMPTS` | 3 | Maximum generations with increasing output budgets |
| `AI_INITIAL_OUTPUT_TOKENS` | 1500 | Starting output budget, capped by model configuration |
| `VLLM_MODEL_REVISION` | empty | Operator-supplied deployed model revision |
| `VLLM_TOKENIZER_REVISION` | empty | Operator-supplied deployed tokenizer revision |

Use measured runtimes and queue sizes when choosing the run budget. Increasing a
timeout alone does not resolve a model that repeatedly produces invalid output.
Do not change request concurrency until the DGX model workload is measured.

## Validation and limits

Regression coverage includes durable course admission, preparation before student
OCR, cross-course scheduling, old-worker fencing, retry exhaustion, explicit retry
with retained OCR, cancellation precedence, preserved deadlines, shared HTTP budget,
numeric grounding, identifier collisions, page headers, wrong mapping and uncertain
zero awards. The standalone audit probes now reject all three reproduced weaknesses.

These tests use synthetic text, mock inference and an in-memory MongoDB substitute.
Local validation: 205 backend tests passed, 17 Batch UI tests passed, and the frontend
production build completed successfully.
They do not measure real MongoDB failover, live DGX throughput, handwritten OCR
quality, or whether awarded marks agree with a teacher. Deadlines constrain stage
boundaries, capacity waits and socket timeouts; native PDF calls and slow-drip HTTP
responses still need process-level isolation for a strict wall-clock guarantee.
Stop prevents publishing a cancelled result but cannot guarantee immediate GPU
abort. Span-based mapping and teacher-calibrated grading remain subsequent work.

## DGX rollout

1. Preserve the deployed code, environment and database backup. Run this release
   against a staging database and a small copied course first.
2. Deploy backend sources and rebuilt frontend together. Merge the new environment
   settings into the existing environment; preserve credentials and service paths.
   Pin the model/tokenizer revisions. No database reset is required.
3. Restart the existing backend and `ai-evaluater-worker` services after deployment.
   An application-only update does not require an nginx restart when its
   configuration is unchanged. Local implementation has restarted no DGX services.
4. Check worker startup, one course preparation for multiple same-course sheets,
   no student OCR for a blocked scheme, successful evaluation, Stop, and explicit
   retry. Verify real logs contain request durations and bounded recovery outcomes.
5. Compare a representative teacher-marked set by question: OCR omissions, mapping
   errors, absolute mark error, bias and optional-question handling. Keep human
   verification enabled until acceptance thresholds are agreed and met.

Legacy queued jobs without a stored deadline derive it from their original creation
time. Old stuck work can therefore pause after rollout rather than restart an
unbounded loop. Explicit retry creates a fresh budget and retains reusable work.
