import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FiFolderPlus, FiCpu, FiZap, FiLayers, FiPlay, FiCheckCircle,
  FiAlertCircle, FiSquare, FiBookOpen, FiEdit3, FiActivity
} from 'react-icons/fi';
import { batchProcessCourses, subscribeToBatchStream, stopBatchProcessing, getBatchStatus } from '../services/api';
import './BatchEvaluate.css';

const BatchEvaluate = ({ setLoading }) => {
  const navigate = useNavigate();
  const eventSourceRef = useRef(null);

  // Config state
  const [rootDirectory, setRootDirectory] = useState('');
  const [parallel, setParallel] = useState(true);
  const [maxWorkers, setMaxWorkers] = useState(3);
  const [examType, setExamType] = useState('end_sem');
  const [maxMarks, setMaxMarks] = useState(100);

  // Processing state
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState('');
  const [progress, setProgress] = useState('');

  // Real-time results
  const [courseDetails, setCourseDetails] = useState({});  // course_code -> {student_count}
  const [liveResults, setLiveResults] = useState({});      // course_code -> [results]
  const [batchSummary, setBatchSummary] = useState(null);
  const [totalCompleted, setTotalCompleted] = useState(0);
  const [totalStudents, setTotalStudents] = useState(0);

  // Auto-set max_marks when exam type changes
  useEffect(() => {
    if (examType === 'mst') {
      setMaxMarks(50);
    } else {
      setMaxMarks(100);
    }
  }, [examType]);

  // Cleanup SSE on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const handleSSEEvent = useCallback((event) => {
    switch (event.type) {
      case 'courses_discovered':
        setProgress(`Discovered ${event.total_courses} courses. Processing...`);
        setTotalStudents(
          Object.values(event.course_details || {}).reduce((sum, c) => sum + c.student_count, 0)
        );
        setCourseDetails(event.course_details || {});
        // Initialize live results for each course
        const initialResults = {};
        (event.course_codes || []).forEach(code => {
          initialResults[code] = [];
        });
        setLiveResults(initialResults);
        break;

      case 'student_complete':
        setLiveResults(prev => {
          const updated = { ...prev };
          if (!updated[event.course_code]) {
            updated[event.course_code] = [];
          }
          updated[event.course_code] = [...updated[event.course_code], {
            roll_number: event.roll_number,
            marks_awarded: event.marks_awarded,
            percentage: event.percentage,
            grade: event.grade,
            status: event.status,
            error: event.error,
            needs_review: event.needs_review || false
          }];
          return updated;
        });
        setTotalCompleted(prev => prev + 1);
        break;

      case 'batch_complete':
        setBatchSummary(event);
        setProcessing(false);
        setProgress('');
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
          eventSourceRef.current = null;
        }
        break;

      case 'batch_error':
        setError(event.error || 'Batch processing failed');
        setProcessing(false);
        setProgress('');
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
          eventSourceRef.current = null;
        }
        break;

      default:
        break;
    }
  }, []);

  // Check if batch is already running when page loads
  useEffect(() => {
    const checkRunningBatch = async () => {
      try {
        const response = await getBatchStatus();
        if (response.status === 'processing') {
          setProcessing(true);
          setProgress('Reconnected to running batch...');
          // Re-subscribe to stream
          if (!eventSourceRef.current) {
            eventSourceRef.current = subscribeToBatchStream(handleSSEEvent);
          }
        }
      } catch (err) {
        console.error("Failed to check batch status", err);
      }
    };
    checkRunningBatch();
  }, [handleSSEEvent]);

  const handleProcess = async () => {
    if (!rootDirectory.trim()) {
      setError('Please enter the root directory path');
      return;
    }

    setError('');
    setProcessing(true);
    setProgress('Starting batch processing...');
    setLiveResults({});
    setCourseDetails({});
    setBatchSummary(null);
    setTotalCompleted(0);
    setTotalStudents(0);

    try {
      // Start batch processing (returns immediately)
      await batchProcessCourses(
        rootDirectory.trim(),
        parallel,
        maxWorkers,
        examType,
        maxMarks
      );

      // Subscribe to SSE stream for real-time updates
      setProgress('Scanning for courses...');
      eventSourceRef.current = subscribeToBatchStream(handleSSEEvent);

    } catch (err) {
      setError(err.response?.data?.error || err.message || 'Failed to start batch processing');
      setProgress('');
      setProcessing(false);
    }
  };

  const handleStop = async () => {
    try {
      await stopBatchProcessing();
      setProgress('Stopping... (current evaluations will finish)');
    } catch (err) {
      setError('Failed to stop: ' + (err.response?.data?.error || err.message));
    }
  };

  const handleNewBatch = () => {
    setLiveResults({});
    setCourseDetails({});
    setBatchSummary(null);
    setTotalCompleted(0);
    setTotalStudents(0);
    setError('');
  };

  const getGradeColor = (grade) => {
    const colors = {
      'A+': '#00c853', 'A': '#2e7d32', 'B+': '#558b2f',
      'B': '#f9a825', 'C': '#ef6c00', 'D': '#e53935', 'F': '#b71c1c'
    };
    return colors[grade] || '#757575';
  };

  const hasAnyResults = Object.values(liveResults).some(arr => arr.length > 0);
  const showConfig = !processing && !hasAnyResults && !batchSummary;

  return (
    <div className="batch-evaluate">
      <div className="batch-container">
        <div className="batch-header">
          <div className="batch-title-section">
            <FiLayers className="batch-icon" size={32} />
            <div>
              <h1 className="batch-title">Batch Evaluation</h1>
              <p className="batch-subtitle">Process multiple courses with multiple students in parallel</p>
            </div>
          </div>
        </div>

        {/* Configuration Card */}
        {showConfig && (
          <div className="config-card">
            <h2><FiFolderPlus /> Configuration</h2>
            
            <div className="config-body">
              <div className="form-group">
                <label>Root Directory Path *</label>
                <input
                  type="text"
                  value={rootDirectory}
                  onChange={(e) => setRootDirectory(e.target.value)}
                  placeholder="e.g., C:\batch_evaluation_2024"
                  className="form-input directory-input"
                  disabled={processing}
                />
                <p className="form-hint">
                  Path to the folder containing course subfolders. <code>config.json</code> is optional when configuring here.
                </p>
              </div>

              {/* Exam Type Selector */}
              <div className="form-group">
                <label>Exam Type *</label>
                <div className="toggle-group exam-type-group">
                  <button
                    className={`toggle-btn exam-toggle ${examType === 'mst' ? 'active mst-active' : ''}`}
                    onClick={() => setExamType('mst')}
                    disabled={processing}
                  >
                    <FiEdit3 /> Mid-Sem (50 marks)
                  </button>
                  <button
                    className={`toggle-btn exam-toggle ${examType === 'end_sem' ? 'active endsem-active' : ''}`}
                    onClick={() => setExamType('end_sem')}
                    disabled={processing}
                  >
                    <FiBookOpen /> End Sem (100 marks)
                  </button>
                </div>
                <p className="form-hint">
                  {examType === 'mst'
                    ? 'MST: 6 MCQs (12), 3×6 marks (18), 2-3×10 marks (20) = 50 total'
                    : 'End Sem: 10 MCQs (20), 5×6 marks (30), 5×10 marks (50) = 100 total'}
                </p>
              </div>

              {/* Max Marks Input */}
              <div className="config-row">
                <div className="form-group">
                  <label>Max Marks</label>
                  <input
                    type="number"
                    value={maxMarks}
                    onChange={(e) => setMaxMarks(Math.max(1, parseInt(e.target.value) || 1))}
                    min="1"
                    max="200"
                    className="form-input marks-input"
                    disabled={processing}
                  />
                  <p className="form-hint">Auto-set from exam type, but editable</p>
                </div>

                <div className="form-group">
                  <label>Processing Mode</label>
                  <div className="toggle-group">
                    <button
                      className={`toggle-btn ${parallel ? 'active' : ''}`}
                      onClick={() => setParallel(true)}
                      disabled={processing}
                    >
                      <FiZap /> Parallel
                    </button>
                    <button
                      className={`toggle-btn ${!parallel ? 'active' : ''}`}
                      onClick={() => setParallel(false)}
                      disabled={processing}
                    >
                      <FiCpu /> Sequential
                    </button>
                  </div>
                </div>

                {parallel && (
                  <div className="form-group">
                    <label>Max Workers</label>
                    <input
                      type="number"
                      value={maxWorkers}
                      onChange={(e) => setMaxWorkers(Math.max(1, Math.min(10, parseInt(e.target.value) || 1)))}
                      min="1"
                      max="10"
                      className="form-input workers-input"
                      disabled={processing}
                    />
                  </div>
                )}
              </div>

              <div className="folder-structure-hint">
                <h4>Expected Folder Structure:</h4>
                <pre>{`root_folder/
├── MB3103/
│   ├── MB3103_Model_Answer.pdf
│   ├── 12345.pdf        (roll number)
│   └── 12346.pdf
├── CH3501/
│   ├── model_answer.pdf
│   ├── 12345.pdf
│   └── ...`}</pre>
              </div>

              {error && (
                <div className="error-alert">
                  <FiAlertCircle /> {error}
                </div>
              )}

              <button
                className="btn-process"
                onClick={handleProcess}
                disabled={processing || !rootDirectory.trim()}
              >
                <FiPlay /> Start Batch Processing ({examType === 'mst' ? 'MST' : 'End Sem'})
              </button>
            </div>
          </div>
        )}

        {/* Processing Progress Bar */}
        {processing && (
          <div className="processing-card">
            <div className="processing-header">
              <div className="processing-info">
                <FiActivity className="pulse-icon" size={22} />
                <div>
                  <h3>Processing in Progress</h3>
                  <p className="processing-detail">{progress}</p>
                </div>
              </div>
              <button className="btn-stop" onClick={handleStop}>
                <FiSquare /> Stop
              </button>
            </div>

            {totalStudents > 0 && (
              <div className="progress-bar-wrapper">
                <div className="progress-bar">
                  <div
                    className="progress-fill"
                    style={{ width: `${Math.min(100, (totalCompleted / totalStudents) * 100)}%` }}
                  />
                </div>
                <span className="progress-text">
                  {totalCompleted} / {totalStudents} students evaluated
                </span>
              </div>
            )}
          </div>
        )}

        {/* Error display (non-config mode) */}
        {!showConfig && error && (
          <div className="error-alert" style={{ marginBottom: '1rem' }}>
            <FiAlertCircle /> {error}
          </div>
        )}

        {/* Batch Summary (shown when batch is complete) */}
        {batchSummary && (
          <div className="summary-card">
            <div className="summary-header">
              <FiCheckCircle size={24} color={batchSummary.cancelled ? '#f9a825' : '#00c853'} />
              <h2>{batchSummary.cancelled ? 'Batch Processing Stopped' : 'Batch Processing Complete'}</h2>
            </div>
            <div className="summary-grid">
              <div className="summary-stat">
                <span className="stat-value">{batchSummary.total_courses}</span>
                <span className="stat-label">Courses</span>
              </div>
              <div className="summary-stat">
                <span className="stat-value">{batchSummary.total_students}</span>
                <span className="stat-label">Students</span>
              </div>
              <div className="summary-stat success">
                <span className="stat-value">{batchSummary.total_completed}</span>
                <span className="stat-label">Completed</span>
              </div>
              <div className="summary-stat danger">
                <span className="stat-value">{batchSummary.total_failed}</span>
                <span className="stat-label">Failed</span>
              </div>
              <div className="summary-stat">
                <span className="stat-value">{batchSummary.max_marks}</span>
                <span className="stat-label">Max Marks</span>
              </div>
            </div>
          </div>
        )}

        {/* Live Results — Per Course */}
        {hasAnyResults && (
          <div className="results-section">
            {Object.entries(liveResults).map(([courseCode, results]) => (
              <div className="course-result-card" key={courseCode}>
                <div className="course-header">
                  <h3 className="course-code">{courseCode}</h3>
                  <div className="course-meta">
                    <span className="badge badge-success">
                      {results.filter(r => r.status === 'completed').length} done
                    </span>
                    {courseDetails[courseCode] && (
                      <span className="badge badge-info">
                        / {courseDetails[courseCode].student_count} total
                      </span>
                    )}
                    {results.some(r => r.status === 'error') && (
                      <span className="badge badge-danger">
                        {results.filter(r => r.status === 'error').length} failed
                      </span>
                    )}
                  </div>
                </div>

                {results.length > 0 && (
                  <div className="students-table-wrapper">
                    <table className="students-table">
                      <thead>
                        <tr>
                          <th>#</th>
                          <th>Roll Number</th>
                          <th>Marks</th>
                          <th>Percentage</th>
                          <th>Grade</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {results.map((student, idx) => (
                          <tr
                            key={student.roll_number}
                            className={`${student.status === 'error' || student.needs_review ? 'row-error' : ''} fade-in-row`}
                          >
                            <td>{idx + 1}</td>
                            <td className="roll-number">{student.roll_number}</td>
                            <td className="marks">
                              {(student.status === 'completed' && !student.needs_review)
                                ? `${student.marks_awarded}/${maxMarks}`
                                : '—'}
                            </td>
                            <td>{(student.status === 'completed' && !student.needs_review) ? `${student.percentage}%` : '—'}</td>
                            <td>
                              {(student.status === 'completed' && !student.needs_review) ? (
                                <span
                                  className="grade-badge"
                                  style={{ backgroundColor: getGradeColor(student.grade) }}
                                >
                                  {student.grade}
                                </span>
                              ) : '—'}
                            </td>
                            <td>
                              <span className={`status-badge status-${student.status === 'error' || student.needs_review ? 'error' : student.status}`}>
                                {student.needs_review ? 'needs review' : student.status}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {results.length === 0 && (
                  <div className="course-waiting">
                    <div className="btn-spinner" /> Waiting to start...
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Action Buttons */}
        {(batchSummary || (!processing && hasAnyResults)) && (
          <div className="results-actions">
            <button className="btn-secondary" onClick={handleNewBatch}>
              New Batch
            </button>
            <button className="btn-primary" onClick={() => navigate('/batch-results')}>
              View Full Results
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default BatchEvaluate;
