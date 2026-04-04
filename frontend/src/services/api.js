import axios from 'axios';

const API_BASE_URL = process.env.NODE_ENV === 'production' 
  ? (process.env.REACT_APP_API_URL || '/api') 
  : (process.env.REACT_APP_API_URL || 'http://localhost:5000/api');
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 0, // No timeout - evaluating up to 36 pages via Gemini Vision can take several minutes
});

// Teacher APIs
export const createTeacher = async (name, email, subject) => {
  const response = await api.post('/teachers', { name, email, subject }, {
    headers: { 'Content-Type': 'application/json' }
  });
  return response.data;
};

export const getTeacher = async (teacherId) => {
  const response = await api.get(`/teachers/${teacherId}`);
  return response.data;
};

export const getAllTeachers = async () => {
  const response = await api.get('/teachers');
  return response.data;
};

export const deleteTeacher = async (teacherId) => {
  const response = await api.delete(`/teachers/${teacherId}`);
  return response.data;
};

// Student APIs
export const createStudent = async (name, email, rollNumber, className) => {
  const response = await api.post('/students', { 
    name, 
    email, 
    roll_number: rollNumber, 
    class: className 
  }, {
    headers: { 'Content-Type': 'application/json' }
  });
  return response.data;
};

export const getStudent = async (studentId) => {
  const response = await api.get(`/students/${studentId}`);
  return response.data;
};

export const getAllStudents = async () => {
  const response = await api.get('/students');
  return response.data;
};

export const deleteStudent = async (studentId) => {
  const response = await api.delete(`/students/${studentId}`);
  return response.data;
};

export const getStudentStatistics = async (studentId) => {
  const response = await api.get(`/students/${studentId}/statistics`);
  return response.data;
};

// Evaluation APIs
export const uploadModelAnswer = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await api.post('/upload-model-answer', formData);
  return response.data;
};

export const evaluateAnswer = async (formDataOrFile, modelAnswer, maxMarks, question = '', teacherId = null, studentId = null) => {
  // Handle both FormData object and individual parameters
  let formData;
  
  if (formDataOrFile instanceof FormData) {
    // If FormData is passed directly, use it as-is
    formData = formDataOrFile;
  } else {
    // Otherwise create FormData from individual parameters
    formData = new FormData();
    formData.append('student_file', formDataOrFile);
    formData.append('model_answer', modelAnswer);
    formData.append('max_marks', maxMarks);
    if (question) formData.append('question', question);
    if (teacherId) formData.append('teacher_id', teacherId);
    if (studentId) formData.append('student_id', studentId);
  }
  
  const response = await api.post('/evaluate-answer', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
  return response.data;
};

export const getEvaluation = async (evaluationId) => {
  const response = await api.get(`/evaluations/${evaluationId}`);
  return response.data;
};

export const getEvaluations = async () => {
  const response = await api.get('/evaluations');
  return response.data;
};

export const getStudentEvaluations = async (studentId, limit = 10) => {
  const response = await api.get(`/evaluations/student/${studentId}?limit=${limit}`);
  return response.data;
};

export const getTeacherEvaluations = async (teacherId, limit = 10) => {
  const response = await api.get(`/evaluations/teacher/${teacherId}?limit=${limit}`);
  return response.data;
};

export const getRecentEvaluations = async (limit = 20) => {
  const response = await api.get(`/evaluations/recent?limit=${limit}`);
  return response.data;
};

export const deleteEvaluation = async (evaluationId) => {
  const response = await api.delete(`/evaluations/${evaluationId}`);
  return response.data;
};

export const extractTextOnly = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await api.post('/ocr-only', formData);
  return response.data;
};

export const updateManualEvaluation = async (evaluationId, marksAwarded, feedback) => {
  const response = await api.put(`/evaluations/${evaluationId}/manual`, {
    marks_awarded: marksAwarded,
    feedback: feedback
  });
  return response.data;
};

// ==================== BATCH PROCESSING APIs ====================

/**
 * Start batch processing. Returns immediately - use subscribeToBatchStream for real-time updates.
 */
export const batchProcessCourses = async (rootDirectory, parallel = true, maxWorkers = 3, examType = 'end_sem', maxMarks = null) => {
  const payload = {
    root_directory: rootDirectory,
    parallel,
    max_workers: maxWorkers,
    exam_type: examType
  };
  if (maxMarks !== null) {
    payload.max_marks = maxMarks;
  }

  const response = await api.post('/batch/process-courses', payload, {
    headers: { 'Content-Type': 'application/json' }
  });
  return response.data;
};

/**
 * Subscribe to real-time batch processing events via Server-Sent Events.
 * @param {function} onEvent - Callback(eventData) called for each event
 * @returns {EventSource} - Call .close() to disconnect
 */
export const subscribeToBatchStream = (onEvent) => {
  const eventSource = new EventSource(`${API_BASE_URL}/batch/stream`);
  
  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type !== 'heartbeat') {
        onEvent(data);
      }
    } catch (err) {
      console.error('SSE parse error:', err);
    }
  };

  eventSource.onerror = (err) => {
    console.error('SSE connection error:', err);
    // Don't auto-close - the browser will try to reconnect
  };

  return eventSource;
};

/**
 * Stop the currently running batch processing.
 */
export const stopBatchProcessing = async () => {
  const response = await api.post('/batch/stop');
  return response.data;
};

export const getBatchStatus = async () => {
  const response = await api.get('/batch/status');
  return response.data;
};

export const getBatchResults = async () => {
  const response = await api.get('/batch/results');
  return response.data;
};

export const getBatchResultsByCourse = async (courseCode) => {
  const response = await api.get(`/batch/results/${courseCode}`);
  return response.data;
};

export default api;
