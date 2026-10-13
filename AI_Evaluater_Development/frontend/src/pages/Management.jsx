import React, { useState, useEffect } from 'react';
import { FiTrash2, FiPlus } from 'react-icons/fi';
import { getAllTeachers, createTeacher, getAllStudents, createStudent, deleteTeacher, deleteStudent } from '../services/api';
import './Management.css';

const Management = ({ setLoading }) => {
  const [activeTab, setActiveTab] = useState('teachers');
  const [teachers, setTeachers] = useState([]);
  const [students, setStudents] = useState([]);
  const [showAddTeacher, setShowAddTeacher] = useState(false);
  const [showAddStudent, setShowAddStudent] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [newTeacher, setNewTeacher] = useState({ name: '', email: '', subject: '' });
  const [newStudent, setNewStudent] = useState({ name: '', email: '', rollNumber: '', class: '' });

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadData = async () => {
    try {
      setLoading(true, 'Loading data...');
      const [teachersRes, studentsRes] = await Promise.all([
        getAllTeachers(),
        getAllStudents()
      ]);
      setTeachers(teachersRes.teachers || []);
      setStudents(studentsRes.students || []);
    } catch (err) {
      setError(err.message);
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
      setError('');
      const response = await createTeacher(newTeacher.name, newTeacher.email, newTeacher.subject);
      setTeachers([...teachers, response.teacher]);
      setNewTeacher({ name: '', email: '', subject: '' });
      setShowAddTeacher(false);
      setSuccess('Teacher added successfully!');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    }
  };

  const handleAddStudent = async () => {
    if (!newStudent.name || !newStudent.email || !newStudent.rollNumber) {
      setError('Name, email, and roll number are required');
      return;
    }

    try {
      setError('');
      const response = await createStudent(
        newStudent.name,
        newStudent.email,
        newStudent.rollNumber,
        newStudent.class
      );
      setStudents([...students, response.student]);
      setNewStudent({ name: '', email: '', rollNumber: '', class: '' });
      setShowAddStudent(false);
      setSuccess('Student added successfully!');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    }
  };

  const handleDeleteTeacher = async (teacherId) => {
    if (window.confirm('Are you sure you want to delete this teacher?')) {
      try {
        await deleteTeacher(teacherId);
        setTeachers(teachers.filter(t => t._id !== teacherId));
        setSuccess('Teacher deleted successfully!');
        setTimeout(() => setSuccess(''), 3000);
      } catch (err) {
        setError(err.response?.data?.error || 'Failed to delete teacher');
      }
    }
  };

  const handleDeleteStudent = async (studentId) => {
    if (window.confirm('Are you sure you want to delete this student?')) {
      try {
        await deleteStudent(studentId);
        setStudents(students.filter(s => s._id !== studentId));
        setSuccess('Student deleted successfully!');
        setTimeout(() => setSuccess(''), 3000);
      } catch (err) {
        setError(err.response?.data?.error || 'Failed to delete student');
      }
    }
  };

  return (
    <div className="management">
      <div className="management-container">
        <h1 className="page-title">Manage Teachers & Students</h1>

        {error && <div className="error-alert">{error}</div>}
        {success && <div className="success-alert">{success}</div>}

        {/* Tabs */}
        <div className="tabs">
          <button
            className={`tab-button ${activeTab === 'teachers' ? 'active' : ''}`}
            onClick={() => setActiveTab('teachers')}
          >
            👨‍🏫 Teachers ({teachers.length})
          </button>
          <button
            className={`tab-button ${activeTab === 'students' ? 'active' : ''}`}
            onClick={() => setActiveTab('students')}
          >
            👨‍🎓 Students ({students.length})
          </button>
        </div>

        {/* Teachers Tab */}
        {activeTab === 'teachers' && (
          <div className="tab-content">
            <div className="section-header">
              <h2>Teachers Management</h2>
              <button
                className="btn btn-primary"
                onClick={() => setShowAddTeacher(!showAddTeacher)}
              >
                <FiPlus /> Add Teacher
              </button>
            </div>

            {/* Add Teacher Form */}
            {showAddTeacher && (
              <div className="add-form-container">
                <div className="add-form">
                  <h3>Add New Teacher</h3>
                  <input
                    type="text"
                    placeholder="Teacher name"
                    value={newTeacher.name}
                    onChange={(e) => setNewTeacher({ ...newTeacher, name: e.target.value })}
                    className="form-input"
                  />
                  <input
                    type="email"
                    placeholder="Email address"
                    value={newTeacher.email}
                    onChange={(e) => setNewTeacher({ ...newTeacher, email: e.target.value })}
                    className="form-input"
                  />
                  <input
                    type="text"
                    placeholder="Subject (optional)"
                    value={newTeacher.subject}
                    onChange={(e) => setNewTeacher({ ...newTeacher, subject: e.target.value })}
                    className="form-input"
                  />
                  <div className="form-buttons">
                    <button className="btn btn-primary" onClick={handleAddTeacher}>
                      Add Teacher
                    </button>
                    <button
                      className="btn btn-secondary"
                      onClick={() => setShowAddTeacher(false)}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Teachers List */}
            <div className="list-container">
              {teachers.length > 0 ? (
                <div className="cards-grid">
                  {teachers.map(teacher => (
                    <div key={teacher._id} className="management-card">
                      <div className="card-header">
                        <div className="avatar">👨‍🏫</div>
                        <div className="card-title">
                          <h3>{teacher.name}</h3>
                          <p className="subject">{teacher.subject || 'No subject'}</p>
                        </div>
                      </div>
                      <p className="email">{teacher.email}</p>
                      <button
                        className="btn-delete"
                        onClick={() => handleDeleteTeacher(teacher._id)}
                        title="Delete teacher"
                      >
                        <FiTrash2 />
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state">
                  <p>No teachers added yet</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Students Tab */}
        {activeTab === 'students' && (
          <div className="tab-content">
            <div className="section-header">
              <h2>Students Management</h2>
              <button
                className="btn btn-primary"
                onClick={() => setShowAddStudent(!showAddStudent)}
              >
                <FiPlus /> Add Student
              </button>
            </div>

            {/* Add Student Form */}
            {showAddStudent && (
              <div className="add-form-container">
                <div className="add-form">
                  <h3>Add New Student</h3>
                  <input
                    type="text"
                    placeholder="Student name"
                    value={newStudent.name}
                    onChange={(e) => setNewStudent({ ...newStudent, name: e.target.value })}
                    className="form-input"
                  />
                  <input
                    type="email"
                    placeholder="Email address"
                    value={newStudent.email}
                    onChange={(e) => setNewStudent({ ...newStudent, email: e.target.value })}
                    className="form-input"
                  />
                  <input
                    type="text"
                    placeholder="Roll number"
                    value={newStudent.rollNumber}
                    onChange={(e) => setNewStudent({ ...newStudent, rollNumber: e.target.value })}
                    className="form-input"
                  />
                  <input
                    type="text"
                    placeholder="Class (optional)"
                    value={newStudent.class}
                    onChange={(e) => setNewStudent({ ...newStudent, class: e.target.value })}
                    className="form-input"
                  />
                  <div className="form-buttons">
                    <button className="btn btn-primary" onClick={handleAddStudent}>
                      Add Student
                    </button>
                    <button
                      className="btn btn-secondary"
                      onClick={() => setShowAddStudent(false)}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Students List */}
            <div className="list-container">
              {students.length > 0 ? (
                <div className="cards-grid">
                  {students.map(student => (
                    <div key={student._id} className="management-card">
                      <div className="card-header">
                        <div className="avatar">👨‍🎓</div>
                        <div className="card-title">
                          <h3>{student.name}</h3>
                          <p className="roll-number">{student.rollNumber}</p>
                        </div>
                      </div>
                      <p className="email">{student.email}</p>
                      {student.class && <p className="class">{student.class}</p>}
                      <button
                        className="btn-delete"
                        onClick={() => handleDeleteStudent(student._id)}
                        title="Delete student"
                      >
                        <FiTrash2 />
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state">
                  <p>No students added yet</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Management;
