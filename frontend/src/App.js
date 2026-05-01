import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Navigation from './components/Navigation';
import Login from './pages/auth/Login';
import Home from './pages/Home';
import Dashboard from './pages/Dashboard';
import Evaluate from './pages/Evaluate';
import Results from './pages/Results';
import Management from './pages/Management';
import EvaluationHistory from './pages/EvaluationHistory';
import BatchEvaluate from './pages/BatchEvaluate';
import BatchResults from './pages/BatchResults';
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
        <Route path="/" element={<ProtectedRoute><Home /></ProtectedRoute>} />
        <Route path="/dashboard" element={<ProtectedRoute><Dashboard setLoading={setAppLoading} /></ProtectedRoute>} />
        <Route path="/evaluate" element={<ProtectedRoute><Evaluate setLoading={setAppLoading} /></ProtectedRoute>} />
        <Route path="/results/:evaluationId" element={<ProtectedRoute><Results /></ProtectedRoute>} />
        <Route path="/management" element={<ProtectedRoute><Management setLoading={setAppLoading} /></ProtectedRoute>} />
        <Route path="/history" element={<ProtectedRoute><EvaluationHistory setLoading={setAppLoading} /></ProtectedRoute>} />
        <Route path="/batch" element={<ProtectedRoute><BatchEvaluate setLoading={setAppLoading} /></ProtectedRoute>} />
        <Route path="/batch-results" element={<ProtectedRoute><BatchResults setLoading={setAppLoading} /></ProtectedRoute>} />
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
      <Router>
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
