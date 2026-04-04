import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { FiMenu, FiX } from 'react-icons/fi';
import './Navigation.css';

const Navigation = () => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const location = useLocation();

  const isActive = (path) => location.pathname === path;

  return (
    <nav className="navbar">
      <div className="navbar-container">
        <Link to="/" className="navbar-logo">
          <span className="logo-icon">📝</span>
          AI Examiner
        </Link>

        <button 
          className="mobile-menu-toggle"
          onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
        >
          {isMobileMenuOpen ? <FiX size={24} /> : <FiMenu size={24} />}
        </button>

        <ul className={`nav-menu ${isMobileMenuOpen ? 'active' : ''}`}>
          <li className="nav-item">
            <Link 
              to="/" 
              className={`nav-link ${isActive('/') ? 'active' : ''}`}
              onClick={() => setIsMobileMenuOpen(false)}
            >
              Home
            </Link>
          </li>
          <li className="nav-item">
            <Link 
              to="/dashboard" 
              className={`nav-link ${isActive('/dashboard') ? 'active' : ''}`}
              onClick={() => setIsMobileMenuOpen(false)}
            >
              Dashboard
            </Link>
          </li>
          <li className="nav-item">
            <Link 
              to="/evaluate" 
              className={`nav-link nav-link-primary ${isActive('/evaluate') ? 'active' : ''}`}
              onClick={() => setIsMobileMenuOpen(false)}
            >
              Evaluate Now
            </Link>
          </li>
          <li className="nav-item">
            <Link 
              to="/management" 
              className={`nav-link ${isActive('/management') ? 'active' : ''}`}
              onClick={() => setIsMobileMenuOpen(false)}
            >
              Management
            </Link>
          </li>
          <li className="nav-item">
            <Link 
              to="/history" 
              className={`nav-link ${isActive('/history') ? 'active' : ''}`}
              onClick={() => setIsMobileMenuOpen(false)}
            >
              History
            </Link>
          </li>
          <li className="nav-item">
            <Link 
              to="/batch" 
              className={`nav-link nav-link-primary ${isActive('/batch') ? 'active' : ''}`}
              onClick={() => setIsMobileMenuOpen(false)}
            >
              Batch Mode
            </Link>
          </li>
          <li className="nav-item">
            <Link 
              to="/batch-results" 
              className={`nav-link ${isActive('/batch-results') ? 'active' : ''}`}
              onClick={() => setIsMobileMenuOpen(false)}
            >
              Batch Results
            </Link>
          </li>
        </ul>
      </div>
    </nav>
  );
};

export default Navigation;
