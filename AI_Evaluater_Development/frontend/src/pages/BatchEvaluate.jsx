import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FiFolderPlus, FiCpu, FiZap, FiLayers, FiPlay, FiCheckCircle,
  FiAlertCircle, FiSquare, FiBookOpen, FiEdit3, FiActivity, FiUploadCloud
} from 'react-icons/fi';
import { batchProcessCourses, subscribeToBatchStream, stopBatchProcessing, getBatchStatus, uploadBatchFolder } from '../services/api';
import './BatchEvaluate.css';

const BatchEvaluate = ({ setLoading }) => {
  const navigate = useNavigate();
  const eventSourceRef = useRef(null);

  // Input mode: 'upload' or 'path'
  const [inputMode, setInputMode] = useState('upload');

  // Config state
  const [rootDirectory, setRootDirectory] = useState('');
  const [parallel, setParallel] = useState(true);
  const [maxWorkers, setMaxWorkers] = useState(3);
  const [examType, setExamType] = useState('end_sem');
  const [maxMarks, setMaxMarks] = useState(100);

  // Upload state
  const [selectedFiles, setSelectedFiles] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploading, setUploading] = useState(false);

  // Processing state
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState('');
  const [progress, setProgress] = useState('');

  // Real-time results
  const [courseDetails, setCourseDetails] = useState({});
  const [liveResults, setLiveResults] = useState({});
  const [batchSummary, setBatchSummary] = useState(null);
  const [totalCompleted, setTotalCompleted] = useState(0);
  const [totalStudents, setTotalStudents] = useState(0);

  useEffect(() => {
    if (examType === 'mst') setMaxMarks(50);
    else setMaxMarks(100);
  }, [examType]);

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) eventSourceRef.current.close();
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
        const initialResults = {};
        (event.course_codes || []).forEach(code => { initialResults[code] = []; });
        setLiveResults(initialResults);
        break;
      case 'student_complete':
        setLiveResults(prev => {
          const updated = { ...prev };
          if (!updated[event.course_code]) updated[event.course_code] = [];
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
        if (eventSourceRef.current) { eventSourceRef.current.close(); eventSourceRef.current = null; }
        break;
      case 'batch_error':
        setError(event.error || 'Batch processing failed');
        setProcessing(false);
        setProgress('');
        if (eventSourceRef.current) { eventSourceRef.current.close(); eventSourceRef.current = null; }
        break;
      default: break;
    }
  }, []);

  useEffect(() => {
    const checkRunningBatch = async () => {
      try {
        const response = await getBatchStatus();
        if (response.status === 'processing') {
          setProcessing(true);
          setProgress('Reconnected to running batch...');
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

  const handleFolderSelect = (e) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      setSelectedFiles(files);
      setError('');
    }
  };

  const startProcessing = async (directory) => {
    setProcessing(true);
    setProgress('Starting batch processing...');
    setLiveResults({});
    setCourseDetails({});
    setBatchSummary(null);
    setTotalCompleted(0);
    setTotalStudents(0);

    try {
      await batchProcessCourses(directory, parallel, maxWorkers, examType, maxMarks);
      setProgress('Scanning for courses...');
      eventSourceRef.current = subscribeToBatchStream(handleSSEEvent);
    } catch (err) {
      setError(err.response?.data?.error || err.message || 'Failed to start batch processing');
      setProgress('');
      setProcessing(false);
    }
  };

  const handleProcess = async () => {
    setError('');

    if (inputMode === 'upload') {
      if (!selectedFiles || selectedFiles.length === 0) {
        setError('Please select a folder to upload');
        return;
      }
      // Upload folder first, then start processing
      setUploading(true);
      setUploadProgress(0);
      try {
        const uploadResult = await uploadBatchFolder(selectedFiles, (pct) => setUploadProgress(pct));
        setUploading(false);
        setUploadProgress(100);
        await startProcessing(uploadResult.upload_dir);
      } catch (err) {
        setUploading(false);
        setError(err.response?.data?.error || err.message || 'Upload failed');
      }
    } else {
      if (!rootDirectory.trim()) {
        setError('Please enter the root directory path');
        return;
      }
      await startProcessing(rootDirectory.trim());
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
    setSelectedFiles(null);
    setUploadProgress(0);
  };

  const getGradeColor = (grade) => {
    const colors = {
      'A+': '#22c55e', 'A': '#22c55e', 'B+': '#14b8a6',
      'B': '#eab308', 'C': '#f59e0b', 'D': '#ef4444', 'F': '#dc2626'
    };
    return colors[grade] || '#71717a';
  };

  const hasAnyResults = Object.values(liveResults).some(arr => arr.length > 0);
  const showConfig = !processing && !uploading && !hasAnyResults && !batchSummary;

  return (
    <div className="batch-evaluate">
      <div className="batch-container">
        <div className="batch-header">
          <div className="batch-title-section">
            <div className="batch-icon-wrap"><FiLayers size={20} /></div>
            <div>
              <h1 className="batch-title">Batch Evaluation</h1>
              <p className="batch-subtitle">Process multiple courses with multiple students</p>
            </div>
          </div>
        </div>

        {showConfig && (
          <div className="config-card">
            <div className="config-card-header">
              <FiFolderPlus size={16} /> Configuration
            </div>
            <div className="config-body">

              {/* Input Mode Toggle */}
              <div className="form-group">
                <label>Source</label>
                <div className="toggle-group">
                  <button
                    className={`toggle-btn ${inputMode === 'upload' ? 'active' : ''}`}
                    onClick={() => setInputMode('upload')}
                  >
                    <FiUploadCloud /> Upload Folder
                  </button>
                  <button
                    className={`toggle-btn ${inputMode === 'path' ? 'active' : ''}`}
                    onClick={() => setInputMode('path')}
                  >
                    <FiFolderPlus /> Server Path
                  </button>
                </div>
              </div>

              {inputMode === 'upload' ? (
                <div className="form-group">
                  <label>Select Folder</label>
                  <div className="folder-upload-area">
                    <input
                      type="file"
                      id="folderUpload"
                      webkitdirectory="true"
                      directory="true"
                      multiple
                      onChange={handleFolderSelect}
                      className="file-input-hidden"
                    />
                    <label htmlFor="folderUpload" className="folder-upload-label">
                      <FiUploadCloud size={28} />
                      {selectedFiles ? (
                        <span className="folder-upload-selected">
                          {selectedFiles.length} files selected
                        </span>
                      ) : (
                        <>
                          <span className="folder-upload-text">Click to select folder</span>
                          <span className="folder-upload-hint">Select the root folder containing course subfolders</span>
                        </>
                      )}
                    </label>
                  </div>
                </div>
              ) : (
                <div className="form-group">
                  <label>Root Directory Path</label>
                  <input
                    type="text"
                    value={rootDirectory}
                    onChange={(e) => setRootDirectory(e.target.value)}
                    placeholder="e.g., C:\batch_evaluation_2024"
                    className="form-input"
                    disabled={processing}
                  />
                  <p className="form-hint">Path to the folder containing course subfolders.</p>
                </div>
              )}

              {/* Exam Type */}
              <div className="form-group">
                <label>Exam Type</label>
                <div className="toggle-group">
                  <button className={`toggle-btn ${examType === 'mst' ? 'active active-warn' : ''}`} onClick={() => setExamType('mst')}>
                    <FiEdit3 /> Mid-Sem (50)
                  </button>
                  <button className={`toggle-btn ${examType === 'end_sem' ? 'active' : ''}`} onClick={() => setExamType('end_sem')}>
                    <FiBookOpen /> End Sem (100)
                  </button>
                </div>
              </div>

              {/* Config Row */}
              <div className="config-row">
                <div className="form-group">
                  <label>Max Marks</label>
                  <input
                    type="number"
                    value={maxMarks}
                    onChange={(e) => setMaxMarks(Math.max(1, parseInt(e.target.value) || 1))}
                    min="1" max="200"
                    className="form-input marks-input"
                  />
                </div>
                <div className="form-group">
                  <label>Mode</label>
                  <div className="toggle-group">
                    <button className={`toggle-btn ${parallel ? 'active' : ''}`} onClick={() => setParallel(true)}><FiZap /> Parallel</button>
                    <button className={`toggle-btn ${!parallel ? 'active' : ''}`} onClick={() => setParallel(false)}><FiCpu /> Sequential</button>
                  </div>
                </div>
                {parallel && (
                  <div className="form-group">
                    <label>Workers</label>
                    <input
                      type="number"
                      value={maxWorkers}
                      onChange={(e) => setMaxWorkers(Math.max(1, Math.min(10, parseInt(e.target.value) || 1)))}
                      min="1" max="10"
                      className="form-input workers-input"
                    />
                  </div>
                )}
              </div>

              <div className="folder-structure-hint">
                <h4>Expected Folder Structure:</h4>
                <pre>{`root_folder/
├── MB3103/
│   ├── MB3103_Model_Answer.pdf
│   ├── 12345.pdf
│   └── 12346.pdf
├── CH3501/
│   ├── model_answer.pdf
│   └── 12345.pdf`}</pre>
              </div>

              {error && <div className="error-alert"><FiAlertCircle /> {error}</div>}

              <button
                className="btn-process"
                onClick={handleProcess}
                disabled={processing || (inputMode === 'upload' ? !selectedFiles : !rootDirectory.trim())}
              >
                <FiPlay /> Start Batch Processing ({examType === 'mst' ? 'MST' : 'End Sem'})
              </button>
            </div>
          </div>
        )}

        {/* Upload Progress */}
        {uploading && (
          <div className="processing-card">
            <div className="processing-info">
              <FiUploadCloud className="pulse-icon" size={20} />
              <div>
                <h3>Uploading Files...</h3>
                <p className="processing-detail">{uploadProgress}% complete</p>
              </div>
            </div>
            <div className="progress-bar-wrapper">
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${uploadProgress}%` }} />
              </div>
            </div>
          </div>
        )}

        {/* Processing Progress */}
        {processing && (
          <div className="processing-card">
            <div className="processing-header">
              <div className="processing-info">
                <FiActivity className="pulse-icon" size={20} />
                <div>
                  <h3>Processing</h3>
                  <p className="processing-detail">{progress}</p>
                </div>
              </div>
              <button className="btn-stop" onClick={handleStop}><FiSquare /> Stop</button>
            </div>
            {totalStudents > 0 && (
              <div className="progress-bar-wrapper">
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: `${Math.min(100, (totalCompleted / totalStudents) * 100)}%` }} />
                </div>
                <span className="progress-text">{totalCompleted} / {totalStudents} students</span>
              </div>
            )}
          </div>
        )}

        {!showConfig && !uploading && error && (
          <div className="error-alert" style={{ marginBottom: '1rem' }}><FiAlertCircle /> {error}</div>
        )}

        {/* Summary */}
        {batchSummary && (
          <div className="summary-card">
            <div className="summary-header">
              <FiCheckCircle size={20} color={batchSummary.cancelled ? '#eab308' : '#22c55e'} />
              <h2>{batchSummary.cancelled ? 'Processing Stopped' : 'Processing Complete'}</h2>
            </div>
            <div className="summary-grid">
              <div className="summary-stat"><span className="stat-value">{batchSummary.total_courses}</span><span className="stat-label">Courses</span></div>
              <div className="summary-stat"><span className="stat-value">{batchSummary.total_students}</span><span className="stat-label">Students</span></div>
              <div className="summary-stat success"><span className="stat-value">{batchSummary.total_completed}</span><span className="stat-label">Completed</span></div>
              <div className="summary-stat danger"><span className="stat-value">{batchSummary.total_failed}</span><span className="stat-label">Failed</span></div>
            </div>
          </div>
        )}

        {/* Live Results */}
        {hasAnyResults && (
          <div className="results-section">
            {Object.entries(liveResults).map(([courseCode, results]) => (
              <div className="course-result-card" key={courseCode}>
                <div className="course-header">
                  <h3 className="course-code">{courseCode}</h3>
                  <div className="course-meta">
                    <span className="badge badge-success">{results.filter(r => r.status === 'completed').length} done</span>
                    {courseDetails[courseCode] && <span className="badge badge-info">/ {courseDetails[courseCode].student_count} total</span>}
                    {results.some(r => r.status === 'error') && <span className="badge badge-danger">{results.filter(r => r.status === 'error').length} failed</span>}
                  </div>
                </div>
                {results.length > 0 ? (
                  <div className="students-table-wrapper">
                    <table className="students-table">
                      <thead>
                        <tr><th>#</th><th>Roll Number</th><th>Marks</th><th>%</th><th>Grade</th><th>Status</th></tr>
                      </thead>
                      <tbody>
                        {results.map((student, idx) => (
                          <tr key={student.roll_number} className={`${student.status === 'error' || student.needs_review ? 'row-error' : ''} fade-in-row`}>
                            <td>{idx + 1}</td>
                            <td className="roll-number">{student.roll_number}</td>
                            <td className="marks">{(student.status === 'completed' && !student.needs_review) ? `${student.marks_awarded}/${maxMarks}` : '—'}</td>
                            <td>{(student.status === 'completed' && !student.needs_review) ? `${student.percentage}%` : '—'}</td>
                            <td>
                              {(student.status === 'completed' && !student.needs_review) ? (
                                <span className="grade-badge" style={{ backgroundColor: getGradeColor(student.grade) }}>{student.grade}</span>
                              ) : '—'}
                            </td>
                            <td>
                              <span className={`status-badge status-${student.status === 'error' || student.needs_review ? 'error' : student.status}`}>
                                {student.needs_review ? 'review' : student.status}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="course-waiting"><div className="btn-spinner" /> Waiting...</div>
                )}
              </div>
            ))}
          </div>
        )}

        {(batchSummary || (!processing && hasAnyResults)) && (
          <div className="results-actions">
            <button className="btn-secondary" onClick={handleNewBatch}>New Batch</button>
            <button className="btn-primary" onClick={() => navigate('/batch-results')}>View Full Results</button>
          </div>
        )}
      </div>
    </div>
  );
};

export default BatchEvaluate;
