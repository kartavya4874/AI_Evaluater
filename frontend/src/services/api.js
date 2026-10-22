import axios from 'axios';

const API_BASE_URL = process.env.NODE_ENV === 'production' 
  ? (process.env.REACT_APP_API_URL || '/api') 
  : (process.env.REACT_APP_API_URL || 'http://localhost:5000/api');

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
});

// Request interceptor — attach JWT token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor — handle 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      const loginPath = `${process.env.REACT_APP_BASENAME || ''}/login`;
      if (window.location.pathname !== loginPath) {
        window.location.href = loginPath;
      }
    }
    return Promise.reject(error);
  }
);

// ==================== AUTH APIs ====================

export const login = async (credential) => {
  const response = await api.post('/auth/google', { credential });
  return response.data;
};

export const getMe = async () => {
  const response = await api.get('/auth/me');
  return response.data;
};

// ==================== Teacher APIs ====================

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

// ==================== Student APIs ====================

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

// ==================== Evaluation APIs ====================

export const uploadModelAnswer = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await api.post('/upload-model-answer', formData, { timeout: 900000 });
  return response.data;
};

export const evaluateAnswer = async (formDataOrFile, modelAnswer, maxMarks, question = '', teacherId = null, studentId = null) => {
  let formData;
  if (formDataOrFile instanceof FormData) {
    formData = formDataOrFile;
  } else {
    formData = new FormData();
    formData.append('student_file', formDataOrFile);
    formData.append('model_answer', modelAnswer);
    formData.append('max_marks', maxMarks);
    if (question) formData.append('question', question);
    if (teacherId) formData.append('teacher_id', teacherId);
    if (studentId) formData.append('student_id', studentId);
  }
  const response = await api.post('/evaluate-answer', formData, {
    timeout: 900000,
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
  const response = await api.post('/ocr-only', formData, { timeout: 900000 });
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

export const subscribeToBatchStream = () => {
  throw new Error('Legacy batch streaming is retired. Use Workspace & progress.');
};

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

// ==================== FOLDER UPLOAD ====================

export const uploadBatchFolder = async (files, onProgress) => {
  const manifest = Array.from(files, file => ({ path: file.webkitRelativePath || file.name, size: file.size }));
  const identity = JSON.stringify(manifest.map((item, index) => ({ ...item, modified: files[index].lastModified })));
  const storageKey = 'pending-folder-upload';
  let pending;
  try { pending = JSON.parse(localStorage.getItem(storageKey)); } catch (_) { /* start fresh */ }
  const sessionId = pending?.identity === identity ? pending.id : crypto.randomUUID().replaceAll('-', '');
  localStorage.setItem(storageKey, JSON.stringify({ id: sessionId, identity }));
  await api.post('/workspace/uploads', { session_id: sessionId, files: manifest });
  const total = manifest.reduce((sum, file) => sum + file.size, 0);
  let completed = 0;
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    const completedBeforeFile = completed;
    const hash = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
    const checksum = Array.from(new Uint8Array(hash), b => b.toString(16).padStart(2, '0')).join('');
    let lastError;
    for (let retry = 0; retry < 3; retry++) {
      try {
        await api.put(`/workspace/uploads/${sessionId}/${i}`, file, {
          timeout: 120000,
          headers: { 'Content-Type': 'application/pdf', 'X-Content-SHA256': checksum },
          onUploadProgress: event => onProgress?.(Math.round(100 * (completedBeforeFile + Math.min(event.loaded, file.size)) / total)),
        });
        lastError = null; break;
      } catch (error) {
        lastError = error;
        if (error.response && error.response.status < 500 && error.response.status !== 429) {
          if (/new (upload )?session/.test(error.response.data?.error || '')) localStorage.removeItem(storageKey);
          throw error;
        }
        await new Promise(resolve => setTimeout(resolve, 1000 * (retry + 1)));
      }
    }
    if (lastError) throw lastError;
    completed += file.size;
    onProgress?.(Math.round(100 * completed / total));
  }
  const response = await api.post(`/workspace/uploads/${sessionId}/complete`);
  localStorage.removeItem(storageKey);
  return response.data;
};

export default api;
