import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { FiMenu, FiX, FiLogOut } from 'react-icons/fi';
import { useAuth } from '../context/AuthContext';
import './Navigation.css';

const Navigation = () => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [evaluateOpen, setEvaluateOpen] = useState(false);
  const location = useLocation();
  const { user, logout } = useAuth();

  const isActive = (path) => location.pathname === path;
  useEffect(() => { setEvaluateOpen(false); setIsMobileMenuOpen(false); }, [location.pathname]);

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
          <li className="nav-evaluate" onBlur={e => { if (!e.currentTarget.contains(e.relatedTarget)) setEvaluateOpen(false); }} onKeyDown={e => { if (e.key === 'Escape') { setEvaluateOpen(false); e.currentTarget.querySelector('button').focus(); } }}>
            <button className={`nav-link nav-dropdown-toggle ${location.pathname.startsWith('/evaluate') ? 'active' : ''}`} aria-expanded={evaluateOpen} aria-controls="evaluate-options" onClick={() => setEvaluateOpen(open => !open)}>Evaluate ▾</button>
            {evaluateOpen && <ul id="evaluate-options" className="nav-dropdown">
              {user.role === 'admin' ? <li><Link to="/evaluate/single" className="nav-link" onClick={() => setEvaluateOpen(false)}>Single</Link></li> : <li><span className="nav-link" aria-disabled="true">Single (admin only)</span></li>}
              <li><Link to="/evaluate/batch" className="nav-link" onClick={() => setEvaluateOpen(false)}>Batch</Link></li>
            </ul>}
          </li>
          <li><Link to="/results" className="nav-link" onClick={() => setIsMobileMenuOpen(false)}>Review results</Link></li>
          <li><Link to="/teacher-comparison" className={`nav-link ${isActive('/teacher-comparison') ? 'active' : ''}`}>Teacher comparison</Link></li>
          {user.role === 'admin' && <li><Link to="/manage-results" className={`nav-link ${isActive('/manage-results') ? 'active' : ''}`}>Manage answer sheets</Link></li>}
          <li><Link to="/guide" className={`nav-link ${isActive('/guide') ? 'active' : ''}`} onClick={() => setIsMobileMenuOpen(false)}>User guide</Link></li>
          {user.role === 'admin' && <li><Link to="/management" className={`nav-link ${isActive('/management') ? 'active' : ''}`} onClick={() => setIsMobileMenuOpen(false)}>Courses & accounts</Link></li>}
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
