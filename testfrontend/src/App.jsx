import { useState } from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import Todos from './pages/Todos';
import History from './pages/History';
import Jobs from './pages/Jobs';
import Docs from './pages/Docs';
import Profile from './pages/Profile';
import SessionBar from './components/SessionBar';
import './styles/app.css';

export default function App() {
  const [todos, setTodos] = useState([]);
  // activeSession: { sessionId, todoId, todoTitle, startedAt }
  const [activeSession, setActiveSession] = useState(null);

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
            to="/history"
            className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
          >
            History
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
                todos={todos}
                setTodos={setTodos}
                activeSession={activeSession}
                setActiveSession={setActiveSession}
              />
            }
          />
          <Route path="/history" element={<History />} />
          <Route path="/jobs" element={<Jobs />} />
          <Route path="/docs" element={<Docs />} />
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
