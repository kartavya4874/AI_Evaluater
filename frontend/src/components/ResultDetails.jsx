import React, { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import './ResultDetails.css';

export default function ResultDetails({ result, maxMarks, onClose, onVerify, modal = false, children }) {
  const panel = useRef(null);
  useEffect(() => {
    if (!modal) return;
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    panel.current?.focus();
    return () => { document.body.style.overflow = overflow; previous?.focus(); };
  }, [modal]);
  const content = <section ref={panel} tabIndex={modal ? -1 : undefined} role={modal ? 'dialog' : undefined}
    aria-modal={modal || undefined} onKeyDown={e => {
      if (!modal) return;
      if (e.key === 'Escape') { e.stopPropagation(); onClose(); }
      if (e.key === 'Tab') {
        const controls = panel.current.querySelectorAll('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary');
        const first = controls[0], last = controls[controls.length - 1];
        if (!controls.length) { e.preventDefault(); return; }
        if (e.shiftKey && (document.activeElement === first || document.activeElement === panel.current)) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    }}
    className={`workspace-panel result-details ${modal ? 'result-details-modal' : ''}`} aria-label="Result details">
    <header className="result-details-header"><div><h2>Result details</h2>{result.roll_number && <p>{result.roll_number}</p>}</div>
    <button onClick={onClose}>Close details</button></header>
    <p>Marks: {result.marks ?? '—'} / {maxMarks} · Grade: {result.grade || '—'}</p>
    <p>{result.verified ? `Verified by ${result.verified_by || 'reviewer'}` : 'Not verified'}</p>
    {!result.verified && onVerify && <button onClick={onVerify}>Mark this result verified</button>}
    <h3>Full feedback</h3><p style={{ whiteSpace: 'pre-wrap' }}>{result.feedback || result.error?.message || 'No feedback saved.'}</p>
    {(result.question_scores || []).length > 0 && <><h3>Question scores</h3><table><thead><tr><th>Question</th><th>Marks</th><th>Feedback</th></tr></thead><tbody>
      {result.question_scores.map((q, i) => <tr key={i}><td>{q.question_id}</td><td>{q.marks_awarded}/{q.max_marks}</td><td>{q.feedback || q.reason || q.reasoning || '—'}</td></tr>)}
    </tbody></table></>}
    {['strengths', 'missing_points'].map(field => (result[field] || []).length > 0 && <div key={field}>
      <h3>{field === 'strengths' ? 'Strengths' : 'Missing points'}</h3><ul>{result[field].map((v, i) => <li key={i}>{v}</li>)}</ul></div>)}
    {result.extracted_text && <details><summary>Extracted answer text</summary><p style={{ whiteSpace: 'pre-wrap' }}>{result.extracted_text}</p></details>}
    {children}
  </section>;
  return modal ? createPortal(<div className="result-details-backdrop" data-testid="result-details-backdrop" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>{content}</div>, document.body) : content;
}
