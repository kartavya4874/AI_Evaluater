import React, { useState, useEffect } from 'react';
import FileUpload from './FileUpload';
import Results from './Results';
import { 
  uploadModelAnswer, 
  evaluateAnswer, 
  getAllTeachers, 
  getAllStudents,
  createTeacher,
  createStudent 
} from '../services/api';

const ExamEvaluator = () => {
  const [modelAnswerFile, setModelAnswerFile] = useState(null);
  const [modelAnswerText, setModelAnswerText] = useState('');
  const [studentFile, setStudentFile] = useState(null);
  const [maxMarks, setMaxMarks] = useState('');
  const [question, setQuestion] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [step, setStep] = useState(1);
  
  // User management states
  const [teachers, setTeachers] = useState([]);
  const [students, setStudents] = useState([]);
  const [selectedTeacher, setSelectedTeacher] = useState('');
  const [selectedStudent, setSelectedStudent] = useState('');
  const [showAddTeacher, setShowAddTeacher] = useState(false);
  const [showAddStudent, setShowAddStudent] = useState(false);
  
  // New user form states
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

  const handleAddTeacher = async () => {
    try {
      const response = await createTeacher(newTeacher.name, newTeacher.email, newTeacher.subject);
      setTeachers([...teachers, response.teacher]);
      setSelectedTeacher(response.teacher._id);
      setShowAddTeacher(false);
      setNewTeacher({ name: '', email: '', subject: '' });
    } catch (err) {
      setError('Error adding teacher: ' + (err.response?.data?.error || err.message));
    }
  };

  const handleAddStudent = async () => {
    try {
      const response = await createStudent(
        newStudent.name, 
        newStudent.email, 
        newStudent.rollNumber, 
        newStudent.class
      );
      setStudents([...students, response.student]);
      setSelectedStudent(response.student._id);
      setShowAddStudent(false);
      setNewStudent({ name: '', email: '', rollNumber: '', class: '' });
    } catch (err) {
      setError('Error adding student: ' + (err.response?.data?.error || err.message));
    }
  };

  const handleModelAnswerUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setModelAnswerFile(file);
    setLoading(true);
    setError('');

    try {
      const response = await uploadModelAnswer(file);
      setModelAnswerText(response.model_answer);
      setStep(2);
    } catch (err) {
      setError('Error uploading model answer: ' + (err.response?.data?.error || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleStudentFileUpload = (event) => {
    const file = event.target.files[0];
    setStudentFile(file);
  };

  const handleEvaluation = async () => {
    if (!studentFile || !modelAnswerText || !maxMarks) {
      setError('Please provide all required inputs');
      return;
    }

    setLoading(true);
    setError('');
    setResults(null);

    try {
      const response = await evaluateAnswer(
        studentFile, 
        modelAnswerText, 
        maxMarks, 
        question,
        selectedTeacher || null,
        selectedStudent || null
      );
      setResults(response.evaluation);
      setStep(3);
    } catch (err) {
      setError('Error evaluating answer: ' + (err.response?.data?.error || err.message));
    } finally {
      setLoading(false);
    }
  };

  const resetEvaluation = () => {
    setModelAnswerFile(null);
    setModelAnswerText('');
    setStudentFile(null);
    setMaxMarks('');
    setQuestion('');
    setResults(null);
    setError('');
    setStep(1);
    setSelectedTeacher('');
    setSelectedStudent('');
  };

  return (
    <div className="evaluator-container">
      <header className="header">
        <h1>🧠 AI Examiner</h1>
        <p>Automated Answer Evaluation using Gemini AI with MongoDB</p>
      </header>

      {error && (
        <div className="error-message">
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* User Selection */}
      <div className="step-card">
        <h2 className="step-title">Select Teacher & Student</h2>
        
        <div className="user-selection">
          <div className="input-group">
            <label>Teacher</label>
            <div className="select-with-button">
              <select 
                value={selectedTeacher} 
                onChange={(e) => setSelectedTeacher(e.target.value)}
                className="user-select"
              >
                <option value="">-- Optional --</option>
                {teachers.map(teacher => (
                  <option key={teacher._id} value={teacher._id}>
                    {teacher.name} ({teacher.email})
                  </option>
                ))}
              </select>
              <button 
                onClick={() => setShowAddTeacher(!showAddTeacher)} 
                className="btn-add-user"
              >
                +
              </button>
            </div>
          </div>

          {showAddTeacher && (
            <div className="add-user-form">
              <input 
                type="text" 
                placeholder="Name"
                value={newTeacher.name}
                onChange={(e) => setNewTeacher({...newTeacher, name: e.target.value})}
              />
              <input 
                type="email" 
                placeholder="Email"
                value={newTeacher.email}
                onChange={(e) => setNewTeacher({...newTeacher, email: e.target.value})}
              />
              <input 
                type="text" 
                placeholder="Subject (optional)"
                value={newTeacher.subject}
                onChange={(e) => setNewTeacher({...newTeacher, subject: e.target.value})}
              />
              <button onClick={handleAddTeacher} className="btn btn-primary">Add Teacher</button>
            </div>
          )}

          <div className="input-group">
            <label>Student</label>
            <div className="select-with-button">
              <select 
                value={selectedStudent} 
                onChange={(e) => setSelectedStudent(e.target.value)}
                className="user-select"
              >
                <option value="">-- Optional --</option>
                {students.map(student => (
                  <option key={student._id} value={student._id}>
                    {student.name} - {student.roll_number || student.email}
                  </option>
                ))}
              </select>
              <button 
                onClick={() => setShowAddStudent(!showAddStudent)} 
                className="btn-add-user"
              >
                +
              </button>
            </div>
          </div>

          {showAddStudent && (
            <div className="add-user-form">
              <input 
                type="text" 
                placeholder="Name"
                value={newStudent.name}
                onChange={(e) => setNewStudent({...newStudent, name: e.target.value})}
              />
              <input 
                type="email" 
                placeholder="Email"
                value={newStudent.email}
                onChange={(e) => setNewStudent({...newStudent, email: e.target.value})}
              />
              <input 
                type="text" 
                placeholder="Roll Number"
                value={newStudent.rollNumber}
                onChange={(e) => setNewStudent({...newStudent, rollNumber: e.target.value})}
              />
              <input 
                type="text" 
                placeholder="Class"
                value={newStudent.class}
                onChange={(e) => setNewStudent({...newStudent, class: e.target.value})}
              />
              <button onClick={handleAddStudent} className="btn btn-primary">Add Student</button>
            </div>
          )}
        </div>
      </div>

      {step >= 1 && (
        <div className="step-card">
          <h2 className="step-title">Step 1: Teacher - Upload Model Answer</h2>
          <FileUpload
            label="Upload Model Answer (PDF)"
            onChange={handleModelAnswerUpload}
            disabled={loading || modelAnswerText !== ''}
          />
          {modelAnswerFile && <p className="file-name">✓ {modelAnswerFile.name}</p>}
          {modelAnswerText && (
            <div className="success-message">
              ✓ Model answer uploaded successfully
            </div>
          )}
        </div>
      )}

      {step >= 2 && (
        <div className="step-card">
          <h2 className="step-title">Step 2: Student - Upload Answer Sheet</h2>
          
          <div className="input-group">
            <label>Question (Optional)</label>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Enter the question that was asked (optional)"
              rows="3"
              className="question-input"
            />
          </div>

          <FileUpload
            label="Upload Student's Answer Sheet (PDF/Image)"
            onChange={handleStudentFileUpload}
            accept=".pdf,.png,.jpg,.jpeg"
            disabled={loading}
          />
          {studentFile && <p className="file-name">✓ {studentFile.name}</p>}

          <div className="input-group">
            <label>Maximum Marks</label>
            <input
              type="number"
              value={maxMarks}
              onChange={(e) => setMaxMarks(e.target.value)}
              placeholder="Enter maximum marks (e.g., 10)"
              min="1"
              className="marks-input"
            />
          </div>

          <div className="button-group">
            <button
              onClick={handleEvaluation}
              disabled={loading || !studentFile || !maxMarks}
              className="btn btn-primary"
            >
              {loading ? '🔄 Evaluating...' : '🚀 Evaluate Answer'}
            </button>
            <button onClick={resetEvaluation} className="btn btn-secondary">
              🔄 Start Over
            </button>
          </div>
        </div>
      )}

      {step >= 3 && results && <Results evaluation={results} />}

      {loading && (
        <div className="loading-overlay">
          <div className="spinner"></div>
          <p>Processing... This may take a few moments</p>
        </div>
      )}
    </div>
  );
};

export default ExamEvaluator;
