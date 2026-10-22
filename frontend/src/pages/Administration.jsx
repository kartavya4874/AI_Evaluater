import React, { useCallback, useEffect, useState } from 'react';
import { Navigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';
import './Workspace.css';

export default function Administration() {
  const { user } = useAuth();
  const [data, setData] = useState({ courses: [], faculty: [] });
  const [faculty, setFaculty] = useState({ name: '', email: '', role: 'faculty' });
  const [course, setCourse] = useState({ code: '', name: '', uploaders: [], reviewers: [] });
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const refresh = useCallback(async () => setData((await api.get('/access')).data), []);
  useEffect(() => { if (user?.role === 'admin') refresh().catch(e => setError(e.message)); }, [refresh, user]);
  if (user?.role !== 'admin') return <Navigate to="/" replace />;
  const save = async (operation, notice) => {
    setBusy(true); setError(''); setMessage('');
    try { await operation(); await refresh(); setMessage(notice); }
    catch (e) { setError(e.response?.data?.error || e.message); }
    finally { setBusy(false); }
  };
  return <main className="workspace"><h1>Courses & accounts</h1>
    <p>To inspect or delete evaluation records, open <Link to="/manage-results">Manage answer sheets</Link>.</p>
    <p>Register courses, approve Google accounts, and assign upload and review responsibilities. Administrators can perform every task.</p>
    {error && <p role="alert" className="workspace-error">{error}</p>}{message && <p role="status">{message}</p>}
    <section className="workspace-panel"><h2>1. Approve faculty or administrator access</h2><p>Administrators can manage all courses and accounts. Faculty work only on assigned courses.</p>{data.bootstrap_admin && <p>Initial administrator: {data.bootstrap_admin} (managed in server settings)</p>}
      <form onInvalid={e => e.currentTarget.classList.add('show-validation')} onSubmit={e => { e.preventDefault(); e.currentTarget.classList.add('show-validation'); if (!e.currentTarget.reportValidity()) return; save(() => api.post('/access/faculty', faculty), 'Account saved. They can now sign in with Google.'); }}>
        <label>Full name *<input required maxLength={120} pattern=".*\S.*" title="Enter the account holder’s name" value={faculty.name} onChange={e => setFaculty({ ...faculty, name: e.target.value })} /></label>
        <label>Google email *<input required type="email" value={faculty.email} onChange={e => setFaculty({ ...faculty, email: e.target.value })} /></label>
        <label>Account role<select value={faculty.role} onChange={e => setFaculty({ ...faculty, role: e.target.value })}><option value="faculty">Faculty — assigned courses only</option><option value="admin">Administrator — full access</option></select></label>
        <button disabled={busy}>Save account</button>
      </form>
      {data.faculty.map(f => <p key={f.email}>{f.name} · {f.email} · {f.role === 'admin' ? 'Administrator' : 'Faculty'} · {f.active ? 'Enabled' : 'Disabled'}
        <button disabled={busy || f.email === user.email} onClick={() => save(() => api.post('/access/faculty', { ...f, role: f.role === 'admin' ? 'faculty' : 'admin' }), 'Account role updated.')}>{f.role === 'admin' ? 'Make faculty' : 'Make administrator'}</button>
        <button disabled={busy || f.email === user.email} onClick={() => save(() => api.post('/access/faculty', { ...f, active: !f.active }), 'Account access updated.')}>{f.active ? 'Disable access' : 'Enable access'}</button>
      </p>)}
    </section>
    <section className="workspace-panel"><h2>2. Register courses</h2>
      <p>Import an Excel .xlsx file with a <strong>course_code</strong> column and optional <strong>name</strong> column. Existing assignments are preserved.</p>
      <label>Import course list<input disabled={busy} type="file" accept=".xlsx" onChange={e => {
        const file = e.target.files[0]; if (!file) return;
        const body = new FormData(); body.append('file', file);
        save(() => api.post('/access/import', body), 'Course list imported. Assign faculty below.'); e.target.value = '';
      }} /></label>
      <h2>3. Assign course responsibilities</h2>
      <form onInvalid={e => e.currentTarget.classList.add('show-validation')} onSubmit={e => { e.preventDefault(); e.currentTarget.classList.add('show-validation'); if (!e.currentTarget.reportValidity()) return; save(() => api.post('/access/courses', course), 'Course and assignments saved.'); }}>
        <label>Course code *<input required pattern="[A-Za-z]{2,}[0-9]{3,}((_| |-)[A-Za-z0-9]+)*" title="Enter a course code such as FS3401 or FS3401_MSE" placeholder="FS3401" value={course.code} onChange={e => setCourse({ ...course, code: e.target.value })} /></label>
        <label>Course name (optional)<input value={course.name} onChange={e => setCourse({ ...course, name: e.target.value })} /></label>
        {['uploaders', 'reviewers'].map(field => <fieldset key={field}><legend>{field === 'uploaders' ? 'Upload and run evaluation' : 'Review, revise and verify results'}</legend>
          {!data.faculty.some(f => f.active && f.role !== 'admin') && <p>Add an active faculty account first, or leave unassigned for the administrator.</p>}
          {data.faculty.filter(f => f.active && f.role !== 'admin').map(f => <label key={f.email}><input type="checkbox" checked={course[field].includes(f.email)} onChange={e => setCourse({ ...course, [field]: e.target.checked ? [...course[field], f.email] : course[field].filter(v => v !== f.email) })} />{f.name} ({f.email})</label>)}
        </fieldset>)}<button disabled={busy}>Save course & assignments</button>
        <button type="button" onClick={() => setCourse({ code: '', name: '', uploaders: [], reviewers: [] })}>New course</button>
      </form>
    </section>
    <section className="workspace-panel"><h2>Registered courses ({data.courses.length})</h2>
      {!data.courses.length && <p>Add a course or import your Excel list to begin.</p>}
      <div className="workspace-scroll"><table><thead><tr><th>Course</th><th>Upload faculty</th><th>Review faculty</th><th>Assignment</th></tr></thead><tbody>
        {data.courses.map(c => <tr key={c._id}><td>{c._id}<br />{c.name}</td><td>{c.uploaders.join(', ') || 'Administrator'}</td><td>{c.reviewers.join(', ') || 'Administrator'}</td><td><button onClick={() => { setCourse({ code: c._id, name: c.name, uploaders: c.uploaders, reviewers: c.reviewers }); window.scrollTo({ top: 0, behavior: 'smooth' }); }}>Edit assignments</button></td></tr>)}
      </tbody></table></div>
    </section>
  </main>;
}
