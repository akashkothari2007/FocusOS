import { useState, useEffect } from 'react';
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

export default function App() {
  // activeSession: { sessionId, todoId, todoTitle, startedAt }
  const [activeSession, setActiveSession] = useState(null);

  // Restore any in-progress session on load
  useEffect(() => {
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
  }, []);

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
