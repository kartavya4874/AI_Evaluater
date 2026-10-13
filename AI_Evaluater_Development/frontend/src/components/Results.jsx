import React from 'react';

const Results = ({ evaluation }) => {
  if (!evaluation) return null;

  const { marks_awarded, percentage, strengths, missing_points, feedback, grade, extracted_text } = evaluation;

  return (
    <div className="results-container">
      <h2 className="results-title">📊 Evaluation Results</h2>
      
      <div className="score-card">
        <div className="score-main">
          <div className="marks-display">
            <span className="marks-number">{marks_awarded}</span>
            <span className="marks-total">/ {percentage ? Math.round(marks_awarded * 100 / percentage) : 'N/A'}</span>
          </div>
          <div className="grade-badge">{grade}</div>
        </div>
        <div className="percentage">{percentage}%</div>
      </div>

      <div className="evaluation-section strengths-section">
        <h3>✅ Strengths</h3>
        <ul>
          {strengths && strengths.length > 0 ? (
            strengths.map((strength, index) => (
              <li key={index}>{strength}</li>
            ))
          ) : (
            <li>No strengths identified</li>
          )}
        </ul>
      </div>

      <div className="evaluation-section missing-section">
        <h3>❌ Missing Points</h3>
        <ul>
          {missing_points && missing_points.length > 0 ? (
            missing_points.map((point, index) => (
              <li key={index}>{point}</li>
            ))
          ) : (
            <li>No missing points identified</li>
          )}
        </ul>
      </div>

      <div className="evaluation-section feedback-section">
        <h3>📝 Feedback</h3>
        <p>{feedback}</p>
      </div>

      {extracted_text && (
        <details className="extracted-text-section">
          <summary>View Extracted Handwritten Text</summary>
          <pre className="extracted-text">{extracted_text}</pre>
        </details>
      )}
    </div>
  );
};

export default Results;
