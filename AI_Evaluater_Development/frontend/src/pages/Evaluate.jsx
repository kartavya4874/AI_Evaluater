import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { FiUploadCloud, FiCheckCircle } from 'react-icons/fi';
import { uploadModelAnswer, evaluateAnswer, getAllTeachers, getAllStudents, createTeacher, createStudent } from '../services/api';
import './Evaluate.css';

const Evaluate = ({ setLoading }) => {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [modelAnswerText, setModelAnswerText] = useState('');
  const [studentFile, setStudentFile] = useState(null);
  const [maxMarks, setMaxMarks] = useState('');
  const [question, setQuestion] = useState('');
  const [teachers, setTeachers] = useState([]);
  const [students, setStudents] = useState([]);
  const [selectedTeacher, setSelectedTeacher] = useState('');
  const [selectedStudent, setSelectedStudent] = useState('');
  const [error, setError] = useState('');
  const [results, setResults] = useState(null);

  const [showNewTeacher, setShowNewTeacher] = useState(false);
  const [showNewStudent, setShowNewStudent] = useState(false);
  const [newTeacher, setNewTeacher] = useState({ name: '', email: '', subject: '' });
  const [newStudent, setNewStudent] = useState({ name: '', email: '', rollNumber: '', class: '' });

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      const [teachersRes, studentsRes] = await Promise.all([
        getAllTeachers(),
        getAllStudents()
      ]);
      setTeachers(teachersRes.teachers || []);
      setStudents(studentsRes.students || []);
    } catch (err) {
      console.error('Error loading users:', err);
    }
  };

  const handleModelAnswerUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setError('');
    setLoading(true, 'Extracting model answer...');

    try {
      const response = await uploadModelAnswer(file);
      setModelAnswerText(response.model_answer);
      setStep(2);
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAddTeacher = async () => {
    if (!newTeacher.name || !newTeacher.email) {
      setError('Name and email are required');
      return;
    }
    try {
      const response = await createTeacher(newTeacher.name, newTeacher.email, newTeacher.subject);
      setTeachers([...teachers, response.teacher]);
      setSelectedTeacher(response.teacher._id);
      setShowNewTeacher(false);
      setNewTeacher({ name: '', email: '', subject: '' });
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    }
  };

  const handleAddStudent = async () => {
    if (!newStudent.name || !newStudent.email) {
      setError('Name and email are required');
      return;
    }
    try {
      const response = await createStudent(newStudent.name, newStudent.email, newStudent.rollNumber, newStudent.class);
      setStudents([...students, response.student]);
      setSelectedStudent(response.student._id);
      setShowNewStudent(false);
      setNewStudent({ name: '', email: '', rollNumber: '', class: '' });
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    }
  };

  const handleEvaluate = async () => {
    if (!studentFile) {
      setError('Please upload a student answer file');
      return;
    }
    if (!maxMarks) {
      setError('Please enter maximum marks');
      return;
    }
    if (!selectedTeacher) {
      setError('Please select a teacher');
      return;
    }
    if (!selectedStudent) {
      setError('Please select a student');
      return;
    }
    if (!modelAnswerText) {
      setError('Please enter model answer');
      return;
    }

    setError('');
    setLoading(true, 'Evaluating answer... This may take a moment');

    try {
      const formData = new FormData();
      formData.append('student_file', studentFile);
      formData.append('model_answer', modelAnswerText);
      formData.append('max_marks', maxMarks);
      formData.append('question', question);
      formData.append('teacher_id', selectedTeacher);
      formData.append('student_id', selectedStudent);

      const response = await evaluateAnswer(formData);
      // Extract evaluation from response
      const evaluationData = response.evaluation || response;
      // Add max_marks to evaluation data for display
      evaluationData.max_marks = maxMarks;
      setResults(evaluationData);
      // Navigate to results page with evaluation data
      navigate('/results/new', { state: { evaluation: evaluationData } });
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="evaluate">
      <div className="evaluate-container">
        <h1 className="page-title">Evaluate Answer</h1>

        {/* Progress Bar */}
        <div className="progress-bar">
          <div className={`progress-step ${step >= 1 ? 'active' : ''}`}>
            <div className="progress-circle">1</div>
            <p>Model Answer</p>
          </div>
          <div className={`progress-line ${step >= 2 ? 'active' : ''}`}></div>
          <div className={`progress-step ${step >= 2 ? 'active' : ''}`}>
            <div className="progress-circle">2</div>
            <p>Student Answer</p>
          </div>
          <div className={`progress-line ${step >= 3 ? 'active' : ''}`}></div>
          <div className={`progress-step ${step >= 3 ? 'active' : ''}`}>
            <div className="progress-circle">3</div>
            <p>Results</p>
          </div>
        </div>

        {error && <div className="error-alert">{error}</div>}

        {/* Step 1: Model Answer */}
        {step === 1 && (
          <div className="step-content">
            <h2>Upload Model Answer</h2>
            <p className="step-description">Upload the correct answer PDF or type it in</p>
            
            <div className="upload-area">
              <input
                type="file"
                id="modelAnswerFile"
                accept=".pdf"
                onChange={handleModelAnswerUpload}
                className="file-input"
              />
              <label htmlFor="modelAnswerFile" className="upload-label">
                <FiUploadCloud size={48} />
                <p className="upload-text">Click or drag PDF file here</p>
                <p className="upload-hint">or paste text below</p>
              </label>
            </div>

            <div className="form-group">
              <label>Or Paste Model Answer Text:</label>
              <textarea
                value={modelAnswerText}
                onChange={(e) => setModelAnswerText(e.target.value)}
                placeholder="Paste the model answer here..."
                className="textarea"
                rows="6"
              ></textarea>
            </div>

            <button
              className="btn btn-primary btn-lg"
              onClick={() => setStep(2)}
              disabled={!modelAnswerText}
            >
              Next <span>→</span>
            </button>
          </div>
        )}

        {/* Step 2: Student Answer */}
        {step === 2 && (
          <div className="step-content">
            <h2>Student Answer & Details</h2>
            <p className="step-description">Upload student answer and fill in the details</p>

            {/* User Selection */}
            <div className="form-section">
              <h3>Teacher & Student</h3>

              <div className="form-group">
                <label>Select Teacher *</label>
                <div className="select-group">
                  <select
                    value={selectedTeacher}
                    onChange={(e) => setSelectedTeacher(e.target.value)}
                    className="form-select"
                  >
                    <option value="">Choose a teacher...</option>
                    {teachers.map(teacher => (
                      <option key={teacher._id} value={teacher._id}>
                        {teacher.name} ({teacher.subject})
                      </option>
                    ))}
                  </select>
                  <button
                    className="btn-icon"
                    onClick={() => setShowNewTeacher(!showNewTeacher)}
                    title="Add new teacher"
                  >
                    +
                  </button>
                </div>
              </div>

              {showNewTeacher && (
                <div className="add-form">
                  <input
                    type="text"
                    placeholder="Teacher name"
                    value={newTeacher.name}
                    onChange={(e) => setNewTeacher({...newTeacher, name: e.target.value})}
                    className="form-input"
                  />
                  <input
                    type="email"
                    placeholder="Email"
                    value={newTeacher.email}
                    onChange={(e) => setNewTeacher({...newTeacher, email: e.target.value})}
                    className="form-input"
                  />
                  <input
                    type="text"
                    placeholder="Subject"
                    value={newTeacher.subject}
                    onChange={(e) => setNewTeacher({...newTeacher, subject: e.target.value})}
                    className="form-input"
                  />
                  <button className="btn btn-sm btn-primary" onClick={handleAddTeacher}>
                    Add Teacher
                  </button>
                </div>
              )}

              <div className="form-group">
                <label>Select Student *</label>
                <div className="select-group">
                  <select
                    value={selectedStudent}
                    onChange={(e) => setSelectedStudent(e.target.value)}
                    className="form-select"
                  >
                    <option value="">Choose a student...</option>
                    {students.map(student => (
                      <option key={student._id} value={student._id}>
                        {student.name} ({student.rollNumber})
                      </option>
                    ))}
                  </select>
                  <button
                    className="btn-icon"
                    onClick={() => setShowNewStudent(!showNewStudent)}
                    title="Add new student"
                  >
                    +
                  </button>
                </div>
              </div>

              {showNewStudent && (
                <div className="add-form">
                  <input
                    type="text"
                    placeholder="Student name"
                    value={newStudent.name}
                    onChange={(e) => setNewStudent({...newStudent, name: e.target.value})}
                    className="form-input"
                  />
                  <input
                    type="email"
                    placeholder="Email"
                    value={newStudent.email}
                    onChange={(e) => setNewStudent({...newStudent, email: e.target.value})}
                    className="form-input"
                  />
                  <input
                    type="text"
                    placeholder="Roll number"
                    value={newStudent.rollNumber}
                    onChange={(e) => setNewStudent({...newStudent, rollNumber: e.target.value})}
                    className="form-input"
                  />
                  <input
                    type="text"
                    placeholder="Class"
                    value={newStudent.class}
                    onChange={(e) => setNewStudent({...newStudent, class: e.target.value})}
                    className="form-input"
                  />
                  <button className="btn btn-sm btn-primary" onClick={handleAddStudent}>
                    Add Student
                  </button>
                </div>
              )}
            </div>

            {/* Student Answer Upload */}
            <div className="form-section">
              <h3>Student Answer</h3>

              <div className="upload-area">
                <input
                  type="file"
                  id="studentFile"
                  accept=".pdf,.png,.jpg,.jpeg"
                  onChange={(e) => {
                    const file = e.target.files[0];
                    if (file) {
                      setStudentFile(file);
                      setError('');
                    }
                  }}
                  className="file-input"
                  required
                />
                <label htmlFor="studentFile" className="upload-label">
                  <FiUploadCloud size={48} />
                  <p className="upload-text">Click or drag file here</p>
                  <p className="upload-hint">PDF or image file</p>
                </label>
              </div>

              {studentFile && (
                <div className="file-selected">
                  <FiCheckCircle color="green" />
                  <span>{studentFile.name}</span>
                </div>
              )}
            </div>

            {/* Evaluation Details */}
            <div className="form-section">
              <h3>Evaluation Details</h3>

              <div className="form-group">
                <label>Question (Optional)</label>
                <textarea
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="Enter the question for context..."
                  className="textarea"
                  rows="3"
                ></textarea>
              </div>

              <div className="form-group">
                <label>Maximum Marks *</label>
                <input
                  type="number"
                  value={maxMarks}
                  onChange={(e) => setMaxMarks(e.target.value)}
                  placeholder="e.g., 100"
                  className="form-input"
                  min="1"
                />
              </div>
            </div>

            <div className="button-group">
              <button className="btn btn-secondary" onClick={() => setStep(1)}>
                ← Back
              </button>
              <button
                className="btn btn-primary btn-lg"
                onClick={handleEvaluate}
                disabled={!studentFile || !maxMarks}
              >
                Evaluate <span>→</span>
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Results */}
        {step === 3 && results && (
          <div className="step-content results-content">
            <h2>Evaluation Results</h2>
            <div className="results-grid">
              <div className="result-card">
                <h3>Marks Awarded</h3>
                <div className="marks-display">
                  <span className="marks-value">{results.marks_awarded}</span>
                  <span className="marks-max">/ {maxMarks}</span>
                </div>
              </div>

              <div className="result-card">
                <h3>Percentage</h3>
                <div className="percentage-display">{results.percentage}%</div>
              </div>

              <div className="result-card">
                <h3>Grade</h3>
                <div className="grade-display">{results.grade}</div>
              </div>
            </div>

            <div className="result-section">
              <h3>Feedback</h3>
              <p className="feedback">{results.feedback}</p>
            </div>

            <div className="result-section">
              <h3>Strengths</h3>
              <ul className="points-list strengths">
                {results.strengths?.map((strength, idx) => (
                  <li key={idx}><span>✓</span> {strength}</li>
                ))}
              </ul>
            </div>

            <div className="result-section">
              <h3>Areas for Improvement</h3>
              <ul className="points-list improvements">
                {results.missing_points?.map((point, idx) => (
                  <li key={idx}><span>→</span> {point}</li>
                ))}
              </ul>
            </div>

            <div className="button-group">
              <button
                className="btn btn-primary"
                onClick={() => {
                  setStep(1);
                  setModelAnswerText('');
                  setStudentFile(null);
                  setMaxMarks('');
                  setQuestion('');
                  setResults(null);
                }}
              >
                Evaluate Another
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Evaluate;
