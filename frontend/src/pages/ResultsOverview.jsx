import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api, { updateManualEvaluation } from '../services/api';
import ResultDetails from '../components/ResultDetails';
import './Workspace.css';
import './BatchResults.css';

export default function ResultsOverview() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [view, setView] = useState('all');
  const [course, setCourse] = useState('');
  const [exam, setExam] = useState('');
  const [source, setSource] = useState('all');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState([]);
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [reload, setReload] = useState(0);
  const key = row => `${row.source}:${row.id}`;
  const refresh = useCallback(() => { setSelected([]); setReload(value => value + 1); }, []);
  useEffect(() => {
    let active = true;
    setLoading(true); setSelected([]);
    api.get('/workspace/results', { params: { page, page_size: 50, view, course_code: course || undefined, exam_id: exam || undefined, ...(search ? { q: search } : {}), ...(source !== 'all' ? { source } : {}) } })
      .then(response => { if (active) {
        setData(response.data);
        const lastPage = Math.max(1, Math.ceil(response.data.total / 50));
        if (page > lastPage) setPage(lastPage);
      } })
      .catch(e => { if (active) { setData(null); setError(e.response?.data?.error || e.message); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [page, view, course, exam, source, search, reload]);
  useEffect(() => { setError(''); }, [page, view, course, exam, source, search]);
  const rows = data?.items || [];
  const eligible = row => !row.result.needs_review && !row.result.verified && row.result.marks != null && !['error', 'processing', 'cancelled', 'needs_review'].includes(row.result.status);
  const chosen = rows.filter(row => selected.includes(key(row)) && eligible(row));
  const act = async operation => {
    setBusy(true); setError(''); setNotice('');
    try { await operation(); }
    catch (e) { setError(e.response?.data?.error || e.message); }
    finally { setBusy(false); }
  };
  const verify = records => act(async () => {
    try {
      for (const source of ['workspace', 'legacy']) {
        const items = records.filter(row => row.source === source).map(row => source === 'workspace'
          ? { id: row.id, attempt_id: row.result._id } : { id: row.id, revision: row.result.verification_revision });
        if (items.length) await api.post('/workspace/verify', { source, items });
      }
      setNotice('Selected results verified.'); setDetail(null); refresh();
    } catch (e) {
      // Reload partial successes without hiding the error from the failed group.
      setDetail(null); refresh();
      throw new Error(`${e.response?.data?.error || e.message}. Some results may already be verified; the list has been requested again. Check its current state before retrying.`);
    }
  });
  const open = row => act(async () => {
    const response = await api.get(row.source === 'legacy' ? `/workspace/results/legacy/${row.id}` : `/workspace/sheets/${row.id}`);
    const sheet = response.data.sheet;
    const result = row.source === 'legacy' ? response.data.result : sheet.job?.state === 'needs_review'
      ? { status: 'needs_review', needs_review: true, marks: null, feedback: sheet.job.error || 'Marking scheme needs review' } : sheet.active;
    if (!result) { refresh(); throw new Error('This result is no longer active. The results list is being refreshed.'); }
    setDetail({ ...row, result,
      sheet: response.data.sheet, historyOffset: 0 });
  });
  const revise = row => {
    const marks = window.prompt(`Manual marks (0–${row.max_marks})`, String(row.result.marks ?? ''));
    if (marks === null || !marks.trim()) return;
    const reason = window.prompt('Reason for the manual revision');
    if (!reason?.trim()) return;
    act(async () => {
      if (!Number.isFinite(Number(marks)) || Number(marks) < 0 || Number(marks) > row.max_marks) throw new Error('Enter marks within the allowed range.');
      if (row.source === 'legacy') await updateManualEvaluation(row.id, Number(marks), reason);
      else await api.post('/workspace/result', { sheet_id: row.id, marks: Number(marks), reason });
      setDetail(null); setNotice('Manual grade saved. Review and verify the updated marks.'); refresh();
    });
  };
  const download = () => act(async () => {
    const response = await api.get('/workspace/export', { params: { source, course_code: course || undefined, exam_id: exam || undefined, ...(search ? { q: search } : {}) }, responseType: 'blob' });
    const url = URL.createObjectURL(response.data), anchor = document.createElement('a');
    anchor.href = url; anchor.download = `${course || 'all-courses'}-verified-results.xlsx`; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  return <main className="workspace batch-results">
    <div className="results-header"><div><h1>Review results</h1><p className="results-subtitle">All saved evaluations in one place, including single sheets and previous batches.</p></div>
      {user?.role === 'admin' && <Link to="/manage-results">Manage answer sheets</Link>}
    </div>
    {error && <p role="alert" className="workspace-error">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    <section className="workspace-panel" aria-label="Results summary"><div className="progress-cards">
      <div><strong>{loading || !data ? '—' : data.total}</strong><span>Results in this view</span></div>
      <div><strong>{loading || !data ? '—' : data.pending}</strong><span>Awaiting verification</span></div>
      <div><strong>{loading || !data ? '—' : data.verified}</strong><span>Verified</span></div>
      <div><strong>{loading || !data ? '—' : data.needs_review || 0}</strong><span>Needs review</span></div>
    </div></section>
    <section className="workspace-panel" aria-label="Saved results">
      <form className="workspace-toolbar" role="search" onSubmit={e => { e.preventDefault(); setSearch(searchInput.trim()); setPage(1); setSelected([]); }}>
        <label>Search results<input type="search" maxLength={120} disabled={busy} value={searchInput} onChange={e => setSearchInput(e.target.value)} placeholder="Roll number, student name, course or examination" /></label>
        <button disabled={busy}>Search</button>
        <button type="button" disabled={busy} onClick={() => { setSearchInput(''); setSearch(''); setCourse(''); setExam(''); setSource('all'); setView('all'); setPage(1); setSelected([]); }}>Clear filters</button>
      </form>
      <div className="workspace-toolbar">
        {[['all', 'All results'], ['pending', 'Awaiting verification'], ['verified', 'Verified results'], ['needs_review', 'Needs review']].map(([value, label]) => <button key={value} disabled={busy} aria-pressed={view === value} onClick={() => { setView(value); setPage(1); }}>{label}</button>)}
        <label>Record type<select disabled={busy} value={source} onChange={e => { setSource(e.target.value); setPage(1); }}><option value="all">All records</option><option value="workspace">Workspace results</option><option value="legacy">Saved single and previous batch results</option></select></label>
        <label>Course<select disabled={busy} value={course} onChange={e => { setCourse(e.target.value); setPage(1); }}><option value="">All courses</option>{(data?.course_codes || []).map(code => <option key={code}>{code}</option>)}</select></label>
        <label>Examination<select disabled={busy} value={exam} onChange={e => { setExam(e.target.value); setPage(1); }}><option value="">All examinations</option>{(data?.examinations || []).map(id => <option key={id}>{id}</option>)}</select></label>
        <button disabled={busy || loading} onClick={refresh}>Refresh results</button>
      </div>
      <div className="saved-results-toolbar"><div className="header-actions">
        <button disabled={busy || loading} onClick={() => setSelected(rows.filter(eligible).map(key))}>Select unverified on this page</button>
        <button disabled={busy || !selected.length} onClick={() => setSelected([])}>Clear selection</button>
        <button className="saved-primary" disabled={busy || loading || !chosen.length} onClick={() => verify(chosen)}>Mark selected verified ({chosen.length})</button>
        <button disabled={busy || loading} onClick={download}>Download verified workbook</button>
      </div></div>
      <p className="saved-results-help">Only verified marks are exported. Search, course, examination and record-type filters apply across all pages and to the verified workbook. Deletion and cache management are available under Manage answer sheets.</p>
      {loading ? <p role="status">Loading results…</p> : data && <>
        <div className="workspace-scroll"><table className="results-table"><thead><tr><th>Select</th><th>Student</th><th>Course / examination</th><th>Marks</th><th>Grade</th><th>Status</th><th>Actions</th></tr></thead><tbody>
          {rows.map(row => <tr key={key(row)}><td><input type="checkbox" aria-label={`Select ${row.roll_number || row.id} ${row.source}`} disabled={busy || !eligible(row)} checked={selected.includes(key(row))} onChange={e => setSelected(old => e.target.checked ? [...old, key(row)] : old.filter(id => id !== key(row)))} /></td>
            <td className="roll-num">{row.roll_number || row.id}</td><td>{row.course_code || 'Not recorded'}<br />{row.exam_id || 'Not recorded'}</td>
            <td className="marks-col">{row.result.marks == null ? '—' : `${row.result.marks}/${row.max_marks}`} {!row.result.verified && row.result.marks != null && <small>Unverified saved score</small>}</td>
            <td>{row.result.needs_review ? 'Needs review' : row.result.grade || '—'}</td>
            <td><span className={`verification-badge ${row.result.verified ? 'is-verified' : 'is-pending'}`}>{row.result.needs_review ? 'Needs review' : row.result.verified ? 'Verified' : 'Not verified'}</span>{row.result.needs_review && <small>{row.result.feedback}</small>}</td>
            <td><div className="saved-row-actions"><button disabled={busy} onClick={() => open(row)}>View details</button>{row.can_edit && <button disabled={busy} onClick={() => revise(row)}>Edit grade</button>}</div></td>
          </tr>)}
        </tbody></table></div>
        {!rows.length && <p>No saved results match these filters.</p>}
        <nav aria-label="Result pages"><button disabled={busy || page === 1} onClick={() => setPage(p => p - 1)}>Previous page</button> Page {page} of {Math.max(1, Math.ceil(data.total / 50))} · {data.total} results <button disabled={busy || page * 50 >= data.total} onClick={() => setPage(p => p + 1)}>Next page</button></nav>
      </>}
    </section>
    {detail?.result && <ResultDetails modal result={detail.result} maxMarks={detail.max_marks} onClose={() => setDetail(null)} onVerify={busy || !eligible(detail) ? null : () => verify([detail])}>
      {detail.result.needs_review && <p>Correct the marking scheme in <Link to="/management">Courses & accounts</Link>, then <Link to="/evaluate/batch">retry the sheet in Batch evaluation</Link>. No marks have been awarded for this attempt.</p>}
      {detail.sheet && <section><h3>Attempt history</h3>{(detail.sheet.attempts || []).map(attempt => <article key={attempt._id}><p>{attempt.status} · {attempt.marks ?? '—'} / {detail.max_marks}</p>
        <p>{attempt.feedback || attempt.error?.message}</p>
        {attempt.status === 'completed' && attempt._id !== detail.sheet.active_attempt && <button disabled={busy} onClick={() => act(async () => { await api.post('/workspace/result', { sheet_id: detail.id, attempt_id: attempt._id }); setDetail(null); refresh(); })}>Use this result</button>}
      </article>)}{detail.sheet.attempt_count > 20 && <div>
        {[['Newer attempts', -20], ['Older attempts', 20]].map(([label, change]) => <button key={label} disabled={busy || (change < 0 ? detail.historyOffset === 0 : detail.historyOffset + 20 >= detail.sheet.attempt_count)} onClick={() => act(async () => {
          const offset = detail.historyOffset + change;
          const response = await api.get(`/workspace/sheets/${detail.id}`, { params: { offset } });
          setDetail({ ...detail, sheet: response.data.sheet, historyOffset: offset });
        })}>{label}</button>)}
      </div>}</section>}
    </ResultDetails>}
  </main>;
}
