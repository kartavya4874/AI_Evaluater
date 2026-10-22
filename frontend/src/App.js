import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Navigation from './components/Navigation';
import Login from './pages/auth/Login';
import Administration from './pages/Administration';
import ManageResults from './pages/ManageResults';
import TeacherComparison from './pages/TeacherComparison';
import Dashboard from './pages/Dashboard';
import Evaluate from './pages/Evaluate';
import Results from './pages/Results';
import EvaluationHistory from './pages/EvaluationHistory';
import BatchResults from './pages/BatchResults';
import ResultsOverview from './pages/ResultsOverview';
import Workspace from './pages/Workspace';
import UserGuide from './pages/UserGuide';
import './App.css';

const AppLayout = ({ loading, loadingMessage, setAppLoading }) => {
  const location = useLocation();
  const isLoginPage = location.pathname === '/login';

  return (
    <div className="App">
      {!isLoginPage && <Navigation />}
      {loading && (
        <div className="app-loading-overlay">
          <div className="app-loading-container">
            <div className="loading-spinner"></div>
            <p className="loading-message">{loadingMessage || 'Processing...'}</p>
          </div>
        </div>
      )}
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/guide" element={<ProtectedRoute><UserGuide /></ProtectedRoute>} />
        <Route path="/" element={<ProtectedRoute><Navigate to="/evaluate/batch" replace /></ProtectedRoute>} />
        <Route path="/dashboard" element={<ProtectedRoute adminOnly><Dashboard setLoading={setAppLoading} /></ProtectedRoute>} />
        <Route path="/evaluate" element={<ProtectedRoute><Navigate to="/evaluate/batch" replace /></ProtectedRoute>} />
        <Route path="/evaluate/single" element={<ProtectedRoute adminOnly><Evaluate setLoading={setAppLoading} /></ProtectedRoute>} />
        <Route path="/evaluate/batch" element={<ProtectedRoute><Workspace /></ProtectedRoute>} />
        <Route path="/results/:evaluationId" element={<ProtectedRoute adminOnly><Results /></ProtectedRoute>} />
        <Route path="/management" element={<ProtectedRoute adminOnly><Administration /></ProtectedRoute>} />
        <Route path="/manage-results" element={<ProtectedRoute adminOnly><ManageResults /></ProtectedRoute>} />
        <Route path="/teacher-comparison" element={<ProtectedRoute><TeacherComparison /></ProtectedRoute>} />
        <Route path="/history" element={<ProtectedRoute adminOnly><EvaluationHistory setLoading={setAppLoading} /></ProtectedRoute>} />
        <Route path="/batch" element={<ProtectedRoute><Navigate to="/evaluate/batch" replace /></ProtectedRoute>} />
        <Route path="/batch-results" element={<ProtectedRoute><Navigate to="/results" replace /></ProtectedRoute>} />
        <Route path="/results" element={<ProtectedRoute><ResultsOverview /></ProtectedRoute>} />
        <Route path="/legacy-results" element={<ProtectedRoute adminOnly><BatchResults setLoading={setAppLoading} /></ProtectedRoute>} />
        <Route path="*" element={<ProtectedRoute><main className="workspace"><h1>Page not found</h1><p>This address is unavailable. Use the navigation above to continue.</p></main></ProtectedRoute>} />
      </Routes>
    </div>
  );
};

function App() {
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('');

  const setAppLoading = (isLoading, message = '') => {
    setLoading(isLoading);
    setLoadingMessage(message);
  };

  return (
    <AuthProvider>
      <Router basename={process.env.REACT_APP_BASENAME || '/'}>
        <AppLayout
          loading={loading}
          loadingMessage={loadingMessage}
          setAppLoading={setAppLoading}
        />
      </Router>
    </AuthProvider>
  );
}

export default App;
