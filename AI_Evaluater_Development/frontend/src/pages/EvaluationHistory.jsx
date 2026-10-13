import React, { useState, useEffect } from 'react';
import { FiEye, FiDownload, FiX, FiChevronDown, FiTrash2 } from 'react-icons/fi';
import { getEvaluations, deleteEvaluation } from '../services/api';
import '../pages/EvaluationHistory.css';

function EvaluationHistory() {
  const [evaluations, setEvaluations] = useState([]);
  const [filteredEvaluations, setFilteredEvaluations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedEvaluation, setSelectedEvaluation] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  
  // Filter states
  const [searchStudent, setSearchStudent] = useState('');
  const [searchRollNo, setSearchRollNo] = useState('');
  const [selectedTeacher, setSelectedTeacher] = useState('all');
  const [dateFilter, setDateFilter] = useState('all');
  
  // Extracted teachers list
  const [teachers, setTeachers] = useState([]);

  useEffect(() => {
    fetchEvaluations();
  }, []);

  const fetchEvaluations = async () => {
    try {
      setLoading(true);
      setError('');
      console.log('Fetching evaluations...');
      const data = await getEvaluations();
      console.log('Raw API response:', data);
      
      // Handle both array response and object response
      const evaluations = Array.isArray(data) ? data : (data.evaluations || data || []);
      console.log('Processed evaluations:', evaluations);
      console.log('Number of evaluations:', evaluations.length);
      
      setEvaluations(evaluations);
      
      // Extract unique teachers
      const uniqueTeachers = [...new Set(evaluations.map(e => e.teacher_name).filter(t => t))];
      setTeachers(uniqueTeachers);
      
      setFilteredEvaluations(evaluations);
      setError('');
    } catch (err) {
      console.error('Error fetching evaluations:', err);
      console.error('Error details:', err.response?.data);
      setError(err.response?.data?.error || err.message || 'Failed to load evaluation history');
      setEvaluations([]);
      setFilteredEvaluations([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    applyFilters();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchStudent, searchRollNo, selectedTeacher, dateFilter, evaluations]);

  const applyFilters = () => {
    let filtered = [...evaluations];

    // Student name filter
    if (searchStudent.trim()) {
      filtered = filtered.filter(e =>
        e.student_name?.toLowerCase().includes(searchStudent.toLowerCase())
      );
    }

    // Roll number filter
    if (searchRollNo.trim()) {
      filtered = filtered.filter(e =>
        e.student_rollno?.toString().includes(searchRollNo)
      );
    }

    // Teacher filter
    if (selectedTeacher !== 'all') {
      filtered = filtered.filter(e => e.teacher_name === selectedTeacher);
    }

    // Date filter
    if (dateFilter !== 'all') {
      const today = new Date();
      const startDate = new Date();

      if (dateFilter === 'today') {
        startDate.setHours(0, 0, 0, 0);
      } else if (dateFilter === 'week') {
        startDate.setDate(today.getDate() - 7);
      } else if (dateFilter === 'month') {
        startDate.setMonth(today.getMonth() - 1);
      }

      filtered = filtered.filter(e => {
        const evalDate = new Date(e.created_at || e.date);
        return evalDate >= startDate;
      });
    }

    setFilteredEvaluations(filtered);
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-IN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getGradeColor = (grade) => {
    const gradeColors = {
      'A+': '#10b981',
      'A': '#10b981',
      'B+': '#3b82f6',
      'B': '#3b82f6',
      'C+': '#f59e0b',
      'C': '#f59e0b',
      'D': '#ef4444',
      'F': '#ef4444'
    };
    return gradeColors[grade] || 'var(--text-secondary)';
  };

  const handleDownloadEvaluation = (evaluation) => {
    // Create HTML content for PDF
    const htmlContent = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="UTF-8">
        <title>Evaluation Report</title>
        <style>
          * { margin: 0; padding: 0; box-sizing: border-box; }
          body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
          .container { max-width: 800px; margin: 0 auto; padding: 40px 20px; }
          .header { text-align: center; border-bottom: 3px solid #6366f1; padding-bottom: 20px; margin-bottom: 30px; }
          .header h1 { font-size: 28px; color: #1f2937; margin-bottom: 5px; }
          .header p { color: #6b7280; font-size: 14px; }
          .section { margin-bottom: 30px; }
          .section h2 { font-size: 18px; color: #1f2937; margin-bottom: 15px; border-left: 4px solid #6366f1; padding-left: 10px; }
          .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px; }
          .info-item { background: #f9fafb; padding: 12px; border-radius: 6px; }
          .info-item label { display: block; font-weight: bold; color: #6366f1; font-size: 12px; margin-bottom: 5px; }
          .info-item value { display: block; font-size: 14px; color: #374151; }
          .results-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-bottom: 20px; }
          .result-card { background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white; padding: 20px; border-radius: 8px; text-align: center; }
          .result-label { font-size: 12px; opacity: 0.9; margin-bottom: 8px; }
          .result-value { font-size: 24px; font-weight: bold; }
          .feedback-box { background: #f0f9ff; border-left: 4px solid #0ea5e9; padding: 15px; border-radius: 6px; font-size: 14px; line-height: 1.6; }
          .points-list { list-style: none; padding: 0; }
          .points-list li { padding: 10px 0; padding-left: 20px; position: relative; font-size: 14px; }
          .points-list li:before { content: "✓"; position: absolute; left: 0; color: #10b981; font-weight: bold; }
          .improvements li:before { content: "→"; color: #f59e0b; }
          .file-info { background: #f3f4f6; padding: 12px; border-radius: 6px; font-size: 14px; margin: 10px 0; }
          .footer { text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #9ca3af; font-size: 12px; }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <h1>Evaluation Report</h1>
            <p>AI Examiner - Assessment Result</p>
          </div>

          <div class="section">
            <h2>Student Information</h2>
            <div class="info-grid">
              <div class="info-item">
                <label>Student Name</label>
                <value>${evaluation.student_name || 'N/A'}</value>
              </div>
              <div class="info-item">
                <label>Roll Number</label>
                <value>${evaluation.student_rollno || 'N/A'}</value>
              </div>
              <div class="info-item">
                <label>Teacher</label>
                <value>${evaluation.teacher_name || 'N/A'}</value>
              </div>
              <div class="info-item">
                <label>Date</label>
                <value>${formatDate(evaluation.created_at || evaluation.date)}</value>
              </div>
            </div>
          </div>

          <div class="section">
            <h2>Evaluation Results</h2>
            <div class="results-grid">
              <div class="result-card">
                <div class="result-label">Marks Obtained</div>
                <div class="result-value">${evaluation.marks_awarded || evaluation.marks || '0'} / ${evaluation.max_marks || '0'}</div>
              </div>
              <div class="result-card">
                <div class="result-label">Percentage</div>
                <div class="result-value">${evaluation.percentage || '0'}%</div>
              </div>
              <div class="result-card">
                <div class="result-label">Grade</div>
                <div class="result-value">${evaluation.grade || 'N/A'}</div>
              </div>
            </div>
          </div>

          ${evaluation.feedback ? `
          <div class="section">
            <h2>Feedback</h2>
            <div class="feedback-box">${evaluation.feedback}</div>
          </div>
          ` : ''}

          ${evaluation.strengths && evaluation.strengths.length > 0 ? `
          <div class="section">
            <h2>Strengths</h2>
            <ul class="points-list">
              ${evaluation.strengths.map(s => `<li>${s}</li>`).join('')}
            </ul>
          </div>
          ` : ''}

          ${evaluation.missing_points && evaluation.missing_points.length > 0 ? `
          <div class="section">
            <h2>Areas for Improvement</h2>
            <ul class="points-list improvements">
              ${evaluation.missing_points.map(p => `<li>${p}</li>`).join('')}
            </ul>
          </div>
          ` : ''}

          <div class="section">
            <h2>Answer Files</h2>
            <div class="file-info"><strong>Model Answer:</strong> ${getDisplayName(evaluation.model_answer)}</div>
            <div class="file-info"><strong>Student Answer:</strong> ${getDisplayName(evaluation.student_answer)}</div>
          </div>

          <div class="footer">
            <p>Generated on ${new Date().toLocaleString('en-IN')}</p>
            <p>AI Examiner - Automated Assessment System</p>
          </div>
        </div>
      </body>
      </html>
    `;

    // Create a blob from the HTML content
    const blob = new Blob([htmlContent], { type: 'text/html' });
    const url = window.URL.createObjectURL(blob);
    
    // Create an iframe to print to PDF
    const iframe = document.createElement('iframe');
    iframe.style.display = 'none';
    iframe.src = url;
    document.body.appendChild(iframe);
    
    // Print to PDF after iframe loads
    iframe.onload = () => {
      setTimeout(() => {
        iframe.contentWindow.print();
        // Clean up
        setTimeout(() => {
          document.body.removeChild(iframe);
          window.URL.revokeObjectURL(url);
        }, 100);
      }, 250);
    };
  };

  const handleViewEvaluation = (evaluation) => {
    setSelectedEvaluation(evaluation);
  };

  const getDisplayName = (text) => {
    if (!text) return 'N/A';
    // Check if it's a filename (ends with extension like .pdf, .txt, etc.)
    if (/\.\w+$/.test(text.trim())) {
      return text.trim();
    }
    // If it's full text content, show "Text Content" instead
    return 'Text Content';
  };

  const handleDeleteEvaluation = async (evaluationId) => {
    if (!window.confirm('Are you sure you want to delete this evaluation? This action cannot be undone.')) {
      return;
    }

    try {
      await deleteEvaluation(evaluationId);
      // Remove the deleted evaluation from the state
      setEvaluations(evaluations.filter(e => e._id !== evaluationId));
      setFilteredEvaluations(filteredEvaluations.filter(e => e._id !== evaluationId));
      setError('');
    } catch (err) {
      console.error('Error deleting evaluation:', err);
      setError(err.response?.data?.error || err.message || 'Failed to delete evaluation');
    }
  };

  if (loading) {
    return (
      <div className="evaluation-history">
        <div className="loading-message">Loading evaluation history...</div>
      </div>
    );
  }

  return (
    <div className="evaluation-history">
      <div className="history-container">
        <div className="page-title">Evaluation History</div>

        {error && <div className="error-alert">{error}</div>}

        {/* Filters */}
        <div className="filters-section">
          <div className="filter-group">
            <label>Search Student Name</label>
            <input
              type="text"
              placeholder="Enter student name..."
              value={searchStudent}
              onChange={(e) => setSearchStudent(e.target.value)}
              className="filter-input"
            />
          </div>

          <div className="filter-group">
            <label>Roll Number</label>
            <input
              type="text"
              placeholder="Enter roll number..."
              value={searchRollNo}
              onChange={(e) => setSearchRollNo(e.target.value)}
              className="filter-input"
            />
          </div>

          <div className="filter-group">
            <label>Teacher</label>
            <select
              value={selectedTeacher}
              onChange={(e) => setSelectedTeacher(e.target.value)}
              className="filter-input"
            >
              <option value="all">All Teachers</option>
              {teachers.map(teacher => (
                <option key={teacher} value={teacher}>{teacher}</option>
              ))}
            </select>
          </div>

          <div className="filter-group">
            <label>Date Range</label>
            <select
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value)}
              className="filter-input"
            >
              <option value="all">All Time</option>
              <option value="today">Today</option>
              <option value="week">Last 7 Days</option>
              <option value="month">Last 30 Days</option>
            </select>
          </div>
        </div>

        {/* Results Count */}
        <div className="results-info">
          <p>Showing <span>{filteredEvaluations.length}</span> evaluation{filteredEvaluations.length !== 1 ? 's' : ''}</p>
        </div>

        {/* Evaluations List */}
        {filteredEvaluations.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📋</div>
            <p>No evaluations found</p>
            <small>Try adjusting your filters or perform a new evaluation</small>
          </div>
        ) : (
          <div className="evaluations-list">
            {filteredEvaluations.map((evaluation) => (
              <div
                key={evaluation._id}
                className={`evaluation-card ${expandedId === evaluation._id ? 'expanded' : ''}`}
              >
                <div
                  className="card-header"
                  onClick={() => setExpandedId(expandedId === evaluation._id ? null : evaluation._id)}
                >
                  <div className="header-content">
                    <div className="student-info">
                      <h3>{evaluation.student_name || 'Unknown Student'}</h3>
                      <div className="info-row">
                        <span className="roll-badge">Roll: {evaluation.student_rollno || 'N/A'}</span>
                        <span className="teacher-badge">Teacher: {evaluation.teacher_name || 'N/A'}</span>
                      </div>
                    </div>
                  </div>

                  <div className="marks-display">
                    <div className="marks-value">
                      {evaluation.marks_awarded || evaluation.marks || '0'} / {evaluation.max_marks || 'N/A'}
                    </div>
                    <div
                      className="grade-badge"
                      style={{ borderColor: getGradeColor(evaluation.grade || 'N/A') }}
                    >
                      {evaluation.grade || 'N/A'}
                    </div>
                  </div>

                  <button
                    className={`expand-btn ${expandedId === evaluation._id ? 'active' : ''}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      setExpandedId(expandedId === evaluation._id ? null : evaluation._id);
                    }}
                  >
                    <FiChevronDown />
                  </button>
                </div>

                <div className="card-meta">
                  <span className="date">{formatDate(evaluation.created_at || evaluation.date)}</span>
                </div>

                {expandedId === evaluation._id && (
                  <div className="card-details">
                    <div className="details-section">
                      <h4>Model Answer File</h4>
                      <p className="file-name"><strong>File:</strong> {evaluation.model_answer || 'N/A'}</p>
                    </div>

                    <div className="details-section">
                      <h4>Student Answer File</h4>
                      <p className="file-name"><strong>File:</strong> {evaluation.student_answer || 'N/A'}</p>
                    </div>

                    {evaluation.feedback && (
                      <div className="details-section">
                        <h4>Feedback</h4>
                        <p className="feedback-text">{evaluation.feedback}</p>
                      </div>
                    )}

                    {evaluation.strengths && (
                      <div className="details-section">
                        <h4>Strengths</h4>
                        <ul className="points-list">
                          {(Array.isArray(evaluation.strengths) 
                            ? evaluation.strengths 
                            : evaluation.strengths.split('\n').filter(s => s.trim())
                          ).map((strength, idx) => (
                            <li key={idx}>{strength}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {evaluation.missing_points && (
                      <div className="details-section">
                        <h4>Points to Improve</h4>
                        <ul className="points-list">
                          {(Array.isArray(evaluation.missing_points)
                            ? evaluation.missing_points
                            : evaluation.missing_points.split('\n').filter(p => p.trim())
                          ).map((point, idx) => (
                            <li key={idx}>{point}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    <div className="card-actions">
                      <button
                        className="action-btn view-btn"
                        onClick={() => handleViewEvaluation(evaluation)}
                        title="View Details"
                      >
                        <FiEye /> View Full Details
                      </button>
                      <button
                        className="action-btn download-btn"
                        onClick={() => handleDownloadEvaluation(evaluation)}
                        title="Download Evaluation"
                      >
                        <FiDownload /> Download
                      </button>
                      <button
                        className="action-btn delete-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteEvaluation(evaluation._id);
                        }}
                        title="Delete Evaluation"
                      >
                        <FiTrash2 /> Delete
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Modal for full evaluation details */}
      {selectedEvaluation && (
        <div className="modal-overlay" onClick={() => setSelectedEvaluation(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Evaluation Details</h2>
              <button
                className="close-btn"
                onClick={() => setSelectedEvaluation(null)}
              >
                <FiX />
              </button>
            </div>

            <div className="modal-body">
              <div className="detail-section">
                <h3>Student Information</h3>
                <div className="info-grid">
                  <div className="info-item">
                    <label>Name</label>
                    <value>{selectedEvaluation.student_name || 'N/A'}</value>
                  </div>
                  <div className="info-item">
                    <label>Roll Number</label>
                    <value>{selectedEvaluation.student_rollno || 'N/A'}</value>
                  </div>
                  <div className="info-item">
                    <label>Teacher</label>
                    <value>{selectedEvaluation.teacher_name || 'N/A'}</value>
                  </div>
                  <div className="info-item">
                    <label>Date</label>
                    <value>{formatDate(selectedEvaluation.created_at || selectedEvaluation.date)}</value>
                  </div>
                </div>
              </div>

              <div className="detail-section">
                <h3>Evaluation Results</h3>
                <div className="results-grid">
                  <div className="result-card">
                    <div className="result-label">Marks Obtained</div>
                    <div className="result-value">{selectedEvaluation.marks || '0'}</div>
                  </div>
                  <div className="result-card">
                    <div className="result-label">Grade</div>
                    <div className="result-value" style={{ color: getGradeColor(selectedEvaluation.grade || 'N/A') }}>
                      {selectedEvaluation.grade || 'N/A'}
                    </div>
                  </div>
                </div>
              </div>

              <div className="detail-section">
                <h3>Answers</h3>
                <div className="answer-comparison">
                  <div className="answer-box">
                    <h4>Model Answer</h4>
                    <p className="file-name"><strong>File/Content:</strong> {getDisplayName(selectedEvaluation.model_answer)}</p>
                  </div>
                  <div className="answer-box">
                    <h4>Student Answer</h4>
                    <p className="file-name"><strong>File/Content:</strong> {getDisplayName(selectedEvaluation.student_answer)}</p>
                  </div>
                </div>
              </div>

              {selectedEvaluation.feedback && (
                <div className="detail-section">
                  <h3>Feedback</h3>
                  <p className="feedback-box">{selectedEvaluation.feedback}</p>
                </div>
              )}

              {selectedEvaluation.strengths && (
                <div className="detail-section">
                  <h3>Strengths</h3>
                  <ul className="points-list">
                    {(Array.isArray(selectedEvaluation.strengths)
                      ? selectedEvaluation.strengths
                      : selectedEvaluation.strengths.split('\n').filter(s => s.trim())
                    ).map((strength, idx) => (
                      <li key={idx}>{strength}</li>
                    ))}
                  </ul>
                </div>
              )}

              {selectedEvaluation.missing_points && (
                <div className="detail-section">
                  <h3>Points to Improve</h3>
                  <ul className="points-list">
                    {(Array.isArray(selectedEvaluation.missing_points)
                      ? selectedEvaluation.missing_points
                      : selectedEvaluation.missing_points.split('\n').filter(p => p.trim())
                    ).map((point, idx) => (
                      <li key={idx}>{point}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="modal-actions">
                <button
                  className="btn btn-secondary"
                  onClick={() => handleDownloadEvaluation(selectedEvaluation)}
                >
                  <FiDownload /> Download Evaluation
                </button>
                <button
                  className="btn btn-primary"
                  onClick={() => setSelectedEvaluation(null)}
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default EvaluationHistory;
