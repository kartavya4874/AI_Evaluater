import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api, { deleteEvaluation } from '../services/api';
import ResultDetails from '../components/ResultDetails';
import './Workspace.css';

export default function ManageResults() {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [source, setSource] = useState('all');
  const [course, setCourse] = useState('');
  const [exam, setExam] = useState('');
  const [status, setStatus] = useState('all');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState([]);
  const [scope, setScope] = useState('records');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [detail, setDetail] = useState(null);
  const key = row => `${row.source}:${row.id}`;
  const loadInventory = useCallback(() => api.get('/workspace/inventory', { params: { page, page_size: 50, source, course_code: course || undefined, ...(exam ? { exam_id: exam } : {}), ...(status !== 'all' ? { status } : {}), ...(search ? { q: search } : {}) } }), [page, source, course, exam, status, search]);
  const refresh = useCallback(async () => {
    const response = await loadInventory();
    setData(response.data);
    setSelected(old => old.filter(id => response.data.items.some(row => `${row.source}:${row.id}` === id)));
    if (page > 1 && !response.data.items.length) setPage(Math.max(1, Math.ceil(response.data.total / 50)));
  }, [page, loadInventory]);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(''); setSelected([]);
    api.get('/workspace/inventory', { params: { page, page_size: 50, source, course_code: course || undefined, ...(exam ? { exam_id: exam } : {}), ...(status !== 'all' ? { status } : {}), ...(search ? { q: search } : {}) } })
      .then(response => { if (active) setData(response.data); })
      .catch(e => { if (active) { setData(null); setError(e.response?.data?.error || e.message); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [page, source, course, exam, status, search]);
  const rows = data?.items || [];
  const chosen = rows.filter(row => selected.includes(key(row)));
  const saved = chosen.filter(row => row.source === 'legacy');
  const workspace = chosen.filter(row => row.source === 'workspace');
  const running = workspace.some(row => ['queued', 'processing', 'managing'].includes(row.status));
  const stoppable = workspace.filter(row => ['queued', 'processing'].includes(row.status));
  useEffect(() => {
    if (!running || busy || loading) return;
    let active = true;
    let timer;
    const poll = async () => {
      try {
        const response = await loadInventory();
        if (active) setData(response.data);
      } catch (e) {
        if (active) setError(`Unable to refresh processing status: ${e.response?.data?.error || e.message}`);
      }
      if (active) timer = setTimeout(poll, 3000);
    };
    timer = setTimeout(poll, 3000);
    return () => { active = false; clearTimeout(timer); };
  }, [running, busy, loading, loadInventory]);
  const description = { records: 'Delete marks and attempt history; retain workspace sheets and cache.', cache: 'Clear workspace cache; retain sheets, marks and history.', both: 'Delete marks, history and cache; retain workspace sheets.', sheet: 'Delete workspace sheet records, marks, history and cache.' }[scope];
  const run = async operation => {
    setBusy(true); setError(''); setNotice('');
    try { await operation(); }
    catch (e) { setError(e.response?.data?.error || e.message); }
    finally { setBusy(false); }
  };
  const remove = () => {
    const explanation = `${workspace.length ? description : ''}\n${saved.length ? `${saved.length} saved evaluations will be permanently deleted, including marks and feedback.` : ''}\nOriginal uploaded PDFs are retained.`;
    if (window.prompt(`${explanation}\n\nSelected: ${chosen.map(row => row.roll_number || row.id).join(', ')}\nThis cannot be undone. Type DELETE to confirm.`) !== 'DELETE') return;
    run(async () => {
      let removed = 0;
      let failure;
      try {
        if (workspace.length) {
          await api.post('/workspace/manage', { sheet_ids: workspace.map(row => row.id), scope, confirmation: 'DELETE' });
          removed += workspace.length;
        }
        for (const row of saved) { await deleteEvaluation(row.id); removed++; }
      } catch (e) { failure = e; }
      await refresh();
      setSelected([]);
      setNotice(`Management action completed for ${removed} selected record(s).`);
      if (failure) throw new Error(`Action stopped: ${failure.response?.data?.error || failure.message}. Review the refreshed list before retrying.`);
    });
  };
  return <main className="workspace">
    <h1>Manage answer sheets</h1>
    <p>All workspace sheets and saved evaluations, including single evaluations, failed work, and sheets without marks. <Link to="/results">Review results</Link></p>
    {error && <p role="alert" className="workspace-error">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    <section className="workspace-panel">
      <form className="workspace-toolbar" role="search" onSubmit={e => { e.preventDefault(); setSearch(searchInput.trim()); setPage(1); setSelected([]); }}>
        <label>Search answer sheets<input type="search" maxLength={120} disabled={busy} value={searchInput} onChange={e => setSearchInput(e.target.value)} placeholder="Roll number, student name, course or examination" /></label>
        <button disabled={busy}>Search</button>
        <button type="button" disabled={busy} onClick={() => { setSearchInput(''); setSearch(''); setSource('all'); setCourse(''); setExam(''); setStatus('all'); setPage(1); setSelected([]); }}>Clear filters</button>
      </form>
      <div className="workspace-toolbar">
        <label>Records<select disabled={busy} value={source} onChange={e => { setSource(e.target.value); setPage(1); }}><option value="all">All answer sheets and evaluations</option><option value="workspace">Workspace sheets</option><option value="legacy">Saved evaluations (single and previous batch)</option></select></label>
        <label>Course<select disabled={busy} value={course} onChange={e => { setCourse(e.target.value); setPage(1); }}><option value="">All courses</option>{(data?.course_codes || []).map(code => <option key={code}>{code}</option>)}</select></label>
        <label>Examination<select disabled={busy} value={exam} onChange={e => { setExam(e.target.value); setPage(1); }}><option value="">All examinations</option>{(data?.examinations || []).map(id => <option key={id}>{id}</option>)}</select></label>
        <label>Status<select disabled={busy} value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}><option value="all">All statuses</option><option value="verified">Verified</option><option value="unverified">Unverified results</option><option value="failed">Failed / needs review</option><option value="no_marks">No saved marks</option></select></label>
        <button disabled={busy || loading} onClick={() => run(refresh)}>Refresh records</button>
      </div>
      {loading ? <p role="status">Loading answer sheets…</p> : data && <>
        <p>{data.total} records: {data.counts.workspace} workspace sheets and {data.counts.legacy} saved evaluations.</p>
        <button disabled={busy} onClick={() => setSelected(rows.map(key))}>Select all on this page</button>
        <button disabled={busy} onClick={() => setSelected([])}>Clear selection</button>
        <div className="workspace-scroll"><table><thead><tr><th>Select</th><th>Student</th><th>Course / examination</th><th>Record type</th><th>Status</th><th>Marks</th><th>Details</th></tr></thead><tbody>
          {rows.map(row => <tr key={key(row)}>
            <td><input type="checkbox" disabled={busy} aria-label={`Select ${row.roll_number || row.id} ${row.source}`} checked={selected.includes(key(row))} onChange={e => setSelected(old => e.target.checked ? [...old, key(row)] : old.filter(id => id !== key(row)))} /></td>
            <td>{row.roll_number || row.id}</td><td>{row.course_code || 'Not recorded'} / {row.exam_id || 'Not recorded'}</td>
            <td>{row.source === 'workspace' ? 'Workspace sheet' : 'Saved evaluation'}</td><td>{row.status}{row.verified ? ' · Verified' : ''}</td>
            <td>{row.marks == null ? 'No saved marks' : `${row.marks}/${row.max_marks ?? '—'}`}</td>
            <td>{row.source === 'legacy' ? <Link to={`/results/${row.id}`}>View details</Link> : <button disabled={busy} onClick={() => run(async () => { const response = await api.get(`/workspace/sheets/${row.id}`); setDetail(response.data.sheet); })}>View details</button>}</td>
          </tr>)}
        </tbody></table></div>
        {!rows.length && <p>No records match these filters.</p>}
        <nav aria-label="Inventory pages"><button disabled={busy || page === 1} onClick={() => setPage(p => p - 1)}>Previous page</button> Page {page} of {Math.max(1, Math.ceil(data.total / 50))} <button disabled={busy || page * 50 >= data.total} onClick={() => setPage(p => p + 1)}>Next page</button></nav>
      </>}
    </section>
    <section className="workspace-panel" aria-label="Manage selected records"><h2>Manage selected records ({chosen.length})</h2>
      <label>Action<select disabled={busy} value={scope} onChange={e => setScope(e.target.value)}><option value="records">Delete marks and history</option><option value="cache">Clear cache only (workspace sheets)</option><option value="both">Delete marks, history and cache</option><option value="sheet">Delete complete records</option></select></label>
      <p>{description} Original uploaded PDFs are retained.</p>
      {saved.length > 0 && <p>Selected saved evaluations are standalone records: deleting their marks deletes the evaluation and feedback. Cache-only actions are unavailable for these records.</p>}
      {running && <p role="status">Apply is unavailable while selected sheets are running, queued or being managed. Stop active sheets below, or deselect them. Status refreshes automatically every 3 seconds; Apply becomes available when all selected sheets are idle.</p>}
      {stoppable.length > 0 && <button className="stop-button" disabled={busy || loading} onClick={() => run(async () => {
        await api.post('/workspace/cancel', { sheet_ids: stoppable.map(row => row.id) });
        setNotice('Stop requested. Running sheets stop after the current request returns. Your selection is retained; apply the deletion once the sheets are idle.');
        await refresh();
      })}>Stop selected active sheets ({stoppable.length})</button>}
      <button disabled={busy || loading || !chosen.length || running || (scope === 'cache' && saved.length > 0)} onClick={remove}>Apply to selected ({chosen.length})…</button>
    </section>
    {detail && <ResultDetails modal result={detail.active || { marks: null, feedback: detail.job?.error || detail.attempts?.[0]?.error?.message || 'No saved result yet.' }} maxMarks={detail.max_marks} onClose={() => setDetail(null)}>
      <p>Processing status: {detail.job?.state || 'ready'}</p>
      {!detail.active && <Link to="/evaluate/batch">Open evaluation workspace</Link>}
      {(detail.attempts || []).length > 0 && <section><h3>Attempt history</h3>{detail.attempts.map(attempt => <p key={attempt._id}>{attempt.status} · {attempt.error?.message || attempt.feedback || 'No feedback saved.'}</p>)}</section>}
    </ResultDetails>}
  </main>;
}
