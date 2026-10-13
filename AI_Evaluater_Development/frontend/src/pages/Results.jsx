import React, { useEffect, useState } from 'react';
import { Link, useParams, useLocation } from 'react-router-dom';
import './Results.css';

const Results = () => {
  const { evaluationId } = useParams();
  const location = useLocation();
  const [evaluation, setEvaluation] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Get evaluation data from location state if available
    if (location.state && location.state.evaluation) {
      console.log('Received evaluation data:', location.state.evaluation);
      setEvaluation(location.state.evaluation);
      setLoading(false);
    } else if (evaluationId) {
      // TODO: Fetch evaluation from backend using evaluationId
      console.log('No evaluation data in state, evaluationId:', evaluationId);
      setLoading(false);
    } else {
      console.log('No evaluation data available');
      setLoading(false);
    }
  }, [evaluationId, location]);

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
            <h1>Evaluation Complete!</h1>
            <p className="results-message">Your evaluation has been successfully submitted and saved.</p>
            
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
