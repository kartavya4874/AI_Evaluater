# Agreed evaluation reliability and management requirements

Recorded 13 October 2026. This document preserves decisions from the project chat. Recording these requirements does not authorize deleting existing data or changing production services.

Implementation update, 14 October 2026: the durable workspace, attempt history, re-evaluation, scoped management, Excel exports, validation and recovery safeguards are implemented locally. See RELIABILITY_DEPLOYMENT.md for startup, legacy migration, verification, and explicitly documented remaining limitations. Production deployment and real DGX grading verification have not been performed.

## Evaluation attempts and duplicate detection

- Identify a sheet using its file content hash, student roll number, course, and examination identity. Separate exams must not share completion state merely because the course and roll number match.
- Check database records and valid caches before processing. Reuse requires matching answer key, marking scheme, model, prompt version, and other relevant grading inputs.
- Provide an Already evaluated tab showing previous results, dates, and statuses, with Use existing result and Re-evaluate actions.
- Re-evaluation creates a separate persisted attempt; it does not overwrite history. One sheet can have multiple attempts/results.
- Maintain one active result for reports and statistics, defaulting to the latest successful attempt. A failed re-evaluation preserves the previous successful active result and remains visible in history.
- Count a sheet once in course totals and statistics, not once per attempt.

## Failure handling and reliable processing

- Distinguish pending, processing, completed, and failed attempts explicitly across service responses, persistence, caches, progress, and UI.
- Technical failures have no academic marks and show Evaluation failed — Retry. A genuine zero after valid grading remains a valid completed result.
- Validate structured grading responses before marking an attempt completed. Never cache a technical failure as a successful evaluation.
- Resume only valid completed evaluations for the same examination and relevant grading inputs. Failed attempts remain retryable.
- Retrying must persist the new attempt even when an older record exists for the course and student.
- Prevent concurrent duplicate work for the same sheet/attempt.
- Determine pending work before extracting the answer key. Reusing an existing result must avoid unnecessary OCR and grading.
- Use consistent timeouts, bounded retries, and useful request diagnostics. Respect the served model's context limit without silently truncating answers.

## Frontend/backend state management

- Implement coordinated state management between frontend and backend; current process-local batch globals and event queues are insufficient for reliable synchronization.
- Backend persisted job/attempt state is authoritative. The frontend must recover current state after refresh, reconnect, or navigation, and accurately show progress, completion, failure, retry, and cancellation.
- Support deployment with multiple backend workers without depending on a particular worker's memory.
- Keep displayed state consistent after re-evaluation and database/cache management actions.

## Database and cache management

- Provide UI controls to inspect and manage stored evaluation data and cache for an individual sheet or all sheets, with course/batch scope where useful.
- Support deletion of database records, cache, or both with explicit scope and clear consequences. Define handling of attempt history and active results.
- Clearing cache alone must not misleadingly imply that database completion state was reset; provide an explicit re-evaluation path.
- Cache entries may be shared by multiple sheets: deletion/invalidation must account for shared ownership and active processing.
- Bulk/destructive actions require deliberate user action and confirmation in the application. These requirements are not an instruction to delete current data.

## Excel result exports

- Provide a downloadable Excel results file for each course.
- Provide a combined workbook containing course results; default to one worksheet per course.
- Exclude feedback and OCR content from all result exports. Also exclude full student/model-answer text, prompts, and technical error payloads.
- Export one active result per sheet rather than duplicate rows for historical attempts.
- Proposed concise columns: course, examination, student roll number, maximum marks, awarded marks, percentage, grade, and evaluation status. Failed/pending attempts must not appear as zero academic marks.
- Exact column labels and combined-workbook layout can be refined during implementation; the confirmed requirement is per-course and combined Excel downloads without feedback or OCR content.

## Production constraints and existing evidence

- Development is on Windows; production runs on DGX. Windows uses the public HTTPS vLLM endpoint; DGX can use localhost:8000/v1.
- Do not modify the production vLLM service/model/context/memory, MongoDB server configuration, Nginx, or firewall as part of application fixes.
- The observed failure chain was timeout -> zero-valued error fallback -> cached/labelled completed -> warning flags omitted from MongoDB -> incorrectly skipped on resume.
- Earlier saved errors used 300 seconds/five attempts; later logs show 600 seconds and current local code uses three attempts. The exact origin of historical failures is not yet verified.
- Existing invalid records need a deliberate recovery/migration plan. No database drop or cleanup is authorized by this document.

## Verification required before calling the work complete

User requirement added October 15, 2026: Results must expose full saved feedback and question-level detail where available. Reviewers can verify one result or select multiple results for verification. Verification must persist with reviewer/time and be tied to the reviewed result; changed marks or a new attempt require fresh verification. Excel downloads must contain only verified results, still excluding feedback and OCR content. Older saved results can be explicitly verified after review without rerunning grading.

Cover successful positive and zero grades, timeout/retry exhaustion, invalid output, failure persistence and cache exclusion, legacy failed records, duplicate detection, re-evaluation history/active result selection, separate exam attempts, synchronized state across workers/reconnects, scoped deletion, and exports without excluded content. Verify one real student end to end before a full batch; HTTP 200 alone is not proof of valid grading.
