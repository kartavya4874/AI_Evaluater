import React, { useState, useEffect } from 'react';
import { FiBarChart2, FiUsers, FiTrendingUp, FiAward, FiChevronDown, FiChevronUp, FiAlertCircle, FiEdit3, FiX, FiCheck } from 'react-icons/fi';
import { getBatchResults, updateManualEvaluation, deleteEvaluation } from '../services/api';
import './BatchResults.css';
import api from '../services/api';
import ResultDetails from '../components/ResultDetails';

const BatchResults = ({ title = 'Batch Results (Audit View)' }) => {
  const [results, setResults] = useState(null);
  const [error, setError] = useState('');
  const [expandedCourse, setExpandedCourse] = useState(null);
  const [loadingData, setLoadingData] = useState(true);
  const [selected, setSelected] = useState([]);
  const [detail, setDetail] = useState(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState('');
  const allRecords = Object.values(results?.courses || {}).flat();
  const selectedRecords = allRecords.filter(r => selected.includes(r._id));
  const verifiableRecords = selectedRecords.filter(r => r.status !== 'error' && r.marks != null);
  const deleteRecords = async records => {
    if (!records.length || !window.confirm(`Delete ${records.length} saved evaluation(s)?\n${records.map(r => r.roll_number || r._id).join(', ')}\n\nSaved marks and feedback will be permanently removed. This cannot be undone.`)) return;
    setSaving(true); setError(''); setNotice('');
    let deleted = 0;
    let failure = '';
    try {
      for (const record of records) {
        await deleteEvaluation(record._id);
        deleted += 1;
      }
    } catch (e) { failure = e.response?.data?.error || e.message; }
    finally {
      setSelected([]); setDetail(null);
      await loadResults();
      setNotice(`${deleted} saved evaluation(s) deleted.`);
      if (failure) setError(`Deletion stopped: ${failure}. Refresh and review the remaining records before retrying.`);
      setSaving(false);
    }
  };
  const verify = async records => {
    setSaving(true); setError('');
    try {
      await api.post('/workspace/verify', { source: 'legacy', items: records.map(r => ({ id: r._id, revision: r.verification_revision })) });
      setSelected([]); setDetail(null); await loadResults();
    } catch (e) { setError(e.response?.data?.error || e.message); }
    finally { setSaving(false); }
  };
  const exportResults = async course => {
    try {
      const response = await api.get('/workspace/export', { params: { source: course ? 'legacy' : undefined, course_code: course || undefined }, responseType: 'blob' });
      const url = URL.createObjectURL(response.data);
      const a = document.createElement('a'); a.href = url; a.download = `${course || 'combined'}-verified-results.xlsx`; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { setError(e.message); }
  };
  
  // Review Queue State
  const [filterReview, setFilterReview] = useState(false);
  const [selectedEval, setSelectedEval] = useState(null); // The eval object being manually graded
  const [manualMarks, setManualMarks] = useState('');
  const [manualFeedback, setManualFeedback] = useState('');

  useEffect(() => {
    loadResults();
  }, []);

  const loadResults = async () => {
    try {
      setLoadingData(true);
      setError('');
      const response = await getBatchResults();
      setResults(response);
      setExpandedCourse(current => current || Object.keys(response.courses || {})[0] || null);
    } catch (err) {
      setError(err.response?.data?.error || err.message || 'Failed to load results');
    } finally {
      setLoadingData(false);
    }
  };

  const handleManualGradeSubmit = async () => {
    if (!selectedEval || manualMarks === '') return;
    try {
      await updateManualEvaluation(selectedEval._id, manualMarks, manualFeedback);
      await loadResults();
      setSelectedEval(null);
    } catch (err) {
      alert("Failed to save manual grade: " + (err.response?.data?.error || err.message));
    }
  };

  const getGradeColor = (grade) => {
    const colors = {
      'A+': '#00c853', 'A': '#2e7d32', 'B+': '#558b2f',
      'B': '#f9a825', 'C': '#ef6c00', 'D': '#e53935', 'F': '#b71c1c'
    };
    return colors[grade] || '#757575';
  };

  const getCourseStats = (evaluations) => {
    if (!evaluations || evaluations.length === 0) return null;
    const marks = evaluations.filter(e => e.verified && !e.needs_review && e.status !== 'error' && e.marks != null).map(e => e.marks);
    if (!marks.length) return { count: evaluations.length, avg: '—', max: '—', min: '—', maxMarks: evaluations[0]?.max_marks || 100 };
    return {
      count: evaluations.length,
      avg: (marks.reduce((a, b) => a + b, 0) / marks.length).toFixed(1),
      max: Math.max(...marks),
      min: Math.min(...marks),
      maxMarks: evaluations[0]?.max_marks || 100
    };
  };

  if (loadingData) {
    return (
      <div className="batch-results">
        <div className="batch-results-container">
          <div className="loading-state">
            <div className="loading-spinner-lg"></div>
            <p>Loading batch results...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="batch-results">
      <div className="batch-results-container">
        <div className="results-header">
          <FiBarChart2 size={28} className="results-icon" />
          <div>
            <h1>{title}</h1>
            <p className="results-subtitle">
              {results?.total_evaluations || 0} total evaluations across{' '}
              {Object.keys(results?.courses || {}).length} courses
            </p>
          </div>
          <div className="header-actions" style={{ marginLeft: 'auto' }}>
            <button className="filter-btn" onClick={loadResults}>Refresh previous results</button>
            <button 
              className={`filter-btn ${filterReview ? 'active' : ''}`}
              aria-pressed={filterReview}
              onClick={() => { setFilterReview(!filterReview); setSelected([]); }}
              style={{
                display: 'flex', alignItems: 'center', gap: '0.5rem',
                background: filterReview ? 'rgba(229, 57, 53, 0.2)' : 'rgba(255,255,255,0.05)',
                border: `1px solid ${filterReview ? '#e53935' : 'rgba(255,255,255,0.1)'}`,
                padding: '0.6rem 1rem', borderRadius: '8px', color: '#fff', cursor: 'pointer'
              }}
            >
              <FiAlertCircle color={filterReview ? '#ef5350' : '#fff'} />
              {filterReview ? 'Showing Needs Review' : 'Filter Needs Review'}
            </button>
          </div>
        </div>

        {error && <div className="error-alert">{error}</div>}
        {notice && <p role="status">{notice}</p>}
        {detail && <ResultDetails modal result={detail} maxMarks={detail.max_marks} onClose={() => setDetail(null)} onVerify={saving || detail.status === 'error' ? null : () => verify([detail])} />}
        <div className="saved-results-toolbar" aria-label="Saved result actions">
          <span className="selection-count">{selected.length ? `${selected.length} selected` : 'Select rows to verify or delete'}</span>
          <div className="header-actions">
          <button disabled={saving} onClick={() => setSelected(allRecords.filter(r => !filterReview || r.needs_review || r.status === 'error').map(r => r._id))}>Select all saved results</button>
          <button disabled={saving || !selected.length} onClick={() => setSelected([])}>Clear selection</button>
          <button className="saved-primary" disabled={saving || !verifiableRecords.length} onClick={() => verify(verifiableRecords)}>Mark selected verified ({verifiableRecords.length})</button>
          <button className="saved-danger" disabled={saving || !selectedRecords.length} onClick={() => deleteRecords(selectedRecords)}>Delete selected saved results ({selectedRecords.length})</button>
          <button onClick={() => exportResults()}>Download verified workbook</button>
          </div>
        </div>
        {results?.total_evaluations > 0 && <p className="saved-results-help">Open a result to read the full feedback. Select rows to verify marks or delete records. Only verified marks are included in course statistics and exports.</p>}

        {(!results || results.total_evaluations === 0) && !error && (
          <div className="empty-state">
            <FiBarChart2 size={48} />
            <h3>No previous batch results found</h3>
            <p>This section shows evaluations saved by the earlier batch workflow. New evaluations appear in the workspace.</p>
          </div>
        )}

        {results && Object.entries(results.courses || {}).map(([courseCode, evaluations]) => {
          const stats = getCourseStats(evaluations);
          const isExpanded = expandedCourse === courseCode;

          return (
            <div className="course-card" key={courseCode}>
              <div
                className="course-card-header"
                role="button" tabIndex={0} aria-expanded={isExpanded} aria-label={`Toggle ${courseCode}`}
                onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpandedCourse(isExpanded ? null : courseCode); } }}
                onClick={() => setExpandedCourse(isExpanded ? null : courseCode)}
              >
                <div className="course-info">
                  <h2 className="course-code-title">{courseCode}</h2>
                  {stats && (
                    <div className="course-stats-row">
                      <span className="mini-stat">
                        <FiUsers size={14} /> {stats.count} students
                      </span>
                      <span className="mini-stat">
                        <FiTrendingUp size={14} /> Avg: {stats.avg}/{stats.maxMarks}
                      </span>
                      <span className="mini-stat">
                        <FiAward size={14} /> Best: {stats.max}/{stats.maxMarks}
                      </span>
                    </div>
                  )}
                </div>
                <div className="expand-icon">
                  {isExpanded ? <FiChevronUp size={20} /> : <FiChevronDown size={20} />}
                </div>
              </div>

              {isExpanded && (
                <div className="course-card-body">
                  <div className="course-results-toolbar"><span>Average and best marks use verified results only.</span><button onClick={() => exportResults(courseCode)}>Download verified {courseCode}</button></div>
                  <table className="results-table">
                    <thead>
                      <tr>
                        <th>Select</th>
                        <th>#</th>
                        <th>Roll Number</th>
                        <th>Marks</th>
                        <th>%</th>
                        <th>Grade</th>
                        <th className="feedback-col">Feedback</th>
                        <th>Status</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filterReview && !evaluations.some(ev => ev.needs_review || ev.status === 'error') && <tr><td colSpan={9} className="saved-empty">No results need review in this course.</td></tr>}
                      {evaluations
                         .filter(ev => filterReview ? ev.needs_review || ev.status === 'error' : true)
                         .map((ev, idx) => (
                        <tr key={ev._id || idx} className={ev.needs_review || ev.status === 'error' ? 'row-alert' : ''}>
                          <td><input type="checkbox" aria-label={`Select saved ${ev.roll_number}`} disabled={saving} checked={selected.includes(ev._id)} onChange={e => setSelected(old => e.target.checked ? [...old, ev._id] : old.filter(id => id !== ev._id))} /></td>
                          <td>{idx + 1}</td>
                          <td className="roll-num">{ev.roll_number || 'N/A'}</td>
                          <td className="marks-col">
                            {ev.status === 'error' || ev.marks == null ? '—' : `${ev.marks}/${ev.max_marks || 100}`}
                            {ev.needs_review && ev.status !== 'error' && ev.marks != null && <small style={{ display: 'block' }}>Unverified saved score</small>}
                          </td>
                          <td>{ev.status === 'error' || ev.percentage == null ? '—' : `${ev.percentage}%`}</td>
                          <td>
                            {ev.needs_review ? (
                              <span className="grade-pill" style={{ backgroundColor: '#e53935' }}>Needs review</span>
                            ) : (
                              <span className="grade-pill" style={{ backgroundColor: getGradeColor(ev.grade) }}>
                                {ev.grade || 'N/A'}
                              </span>
                            )}
                          </td>
                          <td className="feedback-col">
                            {ev.status === 'completed_manually' && <span style={{color: '#b388ff', fontSize: '0.8rem', display: 'block'}}>(Manually Graded)</span>}
                            {ev.feedback ? ev.feedback.length > 100 ? ev.feedback.substring(0, 100) + '…' : ev.feedback : 'No feedback'}
                          </td>
                          <td><span className={`verification-badge ${ev.verified ? 'is-verified' : 'is-pending'}`}>{ev.verified ? 'Verified' : 'Not verified'}</span></td>
                          <td><div className="saved-row-actions">
                            <button className="saved-details" onClick={() => setDetail(ev)}>View details</button>
                            <button className="saved-danger" disabled={saving} aria-label={`Delete saved ${ev.roll_number}`} onClick={() => deleteRecords([ev])}>Delete</button>
                            {(ev.needs_review || ev.status === 'error') && (
                              <button 
                                className="btn-manual-grade"
                                onClick={() => {
                                  setSelectedEval({...ev, course: courseCode});
                                  setManualMarks('');
                                  setManualFeedback('Manually Reviewed');
                                }}
                                style={{
                                  background: '#7c4dff', border: 'none', padding: '0.4rem 0.8rem',
                                  borderRadius: '6px', color: '#fff', cursor: 'pointer', display: 'flex', gap: '0.4rem', alignItems: 'center'
                                }}
                              >
                                <FiEdit3 /> Grade
                              </button>
                            )}
                          </div></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          );
        })}
      </div>
      {/* Manual Grading Modal */}
      {selectedEval && (
        <div className="modal-overlay" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.7)', zIndex: 1000, display: 'flex',
          justifyContent: 'center', alignItems: 'center', backdropFilter: 'blur(5px)'
        }}>
          <div className="modal-content" style={{
            background: '#1a1a3e', border: '1px solid #7c4dff', padding: '2rem',
            borderRadius: '16px', width: '90%', maxWidth: '500px',
            color: '#fff', boxShadow: '0 10px 40px rgba(0,0,0,0.5)'
          }}>
            <h2 style={{marginTop: 0, display: 'flex', alignItems: 'center', gap: '0.5rem'}}>
              <FiEdit3 /> Manual Grading (Review Queue)
            </h2>
            <p style={{color: 'rgba(255,255,255,0.6)'}}>
              Student Roll #: <strong>{selectedEval.roll_number}</strong> <br/>
              Course: <strong>{selectedEval.course}</strong>
            </p>
            
            <div style={{background: 'rgba(229,57,53,0.1)', padding: '1rem', borderRadius: '8px', marginBottom: '1.5rem', border: '1px solid rgba(229,57,53,0.3)'}}>
              <strong style={{color: '#ef5350'}}>AI Reason for Failure:</strong>
              <p style={{margin: '0.5rem 0 0 0', fontSize: '0.9rem'}}>{selectedEval.feedback || selectedEval.error || 'Unknown Error'}</p>
            </div>

            <div className="form-group" style={{marginBottom: '1rem'}}>
              <label style={{display: 'block', marginBottom: '0.5rem'}}>Marks Awarded (Max: {selectedEval.max_marks || 100})</label>
              <input 
                type="number" 
                value={manualMarks}
                onChange={e => setManualMarks(e.target.value)}
                autoFocus
                style={{
                  width: '100%', padding: '0.8rem', background: 'rgba(255,255,255,0.05)',
                  border: '1px solid rgba(255,255,255,0.2)', color: '#fff', borderRadius: '8px'
                }}
              />
            </div>
            
            <div className="form-group" style={{marginBottom: '1.5rem'}}>
              <label style={{display: 'block', marginBottom: '0.5rem'}}>Feedback Note</label>
              <textarea 
                value={manualFeedback}
                onChange={e => setManualFeedback(e.target.value)}
                style={{
                  width: '100%', padding: '0.8rem', background: 'rgba(255,255,255,0.05)',
                  border: '1px solid rgba(255,255,255,0.2)', color: '#fff', borderRadius: '8px', minHeight: '80px'
                }}
              />
            </div>

            <div style={{display: 'flex', gap: '1rem', justifyContent: 'flex-end'}}>
              <button 
                onClick={() => setSelectedEval(null)}
                style={{
                  padding: '0.8rem 1.5rem', background: 'transparent', color: '#fff',
                  border: '1px solid rgba(255,255,255,0.2)', borderRadius: '8px', cursor: 'pointer'
                }}
              >
                <FiX /> Cancel
              </button>
              <button 
                onClick={handleManualGradeSubmit}
                disabled={manualMarks === ''}
                style={{
                  padding: '0.8rem 1.5rem', background: '#00c853', color: '#fff',
                  border: 'none', borderRadius: '8px', cursor: manualMarks === '' ? 'not-allowed' : 'pointer',
                  opacity: manualMarks === '' ? 0.5 : 1, display: 'flex', alignItems: 'center', gap: '0.4rem'
                }}
              >
                <FiCheck /> Save Manual Grade
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default BatchResults;
