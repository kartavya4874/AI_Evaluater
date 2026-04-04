import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Navigation from './components/Navigation';
import Home from './pages/Home';
import Dashboard from './pages/Dashboard';
import Evaluate from './pages/Evaluate';
import Results from './pages/Results';
import Management from './pages/Management';
import EvaluationHistory from './pages/EvaluationHistory';
import BatchEvaluate from './pages/BatchEvaluate';
import BatchResults from './pages/BatchResults';
import './App.css';

function App() {
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('');

  const setAppLoading = (isLoading, message = '') => {
    setLoading(isLoading);
    setLoadingMessage(message);
  };

  return (
    <Router>
      <div className="App">
        <Navigation />
        {loading && (
          <div className="app-loading-overlay">
            <div className="app-loading-container">
              <div className="loading-spinner"></div>
              <p className="loading-message">{loadingMessage || 'Processing...'}</p>
            </div>
          </div>
        )}
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/dashboard" element={<Dashboard setLoading={setAppLoading} />} />
          <Route path="/evaluate" element={<Evaluate setLoading={setAppLoading} />} />
          <Route path="/results/:evaluationId" element={<Results />} />
          <Route path="/management" element={<Management setLoading={setAppLoading} />} />
          <Route path="/history" element={<EvaluationHistory setLoading={setAppLoading} />} />
          <Route path="/batch" element={<BatchEvaluate setLoading={setAppLoading} />} />
          <Route path="/batch-results" element={<BatchResults setLoading={setAppLoading} />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
