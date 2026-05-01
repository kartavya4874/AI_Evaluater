import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { FiMenu, FiX, FiLogOut } from 'react-icons/fi';
import { useAuth } from '../context/AuthContext';
import './Navigation.css';

const Navigation = () => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const location = useLocation();
  const { user, logout } = useAuth();

  const isActive = (path) => location.pathname === path;

  if (!user) return null;

  return (
    <nav className="nav">
      <div className="nav-inner">
        <Link to="/" className="nav-brand">
          AI Examiner
        </Link>

        <button
          className="nav-mobile-toggle"
          onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          aria-label="Toggle menu"
        >
          {isMobileMenuOpen ? <FiX size={20} /> : <FiMenu size={20} />}
        </button>

        <ul className={`nav-links ${isMobileMenuOpen ? 'open' : ''}`}>
          <li><Link to="/" className={`nav-link ${isActive('/') ? 'active' : ''}`} onClick={() => setIsMobileMenuOpen(false)}>Home</Link></li>
          <li><Link to="/dashboard" className={`nav-link ${isActive('/dashboard') ? 'active' : ''}`} onClick={() => setIsMobileMenuOpen(false)}>Dashboard</Link></li>
          <li><Link to="/evaluate" className={`nav-link ${isActive('/evaluate') ? 'active' : ''}`} onClick={() => setIsMobileMenuOpen(false)}>Evaluate</Link></li>
          <li><Link to="/management" className={`nav-link ${isActive('/management') ? 'active' : ''}`} onClick={() => setIsMobileMenuOpen(false)}>Manage</Link></li>
          <li><Link to="/history" className={`nav-link ${isActive('/history') ? 'active' : ''}`} onClick={() => setIsMobileMenuOpen(false)}>History</Link></li>
          <li><Link to="/batch" className={`nav-link nav-link-accent ${isActive('/batch') ? 'active' : ''}`} onClick={() => setIsMobileMenuOpen(false)}>Batch Mode</Link></li>
          <li><Link to="/batch-results" className={`nav-link ${isActive('/batch-results') ? 'active' : ''}`} onClick={() => setIsMobileMenuOpen(false)}>Results</Link></li>
        </ul>

        <div className="nav-user">
          <span className="nav-user-email">{user.email}</span>
          <button className="nav-logout" onClick={logout} title="Sign out">
            <FiLogOut size={16} />
          </button>
        </div>
      </div>
    </nav>
  );
};

export default Navigation;
