import React, { useEffect, useRef, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import api from '../../services/api';
import './Login.css';

export default function Login() {
  const { user, login } = useAuth();
  const button = useRef(null);
  const loginRef = useRef(login);
  loginRef.current = login;
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let alive = true;
    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.onerror = () => alive && setError('Google could not load. Check your connection and reload this page.');
    script.onload = async () => {
      try {
        const { data } = await api.get('/auth/config');
        if (!alive) return;
        if (!data.client_id) throw new Error('Google sign-in is awaiting administrator configuration.');
        window.google.accounts.id.initialize({ client_id: data.client_id, callback: async ({ credential }) => {
          setBusy(true); setError('');
          try { await loginRef.current(credential); }
          catch (e) { setError(e.response?.data?.error || 'Sign-in failed. Please try again.'); }
          finally { if (alive) setBusy(false); }
        }});
        window.google.accounts.id.renderButton(button.current, { theme: 'outline', size: 'large', text: 'signin_with' });
      } catch (e) { if (alive) setError(e.message); }
    };
    document.head.appendChild(script);
    return () => { alive = false; script.remove(); };
  }, []);
  if (user) return <Navigate to="/" replace />;
  return <main className="login-page"><div className="login-container"><div className="login-card">
    <div className="login-header"><h1>AI Examiner</h1><p>Your examination workspace</p></div>
    <p>Sign in with the Google email approved by your administrator.</p>
    {error && <p role="alert" className="login-error">{error}</p>}
    <div ref={button} />{busy && <p role="status">Checking your account…</p>}
    <p>Administrators manage courses and assignments. Faculty see only their assigned courses.</p>
  </div></div></main>;
}
