import React, { useCallback, useEffect, useRef, useState } from 'react';
import api, { uploadBatchFolder } from '../services/api';
import { useAuth } from '../context/AuthContext';
import ResultDetails from '../components/ResultDetails';
import './Workspace.css';

export function stageLabel(stage) {
  const labels = { retry_wait: 'Temporary issue — automatic retry scheduled', needs_review: 'Source or marking scheme needs review', queued: 'Waiting for evaluation', starting: 'Starting evaluation', checking_cache: 'Checking saved work', grading: 'AI is marking the answer sheet', saving: 'Saving marks and feedback', completed: 'Evaluation complete', error: 'Failed — retry required', cancelled: 'Cancelled', ready: 'Ready to evaluate', extracting_answer_key: 'Reading the answer key', extracting_student: 'Reading the student answer sheet', extracting_question_paper: 'Reading the question paper' };
  const completedPage = (stage || '').match(/^extracted_(answer_key|student|question_paper)_page_(\d+)_of_(\d+)$/);
  if (completedPage) return `${{ answer_key: 'Answer key', student: 'Student answer sheet', question_paper: 'Question paper' }[completedPage[1]]}: ${completedPage[2]} of ${completedPage[3]} pages read`;
  const page = (stage || '').match(/^extracting_(answer_key|student|question_paper)_page_(\d+)_of_(\d+)$/);
  if (page) return `${labels['extracting_' + page[1]]} — page ${page[2]} of ${page[3]}`;
  return labels[stage] || (stage ? stage.replace(/_/g, ' ') : labels.ready);
}

