import React, { useEffect, useState } from 'react';
import { Link, useParams, useLocation } from 'react-router-dom';
import './Results.css';
import { getEvaluation } from '../services/api';

const Results = () => {
  const { evaluationId } = useParams();
  const location = useLocation();
  const [evaluation, setEvaluation] = useState(null);
  const [loading, setLoading] = useState(true);

  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true); setError(''); setEvaluation(null);
    const load = async () => {
      try {
        const data = location.state?.evaluation || (await getEvaluation(evaluationId)).evaluation;
        if (active) setEvaluation({ ...data, marks_awarded: data.marks_awarded ?? data.marks });
      } catch (failure) {
        if (active) setError(failure.response?.data?.error || 'Unable to load this evaluation.');
      } finally {
        if (active) setLoading(false);
      }
    };
    load();
    return () => { active = false; };
  }, [evaluationId, location.state]);

  if (loading) {
    return (
      <div className="results-page">
        <div className="results-container">
          <p>Loading results...</p>
        </div>
      </div>
    );
  }

  if (!evaluation) {
    return (
      <div className="results-page">
        <div className="results-container">
          <div className="results-content">
            <h1>Result unavailable</h1>
            <p role="alert" className="results-message">{error || 'No saved evaluation was found.'}</p>
            
            <div className="action-buttons">
              <Link to="/evaluate" className="btn btn-primary btn-lg">
                Evaluate Another
              </Link>
              <Link to="/dashboard" className="btn btn-secondary btn-lg">
                View Dashboard
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="results-page">
      <div className="results-container">
        <div className="results-content">
          <h1>Evaluation Complete!</h1>
          
          {/* Results Grid */}
          <div className="results-grid">
            <div className="result-card">
              <h3>Marks Awarded</h3>
              <div className="marks-display">
                <span className="marks-value">{evaluation.marks_awarded}</span>
                <span className="marks-max">/ {evaluation.max_marks}</span>
              </div>
            </div>

            <div className="result-card">
              <h3>Percentage</h3>
              <div className="percentage-display">{evaluation.percentage}%</div>
            </div>

            <div className="result-card">
              <h3>Grade</h3>
              <div className="grade-display">{evaluation.grade}</div>
            </div>
          </div>

          {/* Feedback Section */}
          <div className="result-section">
            <h3>Feedback</h3>
            <p className="feedback">{evaluation.feedback}</p>
          </div>

          {/* Strengths */}
          {evaluation.strengths && evaluation.strengths.length > 0 && (
            <div className="result-section">
              <h3>Strengths</h3>
              <ul className="points-list strengths">
                {evaluation.strengths.map((strength, idx) => (
                  <li key={idx}><span>✓</span> {strength}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Areas for Improvement */}
          {evaluation.missing_points && evaluation.missing_points.length > 0 && (
            <div className="result-section">
              <h3>Areas for Improvement</h3>
              <ul className="points-list improvements">
                {evaluation.missing_points.map((point, idx) => (
                  <li key={idx}><span>→</span> {point}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="action-buttons">
            <Link to="/evaluate" className="btn btn-primary btn-lg">
              Evaluate Another
            </Link>
            <Link to="/dashboard" className="btn btn-secondary btn-lg">
              View Dashboard
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Results;
