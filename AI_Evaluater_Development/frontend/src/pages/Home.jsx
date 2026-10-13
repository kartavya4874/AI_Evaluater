import React from 'react';
import { Link } from 'react-router-dom';
import { FiArrowRight, FiCheckCircle, FiZap, FiBarChart2, FiCpu, FiFileText, FiShield } from 'react-icons/fi';
import './Home.css';

const Home = () => {
  return (
    <div className="home">
      <section className="hero">
        <div className="hero-content">
          <div className="hero-badge">Automated Grading Platform</div>
          <h1 className="hero-title">
            Evaluate answers<br />
            <span className="hero-highlight">with precision.</span>
          </h1>
          <p className="hero-subtitle">
            Upload student answer sheets, let AI analyze them against model answers,
            and get detailed feedback with grades — in seconds, not hours.
          </p>
          <div className="hero-actions">
            <Link to="/evaluate" className="hero-btn hero-btn-primary">
              Start Evaluating <FiArrowRight />
            </Link>
            <Link to="/batch" className="hero-btn hero-btn-secondary">
              Batch Mode
            </Link>
          </div>
        </div>
        <div className="hero-visual">
          <div className="hero-card">
            <div className="hero-card-header">
              <span className="hero-card-dot" />
              <span className="hero-card-dot" />
              <span className="hero-card-dot" />
            </div>
            <div className="hero-card-body">
              <div className="hero-card-line w-80" />
              <div className="hero-card-line w-60" />
              <div className="hero-card-line w-90" />
              <div className="hero-card-divider" />
              <div className="hero-card-score">
                <span className="score-num">87</span>
                <span className="score-label">/100</span>
              </div>
              <div className="hero-card-grade">A</div>
            </div>
          </div>
        </div>
      </section>

      <section className="features">
        <div className="features-header">
          <h2>Built for Educators</h2>
          <p>Everything you need to streamline the grading process.</p>
        </div>
        <div className="features-grid">
          <div className="feature">
            <div className="feature-icon"><FiZap /></div>
            <h3>Fast Processing</h3>
            <p>Evaluate hundreds of answer sheets in minutes with parallel processing.</p>
          </div>
          <div className="feature">
            <div className="feature-icon"><FiCheckCircle /></div>
            <h3>Consistent Grading</h3>
            <p>Uniform evaluation criteria eliminates bias and subjectivity.</p>
          </div>
          <div className="feature">
            <div className="feature-icon"><FiBarChart2 /></div>
            <h3>Detailed Analytics</h3>
            <p>Strengths, weaknesses, and actionable feedback for every student.</p>
          </div>
          <div className="feature">
            <div className="feature-icon"><FiCpu /></div>
            <h3>AI-Powered OCR</h3>
            <p>Reads handwritten text from scanned PDFs with high accuracy.</p>
          </div>
          <div className="feature">
            <div className="feature-icon"><FiFileText /></div>
            <h3>Batch Processing</h3>
            <p>Upload entire course folders and evaluate all students at once.</p>
          </div>
          <div className="feature">
            <div className="feature-icon"><FiShield /></div>
            <h3>Secure & Private</h3>
            <p>Answer sheets are processed and cached locally with encryption.</p>
          </div>
        </div>
      </section>

      <section className="how-it-works">
        <h2>How It Works</h2>
        <div className="steps">
          <div className="step-item">
            <div className="step-num">1</div>
            <div className="step-content">
              <h3>Upload Model Answer</h3>
              <p>Provide the correct answer as a PDF or paste it as text.</p>
            </div>
          </div>
          <div className="step-connector" />
          <div className="step-item">
            <div className="step-num">2</div>
            <div className="step-content">
              <h3>Submit Student Answer</h3>
              <p>Upload the student's handwritten or typed answer sheet.</p>
            </div>
          </div>
          <div className="step-connector" />
          <div className="step-item">
            <div className="step-num">3</div>
            <div className="step-content">
              <h3>Get Results</h3>
              <p>Receive marks, grade, detailed feedback, and areas for improvement.</p>
            </div>
          </div>
        </div>
      </section>

      <footer className="home-footer">
        <p>&copy; 2026 AI Examiner. All rights reserved.</p>
      </footer>
    </div>
  );
};

export default Home;
