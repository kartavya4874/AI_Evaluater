import React, { useEffect, useState } from 'react';
import api from '../services/api';
import './Workspace.css';

const base = '/workspace/teacher-comparisons';
const statusLabels = { matched: 'Compared', unmatched: 'No matching record', ambiguous: 'Multiple matches — use template ID', no_ai_result: 'No completed AI result', manual_result: 'Manual grade — excluded', max_marks_mismatch: 'Maximum marks differ', invalid_ai_marks: 'Invalid AI marks', missing_question_score: 'Question score unavailable', identity_mismatch: 'Student/exam does not match ID' };

export default function TeacherComparison() {
  const [catalog, setCatalog] = useState({ courses: [], reports: [] });
  const [course, setCourse] = useState('');
  const [name, setName] = useState('');
  const [split, setSplit] = useState('calibration');
  const [independent, setIndependent] = useState(false);
  const [tolerance, setTolerance] = useState(3);
  const [file, setFile] = useState(null);
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [page, setPage] = useState(1);
  const [problemsOnly, setProblemsOnly] = useState(false);
  const refresh = async () => setCatalog((await api.get(base)).data);
  useEffect(() => { refresh().catch(e => setError(e.response?.data?.error || e.message)); }, []);
  const act = async operation => {
    setBusy(true); setError(''); setNotice('');
    try { await operation(); } catch (e) { setError(e.response?.data?.error || e.message); }
    finally { setBusy(false); }
  };
  const show = value => { setReport(value); setPage(1); setProblemsOnly(false); };
  const download = async (url, filename, params) => {
    try {
      const response = await api.get(url, { params, responseType: 'blob' });
      const objectUrl = URL.createObjectURL(response.data), anchor = document.createElement('a');
      anchor.href = objectUrl; anchor.download = filename; anchor.click();
      setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    } catch (e) {
      if (e.response?.data instanceof Blob) {
        const body = await e.response.data.text();
        try { throw new Error(JSON.parse(body).error || 'Download failed'); }
        catch (parsed) { if (parsed instanceof SyntaxError) throw new Error('Download failed'); throw parsed; }
      }
      throw e;
    }
  };
  const metric = value => value == null ? '—' : Number(value).toFixed(2);
  const metrics = (title, value) => <section className="workspace-panel" aria-label={title}><h3>{title}</h3><div className="progress-cards">
    <div><strong>{value.compared} / {value.uploaded}</strong><span>Rows compared</span></div>
    <div><strong>{metric(value.mape_pct)}{value.mape_pct == null ? '' : '%'}</strong><span>Average relative error vs teacher marks</span></div>
    <div><strong>{metric(value.mae_pct)}</strong><span>Average absolute difference (percentage points)</span></div>
    <div><strong>{metric(value.bias_pct)}</strong><span>Bias: AI minus teacher (percentage points)</span></div>
    <div><strong>{metric(value.within_tolerance_pct)}{value.within_tolerance_pct == null ? '' : '%'}</strong><span>Within ±{report.tolerance} percentage points</span></div>
  </div><p>{value.excluded} rows excluded. Positive bias means AI awarded more marks; negative means fewer.</p><p>Relative error = |AI − teacher| ÷ teacher × 100, averaged across {value.relative_compared ?? 'unrecorded'} rows. {value.zero_teacher_rows ?? 'Unrecorded'} zero-teacher-score rows are excluded from relative error only; they remain in absolute differences. Relative errors can be large for low teacher scores.</p></section>;
  const rows = report?.rows.filter(row => !problemsOnly || row.status !== 'matched' || Math.abs(row.difference_pct) > report.tolerance) || [];
  return <main className="workspace">
    <h1>Teacher comparison</h1>
    <p>Compare independent teacher marks with AI marks. Uploads never overwrite grades, verify results, or automatically train the model.</p>
    {error && <p role="alert" className="workspace-error">{error}</p>}{notice && <p role="status">{notice}</p>}
    <section className="workspace-panel"><h2>1. Prepare teacher marks</h2>
      <label>Course<select disabled={busy} value={course} onChange={e => setCourse(e.target.value)}><option value="">Choose a course</option>{catalog.courses.map(code => <option key={code}>{code}</option>)}</select></label>
      <p>Download a template with student IDs and maximum marks. AI scores are hidden so teachers can mark independently. Enter teacher_marks; leave unmarked rows blank. Keep IDs unchanged and roll numbers as text to preserve leading zeros.</p>
      <div className="workspace-toolbar"><button disabled={busy || !course} onClick={() => act(() => download(`${base}/template`, 'teacher-totals-template.xlsx', { course_code: course, level: 'totals' }))}>Download totals template</button>
        <button disabled={busy || !course} onClick={() => act(() => download(`${base}/template`, 'teacher-questions-template.xlsx', { course_code: course, level: 'questions' }))}>Download question template</button></div>
      <details><summary>Using your own spreadsheet</summary><p>Required: teacher_marks, max_marks, and either source + result_id or roll_number + exam_id. Optional: course_code, question_id, teacher_feedback. Use source “workspace” or “legacy”. Leave question_id blank for the total. Matching is exact; ambiguous records are excluded. With no exam_id, only records without an examination ID are eligible. Use numeric cells, not formulas. UTF-8 CSV and .xlsx are supported, up to 5 MB / 1000 rows.</p></details>
    </section>
    <section className="workspace-panel"><h2>2. Upload and preview</h2>
      <form onSubmit={e => { e.preventDefault(); if (!file || !course) { setError('Choose a course and teacher marks file.'); return; } act(async () => {
        const body = new FormData(); body.append('file', file); body.append('course_code', course); body.append('name', name); body.append('split', split); body.append('independent', String(independent)); body.append('tolerance', String(tolerance));
        const response = await api.post(`${base}/preview`, body); show(response.data.report);
      }); }}>
        <label>Comparison name<input required maxLength={120} disabled={busy} value={name} onChange={e => setName(e.target.value)} placeholder="FS3401 October — teacher benchmark" /></label>
        <label>Dataset purpose<select disabled={busy} value={split} onChange={e => setSplit(e.target.value)}><option value="calibration">Calibration — investigate and improve grading</option><option value="test">Held-out test — final assessment</option></select></label>
        <p>Use calibration papers to improve the rubric or prompts. Keep held-out papers separate; do not tune against their scores.</p>
        <label><input type="checkbox" disabled={busy} checked={independent} onChange={e => setIndependent(e.target.checked)} />Teacher marked independently, before seeing AI scores</label>
        <label>Allowed difference (percentage points)<input type="number" min="0" max="100" step="0.1" required disabled={busy} value={tolerance} onChange={e => setTolerance(e.target.value)} /></label>
        <small>For a 50-mark exam, 3 percentage points means 1.5 marks. This is your comparison tolerance, not an accuracy guarantee.</small>
        <label>Teacher marks file<input disabled={busy} type="file" accept=".csv,.xlsx" required onChange={e => setFile(e.target.files?.[0] || null)} /></label>
        <button disabled={busy || !course || !file}>Preview comparison</button>
      </form>
    </section>
    {report && <section aria-label="Comparison report"><h2>{report.name} — {report.state === 'draft' ? 'Preview' : 'Saved comparison'}</h2>
      <p>{report.course_code} · {report.split === 'test' ? 'Held-out test' : 'Calibration'} · {new Date(report.created_at).toLocaleString()}</p>
      {!report.independent && <p role="note">Teacher independence was not confirmed. Treat these differences as assisted review, not an independent accuracy benchmark.</p>}
      <p>These are frozen AI scores from the comparison time. Manual grades and missing or ambiguous matches are excluded, not counted as correct.</p>
      {metrics('Paper totals', report.totals)}{metrics('Question scores', report.questions)}
      {report.change && <section className="workspace-panel" aria-label="Change from baseline">
        <h3>Change from baseline: {report.change.baseline_name}</h3>
        <p>Compared with the saved run from {new Date(report.change.baseline_created_at).toLocaleString()}. Only identical teacher targets with valid AI scores in both runs contribute to the change.</p>
        {['totals', 'questions'].map(level => {
          const change = report.change[level];
          return <div key={level}><h4>{level === 'totals' ? 'Paper totals' : 'Question scores'}</h4>
            <p>{change.paired} paired rows · {change.newly_comparable} newly comparable · {change.no_longer_comparable} no longer comparable</p>
            {change.paired ? <>
              <p>Average absolute difference on the same rows: {metric(change.before_mae_pct)} → {metric(change.after_mae_pct)} percentage points.</p>
              <p>Relative error vs teacher marks: {metric(change.before_mape_pct)}% → {metric(change.after_mape_pct)}% across {change.relative_paired ?? 'unrecorded'} paired rows with nonzero teacher marks.</p>
              <p>Change: {metric(change.mae_change_pct)} percentage points. Negative means closer to teacher marks; positive means further away.</p>
              <p>{change.improved} improved · {change.worsened} worsened · {change.unchanged} unchanged</p>
              {change.same_prediction > 0 && <p>{change.same_prediction} paired rows use the same saved prediction. Re-evaluate after a grading change to measure its effect.</p>}
            </> : <p>No comparable rows in both runs; an improvement cannot be measured.</p>}
            {change.no_longer_comparable > 0 && <p className="workspace-error">Some previously compared rows are now excluded. A lower overall average alone does not demonstrate improvement.</p>}
          </div>;
        })}
        <button disabled={busy} onClick={() => act(async () => show((await api.get(`${base}/${report.change.baseline_id}`)).data.report))}>Open baseline comparison</button>
      </section>}
      <div className="workspace-toolbar">
        {report.state === 'draft' ? <button disabled={busy} onClick={() => act(async () => { await api.post(`${base}/${report._id}/save`, {}); show({ ...report, state: 'saved' }); await refresh(); setNotice('Teacher benchmark and AI comparison saved separately from evaluation records.'); })}>Save comparison</button>
          : <button disabled={busy} onClick={() => act(async () => { const response = await api.post(`${base}/${report._id}/compare-latest`, {}); show(response.data.report); })}>Compare latest AI results</button>}
        <button disabled={busy} onClick={() => act(() => download(`${base}/${report._id}/export`, 'teacher-comparison.xlsx'))}>Download comparison workbook</button>
        <label><input type="checkbox" checked={problemsOnly} onChange={e => { setProblemsOnly(e.target.checked); setPage(1); }} />Show disagreements and excluded rows only</label>
      </div>
      <p>“Compare latest” reads saved AI evaluations; it does not run new grading. Re-evaluate papers in Evaluate → Batch after an approved grading change, then compare again.</p>
      <div className="workspace-scroll"><table><thead><tr><th>Student</th><th>Question</th><th>Teacher</th><th>AI</th><th>AI − teacher</th><th>Status</th><th>Teacher feedback</th><th>Model / version</th></tr></thead><tbody>
        {rows.slice((page - 1) * 50, page * 50).map((row, index) => <tr key={row.row || index}><td>{row.roll_number || row.result_id}</td><td>{row.question_id || 'Total'}</td><td>{row.teacher_marks}/{row.max_marks}</td><td>{row.ai_marks ?? '—'}</td><td>{row.difference ?? '—'}{row.difference_pct != null && <small> ({metric(row.difference_pct)} pp)</small>}</td><td>{statusLabels[row.status] || row.status}{row.status === 'matched' && Math.abs(row.difference_pct) > report.tolerance ? ' — outside tolerance' : ''}</td><td>{row.teacher_feedback || '—'}</td><td>{row.model || '—'} / {row.pipeline_version || '—'}</td></tr>)}
      </tbody></table></div>
      {!rows.length && <p>No rows match this view.</p>}
      <nav aria-label="Comparison pages"><button disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous page</button> Page {page} of {Math.max(1, Math.ceil(rows.length / 50))}<button disabled={page * 50 >= rows.length} onClick={() => setPage(p => p + 1)}>Next page</button></nav>
    </section>}
    <section className="workspace-panel"><h2>Saved comparisons</h2><p>Latest 100 comparisons for courses you can review. Previous snapshots remain unchanged when you compare again.</p>
      {!catalog.reports.length && <p>No saved comparisons yet.</p>}
      {catalog.reports.map(item => <p key={item._id}><button disabled={busy} onClick={() => act(async () => { show((await api.get(`${base}/${item._id}`)).data.report); })}>{item.name}</button> · {item.course_code} · {item.split === 'test' ? 'Held-out test' : 'Calibration'} · {new Date(item.created_at).toLocaleString()}</p>)}
    </section>
  </main>;
}
