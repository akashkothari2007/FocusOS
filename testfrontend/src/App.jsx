import { useState } from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import Todos from './pages/Todos';
import History from './pages/History';
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
