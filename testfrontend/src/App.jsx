import { useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import Todos from './pages/Todos';
import Metrics from './pages/Metrics';
import Jobs from './pages/Jobs';
import Docs from './pages/Docs';
import Profile from './pages/Profile';
import Calendar from './pages/Calendar';
import SessionBar from './components/SessionBar';
import { api } from './api';
import './styles/app.css';

function ApiKeyGate({ onUnlock }) {
  const [key, setKey] = useState('');
  const [error, setError] = useState('');
  const [checking, setChecking] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!key.trim()) return;
    setChecking(true);
    setError('');
    try {
      const res = await fetch('/api/v1/todos', { headers: { 'X-API-Key': key.trim() } });
      if (res.ok) {
        localStorage.setItem('focusos_api_key', key.trim());
        onUnlock();
      } else {
        setError('Wrong key, try again');
      }
    } catch {
      setError('Could not reach server');
    } finally {
      setChecking(false);
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: '#eef0f8',
    }}>
      <div className="glass-card" style={{ width: 360, padding: '36px 32px' }}>
        <h2 style={{ fontSize: 22, fontWeight: 700, color: '#1a1a2e', marginBottom: 8 }}>FocusOS</h2>
        <p style={{ fontSize: 14, color: '#475569', marginBottom: 24 }}>Enter your API key to continue.</p>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <input
            className="input"
            type="password"
            placeholder="API key"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            autoFocus
          />
          {error && <p style={{ fontSize: 13, color: '#e11d48', margin: 0 }}>{error}</p>}
          <button className="btn btn-primary" type="submit" disabled={checking}>
            {checking ? 'Checking...' : 'Unlock'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default function App() {
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('focusos_api_key'));
  const [activeSession, setActiveSession] = useState(null);
  const queryClient = useQueryClient();

  // Prefetch common data on load so tabs feel instant
  useEffect(() => {
    if (!apiKey) return;
    const todayStr = new Date().toISOString().slice(0, 10);
    queryClient.prefetchQuery({
      queryKey: ['todos', 'pending'],
      queryFn: () => api.getTodos('pending').then((d) => d.todos),
    });
    queryClient.prefetchQuery({
      queryKey: ['routines'],
      queryFn: () => api.getRoutines().then((d) => d.routines),
    });
    queryClient.prefetchQuery({
      queryKey: ['daily-plan', todayStr],
      queryFn: () => api.getDailyPlan(todayStr).then((d) => d.content),
      staleTime: Infinity,
    });
  }, [apiKey]);

  // Restore any in-progress session on load
  useEffect(() => {
    if (!apiKey) return;
    api.getActiveSession().then((session) => {
      if (session) {
        setActiveSession({
          sessionId: session.id,
          todoId: session.todo_id,
          todoTitle: session.todo_title,
          startedAt: session.started_at,
        });
      }
    }).catch(() => {});
  }, [apiKey]);

  if (!apiKey) {
    return <ApiKeyGate onUnlock={() => setApiKey(localStorage.getItem('focusos_api_key'))} />;
  }

  return (
    <BrowserRouter>
      <nav className="navbar">
        <span className="navbar-brand">FocusOS</span>
        <div className="navbar-links">
          <NavLink
            to="/"
            end
            className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
          >
            Todos
          </NavLink>
          <NavLink
            to="/metrics"
            className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
          >
            Metrics
          </NavLink>
          <NavLink
            to="/jobs"
            className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
          >
            Job Portal
          </NavLink>
          <NavLink
            to="/docs"
            className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
          >
            Docs
          </NavLink>
          <NavLink
            to="/calendar"
            className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
          >
            Calendar
          </NavLink>
          <NavLink
            to="/profile"
            className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
          >
            Profile
          </NavLink>
        </div>
      </nav>

      <main className="main-content">
        <Routes>
          <Route
            path="/"
            element={
              <Todos
                activeSession={activeSession}
                setActiveSession={setActiveSession}
              />
            }
          />
          <Route path="/metrics" element={<Metrics />} />
          <Route path="/jobs" element={<Jobs />} />
          <Route path="/docs" element={<Docs />} />
          <Route
            path="/calendar"
            element={
              <Calendar
                activeSession={activeSession}
                setActiveSession={setActiveSession}
              />
            }
          />
          <Route path="/profile" element={<Profile />} />
        </Routes>
      </main>

      {activeSession && (
        <SessionBar
          key={activeSession.sessionId}
          activeSession={activeSession}
          setActiveSession={setActiveSession}
        />
      )}
    </BrowserRouter>
  );
}