export default function Workspace({ resultsOnly = false }) {
  const { user } = useAuth();
  const admin = user?.role === 'admin';
  const [sheets, setSheets] = useState([]);
  const [courses, setCourses] = useState([]);
  const [selected, setSelected] = useState([]);
  const [exam, setExam] = useState('');
  const [type, setType] = useState('end_sem');
  const [marks, setMarks] = useState(100);
  const [showValidation, setShowValidation] = useState(false);
  const [files, setFiles] = useState(null);
  const [correctionMode, setCorrectionMode] = useState(false);
  const uploadPanel = useRef(null);
  const [busy, setBusy] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(null);
  const [capabilities, setCapabilities] = useState(null);
  const [phase, setPhase] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [connectionError, setConnectionError] = useState('');
  const [workerOnline, setWorkerOnline] = useState(true);
  const [parallelism, setParallelism] = useState(null);
  const [requestedParallelism, setRequestedParallelism] = useState('');
  const [capacity, setCapacity] = useState(null);
  const [updated, setUpdated] = useState(null);
  const [courseFilter, setCourseFilter] = useState('');
  const [filter, setFilter] = useState('');
  const [tab, setTab] = useState('all');
  const [detail, setDetail] = useState(null);
  const [history, setHistory] = useState(null);
  const [scope, setScope] = useState('cache');
  const [page, setPage] = useState(1);
  const [pageInfo, setPageInfo] = useState(null);
  const [preparations, setPreparations] = useState([]);
  const [historySheet, setHistorySheet] = useState(null);
  const [historyOffset, setHistoryOffset] = useState(0);
  const requestVersion = useRef({ value: 0 });
  const accessCache = useRef({ at: 0, data: null });
  const allowed = (code, field) => admin || courses.some(c => c._id === code && c[field]?.includes(user?.email));
  const canUpload = admin || courses.some(c => c.uploaders?.includes(user?.email));
  const refresh = useCallback(async () => {
    const version = ++requestVersion.current.value;
    const response = await api.get('/workspace/sheets', { params: { page, page_size: 50,
      exam_id: filter || undefined, course_code: courseFilter || undefined, view: tab, results_only: resultsOnly } });
    if (!accessCache.current.data || Date.now() - accessCache.current.at > 60000) {
      accessCache.current = { at: Date.now(), data: (await api.get('/access')).data };
    }
    if (version !== requestVersion.current.value) return;
    const access = accessCache.current.data;
    setSheets(response.data.sheets); setCourses(access.courses); setParallelism(access.parallelism ?? 3);
    setPageInfo(response.data.total === undefined ? null : response.data);
    setPreparations(response.data.preparations || []);
    setCapabilities(response.data.capabilities || {});
    setCapacity(response.data.worker_capacity ?? null);
    setWorkerOnline(response.data.worker_online); setUpdated(new Date()); setConnectionError('');
  }, [page, filter, courseFilter, tab, resultsOnly]);
  useEffect(() => {
    let stopped = false; let timer;
    const versionState = requestVersion.current;
    const poll = async () => {
      try { await refresh(); }
      catch (e) { if (!stopped) setConnectionError(`Unable to load workspace results: ${e.response?.data?.error || e.message}. Retrying…`); }
      if (!stopped) timer = setTimeout(poll, 3000);
    };
    poll(); return () => { stopped = true; clearTimeout(timer); versionState.value++; };
  }, [refresh]);
  const action = async operation => {
    setBusy(true); setError(''); setNotice('');
    try { await operation(); await refresh(); }
    catch (e) { setError(e.response?.data?.error || e.message); }
    finally { setBusy(false); setPhase(''); setUploadProgress(null); }
  };
  const missing = { exam: !exam.trim() ? 'Enter an examination / session ID.' : exam.trim().length > 120 ? 'Use no more than 120 characters.' : '', marks: !Number.isInteger(Number(marks)) || Number(marks) < 1 || Number(marks) > 1000 ? 'Enter whole-number maximum marks from 1 to 1000.' : '', files: !files?.length ? 'Select a course folder containing the PDFs.' : '' };
  const prepare = () => {
    setShowValidation(true);
    if (Object.values(missing).some(Boolean)) {
      setError('Complete the required fields highlighted in red before uploading.');
      return;
    }
    return action(async () => {
    if (!exam.trim() || !files?.length) throw new Error('Enter an examination/session ID and select a course folder.');
    setPhase('Uploading PDFs. Keep this page open until the upload finishes.');
    setUploadProgress(0);
    const uploaded = await uploadBatchFolder(files, value => setUploadProgress(Number.isFinite(value) ? value : null));
    setUploadProgress(null);
    setPhase('Validating course folders and preparing answer sheets…');
    accessCache.current.at = 0;
    const response = await api.post('/workspace/prepare', { directory: uploaded.upload_dir, exam_id: exam, exam_type: type, max_marks: Number(marks), async: true });
    if (response.data.operation_id) {
      setNotice('Upload saved. Folder preparation is queued and will continue if you leave this page. Prepared sheets appear automatically below.');
      return;
    }
    setSelected([]);
    setNotice('Folder validated. Select sheets on each page, then click Evaluate / use existing to start.');
    });
  };
  const evaluate = force => action(async () => {
    await api.post('/workspace/evaluate', { sheet_ids: selected, force });
    setNotice(force ? 'New attempts queued. Previous results remain available.' : 'Pending sheets queued; existing successful results reused.');
  });
  const verify = rows => action(async () => {
    await api.post('/workspace/verify', { source: 'workspace', items: rows.map(s => ({ id: s._id, attempt_id: s.active._id })) });
    setNotice('Selected results verified. They are now eligible for Excel export.'); setDetail(null);
  });
  const download = course => action(async () => {
    const response = await api.get('/workspace/export', { params: { course_code: course || undefined, exam_id: filter || undefined, source: 'workspace' }, responseType: 'blob' });
    const url = URL.createObjectURL(response.data); const anchor = document.createElement('a');
    anchor.href = url; anchor.download = course ? `${course}-results.xlsx` : 'combined-results.xlsx';
    anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  useEffect(() => { setSelected([]); setTab('all'); setDetail(null); setHistory(null); setHistorySheet(null); }, [resultsOnly]);
  const visible = sheets.filter(s => (!resultsOnly || !!s.active) && (!filter || s.exam_id === filter) && (!courseFilter || s.course_code === courseFilter) && (tab === 'all' || (tab === 'pending' ? s.active && !s.active.verified : tab === 'verified' ? s.active?.verified : tab === 'existing' ? !!s.active : ['error', 'needs_review'].includes(s.job?.state))));
  const selectedSet = new Set(selected);
  const selectedRows = visible.filter(s => selectedSet.has(s._id));
  const canRun = selectedRows.length > 0 && selectedRows.every(s => allowed(s.course_code, 'uploaders'));
  const canStop = sheet => ['queued', 'processing'].includes(sheet.job?.state) && !sheet.job.cancel_requested && allowed(sheet.course_code, 'uploaders');
  const stoppableSelected = selectedRows.filter(canStop);
  const stopSheets = rows => action(async () => {
    const ids = rows.filter(canStop).map(s => s._id);
    if (!ids.length) return;
    await api.post('/workspace/cancel', { sheet_ids: ids });
    setNotice(`Stop requested for ${ids.length} sheet${ids.length === 1 ? '' : 's'}. Queued work is cancelled; running work stops after its current request returns.`);
  });
  const stopControl = sheet => allowed(sheet.course_code, 'uploaders') && ['queued', 'processing'].includes(sheet.job?.state) &&
    <button className="stop-button" aria-label={`${sheet.job.cancel_requested ? 'Stopping' : 'Stop'} ${sheet.roll_number}`} disabled={busy || !canStop(sheet)} onClick={() => stopSheets([sheet])}>{sheet.job.cancel_requested ? 'Stopping…' : 'Stop'}</button>;
  const selectedBusy = selectedRows.some(s => ['queued', 'processing', 'managing'].includes(s.job?.state));
  const deleteDescription = { cache: 'Clear cached OCR and AI responses for the selected sheets. Saved marks and history remain.', records: 'Delete all marks, verification and attempt history for the selected sheets. Cached work and sheet records remain.', both: 'Delete all marks, verification, history and cached work. Sheet records remain for evaluation.', sheet: 'Remove the selected sheet records, marks, verification, history and cached work.' }[scope];
  const canReview = selectedRows.length > 0 && selectedRows.every(s => allowed(s.course_code, 'reviewers') && s.active);
  const counts = { ready: 0, queued: 0, processing: 0, review: 0, verified: 0, error: 0, cancelled: 0, needs_review: 0 };
  visible.forEach(s => {
    if (['queued', 'processing', 'error', 'cancelled', 'needs_review'].includes(s.job?.state)) counts[s.job.state]++;
    else if (s.active) counts[s.active.verified ? 'verified' : 'review']++;
    else counts.ready++;
  });
  if (pageInfo?.counts) Object.assign(counts, { ready: 0, queued: 0, processing: 0, review: 0, verified: 0, error: 0, cancelled: 0, needs_review: 0 }, pageInfo.counts);
  const viewTotal = pageInfo?.total ?? visible.length;
  const successful = counts.review + counts.verified;
  const activity = (resultsOnly ? [] : visible).flatMap(sheet => {
    const job = sheet.job;
    if (!job) return [];
    const events = job.events?.length ? job.events : [{ stage: job.stage || job.state, at: job.updated_at || job.created_at, message: job.error }];
    return events.map((event, index) => ({ ...event, course: sheet.course_code, student: sheet.roll_number, key: `${sheet._id}-${job.attempt_id}-${index}` }));
  }).sort((a, b) => new Date(b.at || 0) - new Date(a.at || 0)).slice(0, 100);
  const selectedHistory = historySheet || sheets.find(s => s._id === history);
  const showDetails = async (sheet, asHistory = false, offset = 0) => {
    try {
      const response = await api.get(`/workspace/sheets/${sheet._id}`, { params: { offset } });
      const full = response.data.sheet || sheet;
      if (asHistory) { setHistory(sheet._id); setHistorySheet(full); setHistoryOffset(offset); }
      else setDetail(full);
    } catch (e) { setError(e.response?.data?.error || e.message); }
  };
  useEffect(() => { setPage(1); setSelected([]); setHistorySheet(null); }, [filter, courseFilter, tab, resultsOnly]);
  return <main className="workspace">
    <h1>{resultsOnly ? 'Review results' : 'Batch evaluation'}</h1>
    <p>{resultsOnly ? 'Inspect saved marks and feedback, verify results, and export verified marks.' : admin ? 'Manage examinations and track every course from upload to verified results.' : 'Your assigned courses and responsibilities. Progress is saved even when you leave this page.'}</p>
    {error && <p role="alert" className="workspace-error">{error} <button onClick={() => setError('')}>Dismiss error</button></p>}
    {admin && capabilities && !capabilities.admin_all_courses && <p role="alert" className="workspace-error">The backend is running an older version without the administrator course-access fix. Restart the backend to load the update, then retry the selected sheets.</p>}
    {connectionError && <p role="status" className="workspace-error">{connectionError}</p>}
    {notice && <p role="status">{notice}</p>}{phase && <div role="status"><p>{phase}</p><progress aria-label="Upload and preparation progress" max="100" value={uploadProgress ?? undefined} />{uploadProgress !== null && <span> {uploadProgress}% transferred</span>}</div>}
    {!resultsOnly && !connectionError && !workerOnline && <p role="status" className="workspace-error">Processing worker is reconnecting or offline. Saved jobs and completed OCR pages are retained. The worker retries automatically while the backend is running; refresh after the connection returns.</p>}
    {!resultsOnly && <><section className="workspace-panel" aria-label="Live progress"><h2>What is happening now</h2>
      <p>{!updated ? 'Connecting to your workspace…' : connectionError ? 'Updates paused — these counts may be out of date.' : `Updated ${updated.toLocaleTimeString()} · refreshes every 3 seconds`}</p>
      <p>{workerOnline && capacity ? `Up to ${capacity} sheets can run in parallel across all courses. Additional sheets wait in the queue.` : ''}</p>
      {admin && <div className="workspace-toolbar">
        <label>Parallel evaluations<select aria-label="Parallel evaluations" value={requestedParallelism || String(parallelism || 3)} onChange={e => setRequestedParallelism(e.target.value)} disabled={busy || parallelism === null}>
          {[1, 2, 3, 4, 5].map(n => <option key={n} value={n}>{n} {n === 1 ? 'sheet at a time' : 'sheets at a time'}</option>)}
        </select></label>
        <button disabled={busy || !requestedParallelism || Number(requestedParallelism) === parallelism} onClick={() => action(async () => {
          await api.post('/access/settings', { parallelism: Number(requestedParallelism) });
          accessCache.current.at = 0; setRequestedParallelism(''); setNotice('Parallel evaluation limit saved. Running work will finish; new work uses the updated limit.');
        })}>Save parallel limit</button>
        <span>Saved limit: {parallelism ?? '…'} / 5. Shared across all users. Lowering the limit lets current work finish.</span>
      </div>}
      <div className="progress-cards">{Object.entries({ ready: 'Ready to evaluate', queued: 'Waiting in queue', processing: 'Evaluating now', review: 'Awaiting review', verified: 'Verified', error: 'Needs retry', cancelled: 'Cancelled', needs_review: 'Source needs review' }).map(([key, label]) => <div key={key}><strong>{counts[key]}</strong><span>{label}</span></div>)}</div>
      <p>{counts.needs_review ? 'Some sheets need source or marking-scheme review. Check their current work messages below and correct the source before retrying.' : counts.processing ? 'Evaluation is running. See the current step for each student below.' : counts.queued ? (workerOnline ? 'Sheets are waiting for the processing worker.' : 'Saved jobs are waiting for the worker to reconnect. If this persists after connectivity returns, check the backend worker.') : counts.review ? 'Results are ready. Open Review results to inspect feedback and verify marks for export.' : counts.error ? `${counts.error} sheets failed. Nothing is running. Select failed sheets and click Evaluate / use existing to retry. AI request errors may require configuration changes before retrying.` : counts.ready ? 'Select ready sheets below, then click Evaluate / use existing.' : 'Upload a course folder, then select sheets to start evaluation.'}</p>
      <div className="overall-progress"><label htmlFor="evaluation-progress">Evaluation completion for this view: {successful} / {viewTotal} sheets successful</label>
        <progress id="evaluation-progress" max={viewTotal || 1} value={successful} />
        <p>{viewTotal ? Math.round(successful / viewTotal * 100) : 0}% successful · {counts.processing} running · {counts.queued} queued · {counts.error} failed · {counts.cancelled} cancelled</p>
        <small>Failures are not counted as successful completion. Counts follow the selected course, examination and tab.</small>
      </div>
      {visible.filter(s => s.job?.state === 'processing').map(s => <article className="running-sheet" key={s._id}>
        <strong>{s.course_code} / {s.roll_number}</strong> {stopControl(s)}<p>{s.job.cancel_requested ? 'Stopping — waiting for the current request to return' : stageLabel(s.job.stage)}</p>
        <progress aria-label={`Progress for ${s.roll_number}`} max={s.job.progress?.total || 1} value={s.job.progress ? s.job.progress.completed : undefined} />
        <p>{s.job.progress ? `${s.job.progress.completed} / ${s.job.progress.total} pages read in this document` : 'Working — this stage has no measurable percentage yet.'}</p>
        <small>{s.job.updated_at ? `Current stage started ${Math.max(0, Math.floor(((updated || new Date()) - new Date(s.job.updated_at)) / 1000))} seconds ago. ` : ''}Waiting for the worker or AI response; updates appear when the stage changes.</small>
      </article>)}
      <p><strong>Workflow:</strong> 1. Upload PDFs → 2. Evaluate → 3. Review and verify → 4. Export marks</p>
      <p>Your courses: {courses.length ? courses.map(c => `${c._id} (${admin ? 'all tasks' : [c.uploaders?.includes(user?.email) && 'upload', c.reviewers?.includes(user?.email) && 'review'].filter(Boolean).join(' + ')})`).join(' · ') : admin ? 'Administrator: all courses are accessible, including courses not yet registered.' : 'No courses assigned yet. Contact your administrator.'}</p>
    </section>
    <section className="workspace-panel" aria-label="Activity log"><h2>Live activity log</h2><p>Latest saved events for sheets on this page. Refreshes automatically; shows up to 100 saved events from each sheet’s current attempt.</p>
      {!activity.length ? <p>No processing activity yet. Upload and queue sheets to begin.</p> : <ol className="activity-log">{activity.map(event => <li key={event.key} className={event.stage === 'error' ? 'workspace-error' : ''}><time>{event.at ? new Date(event.at).toLocaleTimeString() : 'Earlier'}</time> <strong>{event.course} / {event.student}</strong> — {stageLabel(event.stage)}{event.message && <span>: {event.message}</span>}</li>)}</ol>}
      <small>Jobs from before this update show their last known status. New attempts record stage-by-stage activity.</small>
    </section>
    </>}
    {resultsOnly && <section className="workspace-panel" aria-label="Results summary"><h2>Saved results</h2><div className="progress-cards"><div><strong>{viewTotal}</strong><span>Results in this view</span></div><div><strong>{pageInfo ? counts.review : visible.filter(s => !s.active.verified).length}</strong><span>Awaiting verification</span></div><div><strong>{pageInfo ? counts.verified : visible.filter(s => s.active.verified).length}</strong><span>Verified for export</span></div></div><p>Open View details to inspect feedback. Attempt history lets reviewers compare results or add a manual revision.</p></section>}
    {!resultsOnly && preparations.length > 0 && <section className="workspace-panel" aria-label="Folder preparation"><h2>Recent folder preparation</h2>{preparations.map(p => <article key={p._id}><p>{p.exam_id}: {p.kind === 'evaluate' ? 'Bulk submission' : 'Folder preparation'} — {p.state}{p.error ? ` — ${p.error}` : ''}</p>
        {(p.issues || []).length > 0 && <><ul>{p.issues.map((issue, index) => <li key={index}>{issue}</li>)}</ul><button disabled={busy} onClick={() => { setCorrectionMode(true); setExam(p.exam_id); setType(p.exam_type); setMarks(p.max_marks); setFiles(null); uploadPanel.current?.scrollIntoView?.({ behavior: 'smooth' }); }}>Upload corrected folders separately</button></>}
      </article>)}</section>}
    {!resultsOnly && canUpload && <section ref={uploadPanel} className="workspace-panel"><h2>1. Upload course answer sheets</h2>
      <button disabled={busy} onClick={() => { setCorrectionMode(value => !value); setFiles(null); }}>{correctionMode ? 'Return to normal upload' : 'Upload corrected folders separately'}</button>
      {correctionMode && <p>Choose only the corrected course folders. Keep the original examination ID and student filenames to update those same sheets. Include the answer key; missing marking rules fall back to the course question paper, then the administrator scheme for this course and examination type. Other courses remain unchanged; running sheets must finish before replacement.</p>}
      <p>Use course folders, for example FS3401/model_answer.pdf and FS3401/101.pdf. Administrators can upload any course; faculty can upload only their registered, assigned courses.</p>
      <label>Examination / session ID *<input aria-invalid={showValidation && !!missing.exam} aria-describedby="exam-error" value={exam} onChange={e => setExam(e.target.value)} placeholder="2026-October-MSE" />{showValidation && missing.exam && <small id="exam-error" className="field-error">{missing.exam}</small>}</label>
      <label>Marking scheme<select value={type} onChange={e => { setType(e.target.value); setMarks(e.target.value === 'mst' ? 50 : 100); }}><option value="end_sem">End semester</option><option value="mst">Mid semester</option></select></label>
      <label>Maximum marks *<input aria-invalid={showValidation && !!missing.marks} aria-describedby="marks-error" type="number" min="1" max="1000" value={marks} onChange={e => setMarks(e.target.value)} />{showValidation && missing.marks && <small id="marks-error" className="field-error">{missing.marks}</small>}</label>
      <label>Course folder *<input key={correctionMode ? 'correction' : 'normal'} aria-invalid={showValidation && !!missing.files} aria-describedby="folder-error" type="file" webkitdirectory="" directory="" multiple onChange={e => setFiles(e.target.files)} />{showValidation && missing.files && <small id="folder-error" className="field-error">{missing.files}</small>}</label>
      <button disabled={busy} onClick={prepare}>{correctionMode ? 'Upload corrected folders' : 'Upload and check existing results'}</button>
    </section>}
    <section className="workspace-panel"><h2>{resultsOnly ? 'Review saved marks' : '2. Evaluate and track sheets'}</h2>
      {!resultsOnly && canUpload && <button disabled={busy || !viewTotal} onClick={() => action(async () => {
        const response = await api.post('/workspace/evaluate-all', { exam_id: filter || undefined, course_code: courseFilter || undefined, view: tab });
        setNotice(`Bulk submission saved for ${response.data.count} eligible sheets across all pages. It continues in the background and reuses existing successful results.`);
      })}>Evaluate eligible sheets across all pages</button>}
      <div className="workspace-toolbar">
        {(resultsOnly ? ['all', 'pending', 'verified'] : ['all', 'existing', 'failed']).map(t => <button key={t} aria-pressed={tab === t} onClick={() => { setTab(t); setSelected([]); }}>{ { all: resultsOnly ? 'All results' : 'All sheets', pending: 'Awaiting verification', verified: 'Verified results', existing: 'Already evaluated', failed: 'Failed — retry' }[t]}</button>)}
        <label>Examination<select value={filter} onChange={e => { setFilter(e.target.value); setSelected([]); }}><option value="">All examinations</option>{(pageInfo?.examinations || [...new Set(sheets.map(s => s.exam_id))]).map(v => <option key={v}>{v}</option>)}</select></label>
        <label>Course<select value={courseFilter} onChange={e => { setCourseFilter(e.target.value); setSelected([]); }}><option value="">All courses</option>{(pageInfo?.course_codes || [...new Set(sheets.map(s => s.course_code))]).map(v => <option key={v}>{v}</option>)}</select></label>
      </div>
      <div className="workspace-toolbar"><button onClick={() => setSelected(visible.map(s => s._id))}>Select all visible ({visible.length})</button><button onClick={() => setSelected([])}>Clear selection</button>
        {!resultsOnly && <><button disabled={busy || !canRun} onClick={() => evaluate(false)}>Evaluate / use existing</button>
        <button disabled={busy || !canRun} onClick={() => evaluate(true)}>Re-evaluate selected</button></>}
        {resultsOnly && <button disabled={busy || !canReview} onClick={() => verify(selectedRows)}>Mark selected verified</button>}
        {!resultsOnly && <><button disabled={busy || !visible.some(canStop)} onClick={() => setSelected(visible.filter(canStop).map(s => s._id))}>Select running / queued on this page</button>
        <button className="stop-button" disabled={busy || !stoppableSelected.length} onClick={() => stopSheets(stoppableSelected)}>Stop selected ({stoppableSelected.length})</button></>}
      </div>
      <p>{!resultsOnly && 'To evaluate one sheet, select only its checkbox, then choose Evaluate / use existing. '}{selected.length} selected. {admin ? 'Administrator access: you can evaluate, revise and verify any course.' : 'Upload assignments allow evaluation; review assignments allow revising and verifying results.'}</p>
      {!resultsOnly && <p>Use Stop beside a sheet, or select multiple running / queued sheets and choose Stop selected. Queued sheets are cancelled immediately; running sheets stop after the current request returns. Saved results remain available.</p>}
      <div className="workspace-scroll"><table><thead><tr><th>Select</th><th>Exam / course</th><th>Student</th><th>{resultsOnly ? 'Verification' : 'Current work'}</th>{resultsOnly && <><th>Active result</th><th>History</th></>}</tr></thead><tbody>
        {visible.map(s => <tr key={s._id}><td><input type="checkbox" aria-label={`Select ${s.roll_number}`} checked={selectedSet.has(s._id)} onChange={e => setSelected(old => e.target.checked ? [...old, s._id] : old.filter(id => id !== s._id))} /></td>
          <td>{s.exam_id}<br />{s.course_code}</td><td>{s.roll_number}</td>
          <td>{resultsOnly ? (s.active.verified ? 'Verified' : 'Awaiting verification') : <>{s.job?.cancel_requested && s.job.state === 'processing' ? 'Stopping — waiting for the current request to return' : stageLabel(s.job?.stage || s.job?.state)}{s.job?.error && <small className="workspace-error">{s.job.error}</small>} {stopControl(s)}</>}</td>
          {resultsOnly && <><td>{s.active ? <><span>{`${s.active.marks}/${s.max_marks} (${s.active.percentage}%)`}</span><br />{s.active.verified ? 'Verified' : 'Not verified'} <button onClick={() => showDetails(s)}>View details</button></> : '—'}</td>
          <td><button onClick={() => showDetails(s, true)}>Attempt history</button></td></>}</tr>)}
      </tbody></table></div>
      {pageInfo && <nav aria-label="Sheet pages"><button disabled={page <= 1 || busy} onClick={() => { setPage(p => p - 1); setSelected([]); }}>Previous page</button><span> Page {page} of {Math.max(1, Math.ceil(viewTotal / 50))} · {viewTotal} sheets </span><button disabled={page * 50 >= viewTotal || busy} onClick={() => { setPage(p => p + 1); setSelected([]); }}>Next page</button></nav>}
      {!updated && !connectionError && <p role="status">Loading workspace results…</p>}
      {updated && !connectionError && !visible.length && <p>{resultsOnly ? 'No saved results match this view. Completed evaluations will appear here.' : 'No sheets in this view.'}</p>}
      {resultsOnly && <><div className="workspace-toolbar"><button disabled={busy} onClick={() => download()}>Download combined workbook</button>{[...new Set(visible.map(s => s.course_code))].map(c => <button disabled={busy} key={c} onClick={() => download(c)}>Download {c}</button>)}</div>
      <p>Exports include only verified active results. Feedback and OCR content are excluded.</p></>}
      {resultsOnly && admin && <section className="workspace-delete" aria-label="Delete selected data"><h3>Delete selected data</h3>
        <label>Data to delete<select aria-describedby="delete-scope-description" value={scope} onChange={e => setScope(e.target.value)}>
          <option value="cache">Cache only — keep marks</option><option value="records">Marks and attempt history — keep cache</option>
          <option value="both">Marks, history and cache — keep sheet</option><option value="sheet">Sheet record, marks, history and cache</option>
        </select></label>
        <p id="delete-scope-description">{deleteDescription} Original uploaded PDFs are retained.</p>
        {selectedBusy && <p role="status">Cancel selected evaluations and wait for them to stop before deleting their data.</p>}
        <button className="danger-button" disabled={busy || !selected.length || selectedBusy} onClick={() => {
          const names = selectedRows.slice(0, 5).map(s => `${s.exam_id} / ${s.course_code} / ${s.roll_number}`).join('\n');
          if (window.prompt(`${deleteDescription}\n\n${selected.length} selected sheets:\n${names}${selectedRows.length > 5 ? '\n…' : ''}\n\nOriginal PDFs are retained. This cannot be undone. Type DELETE to confirm.`) !== 'DELETE') return;
          action(async () => { await api.post('/workspace/manage', { sheet_ids: selected, scope, confirmation: 'DELETE' }); setSelected([]); setDetail(null); setHistory(null); setHistorySheet(null); setNotice('Selected data deleted. Source uploads are retained.'); });
        }}>Delete ({selected.length})…</button>
      </section>}
    </section>
    {detail?.active && <ResultDetails modal result={detail.active} maxMarks={detail.max_marks} onClose={() => setDetail(null)} onVerify={busy || !allowed(detail.course_code, 'reviewers') ? null : () => verify([detail])} />}
    {selectedHistory && <section className="workspace-panel" aria-label="Attempt history"><h2>{selectedHistory.roll_number} — attempt history</h2><button onClick={() => { setHistory(null); setHistorySheet(null); }}>Close history</button>
      {selectedHistory.attempts.map(a => <article key={a._id}><p>{new Date(a.created_at).toLocaleString()} · {a.status} {a._id === selectedHistory.active_attempt ? '· Active result' : ''}</p><p>{a.status === 'completed' ? `${a.marks}/${selectedHistory.max_marks}` : a.error?.message || 'Processing'}</p>
        <ResultDetails result={a} maxMarks={selectedHistory.max_marks} onClose={() => { setHistory(null); setHistorySheet(null); }} />
        {allowed(selectedHistory.course_code, 'reviewers') && a.status === 'completed' && a._id !== selectedHistory.active_attempt && <button disabled={busy} onClick={() => action(() => api.post('/workspace/result', { sheet_id: selectedHistory._id, attempt_id: a._id }))}>Use this result</button>}
      </article>)}
      <div><button disabled={historyOffset === 0} onClick={() => showDetails(selectedHistory, true, Math.max(0, historyOffset - 20))}>Newer attempts</button><button disabled={historyOffset + 20 >= (selectedHistory.attempt_count || selectedHistory.attempts.length)} onClick={() => showDetails(selectedHistory, true, historyOffset + 20)}>Older attempts</button></div>
      <button disabled={busy || !allowed(selectedHistory.course_code, 'reviewers')} onClick={() => {
        const value = window.prompt(`Manual marks (0–${selectedHistory.max_marks})`); if (value === null || value.trim() === '') return;
        const reason = window.prompt('Reason for the manual revision'); if (!reason) return;
        action(() => api.post('/workspace/result', { sheet_id: selectedHistory._id, marks: Number(value), reason }));
      }}>Add manual revision</button>
    </section>}
  </main>;
}
