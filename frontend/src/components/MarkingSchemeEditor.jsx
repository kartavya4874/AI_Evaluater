import React, { useState } from 'react';
import api from '../services/api';

const emptyQuestion = () => ({ question_id: '', max_marks: '', group: '', choose: '', selection: 'exact' });

export default function MarkingSchemeEditor() {
  const [course, setCourse] = useState('');
  const [examType, setExamType] = useState('end_sem');
  const [maximum, setMaximum] = useState('');
  const [questions, setQuestions] = useState([emptyQuestion()]);
  const [loaded, setLoaded] = useState(false);
  const [paper, setPaper] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const act = async operation => {
    setBusy(true); setError(''); setNotice('');
    try { await operation(); } catch (e) { setError(e.response?.data?.error || e.message); }
    finally { setBusy(false); }
  };
  const reset = () => { setLoaded(false); setMaximum(''); setQuestions([emptyQuestion()]); setPaper(false); setNotice(''); setError(''); };
  const identity = { course_code: course.trim().toUpperCase(), exam_type: examType };
  const update = (index, field, value) => setQuestions(old => old.map((q, i) => i === index ? { ...q, [field]: value } : q));
  const upload = (file, endpoint) => act(async () => {
    const body = new FormData();
    body.append('file', file); body.append('course_code', identity.course_code); body.append('exam_type', examType); body.append('max_marks', maximum);
    const response = await api.post(endpoint, body);
    if (response.data.scheme) {
      setQuestions(response.data.scheme.questions); setMaximum(response.data.scheme.max_marks);
      setNotice('Excel preview loaded. Check the allocations below, then Save marking scheme.');
    } else { setPaper(true); setNotice('Default question paper saved for this course and examination type.'); }
  });
  return <section className="workspace-panel" aria-label="Fallback marking schemes"><h2>Fallback marking schemes</h2>
    <p>Each course has separate End Sem and MST settings. Evaluation uses answer-key marks first, the matching question paper second, and these administrator allocations last. Existing results are unchanged; retry affected sheets after saving.</p>
    {error && <p role="alert" className="workspace-error">{error}</p>}{notice && <p role="status">{notice}</p>}
    <label>Marking course code<input disabled={busy} value={course} onChange={e => { setCourse(e.target.value); reset(); }} placeholder="FS3401" maxLength={80} /></label>
    <label>Marking examination type<select disabled={busy} value={examType} onChange={e => { setExamType(e.target.value); reset(); }}><option value="end_sem">End Sem</option><option value="mst">MST</option></select></label>
    <button disabled={busy || !course.trim()} onClick={() => act(async () => {
      const scheme = (await api.get('/access/marking-scheme', { params: identity })).data.scheme;
      setMaximum(scheme.max_marks ?? ''); setQuestions(scheme.questions?.length ? scheme.questions : [emptyQuestion()]); setPaper(scheme.has_question_paper); setLoaded(true);
      setNotice(scheme.questions?.length ? 'Saved scheme loaded.' : 'No saved allocations. Enter them below.');
    })}>Load course scheme</button>
    {loaded && <>
      <p><strong>{identity.course_code} — {examType === 'mst' ? 'MST' : 'End Sem'}</strong></p>
      <label>Default question paper (PDF)<input disabled={busy} type="file" accept=".pdf" onChange={e => { const file = e.target.files[0]; if (file) upload(file, '/access/marking-scheme/paper'); e.target.value = ''; }} /></label>
      <p>{paper ? 'A default question paper is saved.' : 'No default paper saved; the uploaded course-folder paper is used if available.'}</p>
      <label>Scheme maximum marks<input type="number" min="0.01" max="1000" step="any" disabled={busy} value={maximum} onChange={e => setMaximum(e.target.value)} /></label>
      <p>Excel columns, in order: <code>question_id, max_marks, group, choose, selection</code>. One question per row. Leave group, choose and selection blank for compulsory questions. IDs must match the answer key exactly. Import previews the file before saving.</p>
      <label>Import marking Excel<input disabled={busy || !maximum} type="file" accept=".xlsx" onChange={e => { const file = e.target.files[0]; if (file) upload(file, '/access/marking-scheme/import'); e.target.value = ''; }} /></label>
      <div className="workspace-scroll"><table><thead><tr><th>Question ID</th><th>Marks</th><th>Optional group</th><th>Choose</th><th>Selection</th><th>Action</th></tr></thead><tbody>
        {questions.map((q, i) => <tr key={i}>
          <td><input aria-label={`Question ID ${i + 1}`} disabled={busy} value={q.question_id} onChange={e => update(i, 'question_id', e.target.value)} /></td>
          <td><input aria-label={`Marks ${i + 1}`} disabled={busy} type="number" min="0.01" step="any" value={q.max_marks} onChange={e => update(i, 'max_marks', e.target.value)} /></td>
          <td><input aria-label={`Group ${i + 1}`} disabled={busy} value={q.group || ''} onChange={e => update(i, 'group', e.target.value)} /></td>
          <td><input aria-label={`Choose ${i + 1}`} disabled={busy || !q.group} type="number" min="1" value={q.choose || ''} onChange={e => update(i, 'choose', e.target.value)} /></td>
          <td><select aria-label={`Selection ${i + 1}`} disabled={busy || !q.group} value={q.selection || 'exact'} onChange={e => update(i, 'selection', e.target.value)}><option value="exact">Exact count</option><option value="best">Highest marks</option><option value="first">First answers</option></select></td>
          <td><button disabled={busy || questions.length === 1} onClick={() => setQuestions(old => old.filter((_, n) => n !== i))}>Remove question {i + 1}</button></td>
        </tr>)}
      </tbody></table></div>
      <p>Optional questions in the same group must share marks, choose count and selection rule. Compulsory marks plus selected optional marks must equal the scheme maximum.</p>
      <button disabled={busy || questions.length >= 200} onClick={() => setQuestions(old => [...old, emptyQuestion()])}>Add question</button>
      <button disabled={busy || !maximum} onClick={() => act(async () => {
        await api.post('/access/marking-scheme', { ...identity, max_marks: Number(maximum), questions: questions.map(q => ({ ...q, max_marks: Number(q.max_marks), choose: q.group ? Number(q.choose) : undefined })) });
        setNotice('Marking scheme saved. Retry affected sheets from Batch evaluation.');
      })}>Save marking scheme</button>
    </>}
  </section>;
}
