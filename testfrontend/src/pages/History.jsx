import { useState, useEffect } from 'react';
import { api } from '../api';

function formatDuration(seconds) {
  if (!seconds) return '—';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m`;
  return `${seconds}s`;
}

function formatDate(dt) {
  if (!dt) return '—';
  return new Date(dt).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

export default function History() {
  const [todos, setTodos] = useState([]);
  const [selectedId, setSelectedId] = useState('all');
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);

  // Load all todos once
  useEffect(() => {
    api.getTodos().then((data) => setTodos(data.todos));
  }, []);

  // Reload sessions whenever selection or todos change
  useEffect(() => {
    if (todos.length === 0) return;
    setLoading(true);

    if (selectedId === 'all') {
      Promise.all(
        todos.map((t) =>
          api.getSessions(t.id).then((d) =>
            d.sessions.map((s) => ({ ...s, todoTitle: t.title }))
          )
        )
      )
        .then((results) => {
          const all = results
            .flat()
            .sort((a, b) => new Date(b.started_at) - new Date(a.started_at));
          setSessions(all);
        })
        .finally(() => setLoading(false));
    } else {
      const todo = todos.find((t) => t.id === Number(selectedId));
      api
        .getSessions(selectedId)
        .then((data) =>
          setSessions(
            data.sessions
              .map((s) => ({ ...s, todoTitle: todo?.title || '' }))
              .sort((a, b) => new Date(b.started_at) - new Date(a.started_at))
          )
        )
        .finally(() => setLoading(false));
    }
  }, [selectedId, todos]);

  return (
    <div className="page">
      <div className="history-header">
        <h2 className="page-title">Session History</h2>
        <select
          className="input select"
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
        >
          <option value="all">All todos</option>
          {todos.map((t) => (
            <option key={t.id} value={t.id}>
              {t.title}
            </option>
          ))}
        </select>
      </div>

      {loading && <p className="empty-state">Loading…</p>}

      {!loading && sessions.length === 0 && (
        <p className="empty-state">No sessions found.</p>
      )}

      {!loading &&
        sessions.map((s) => (
          <div key={s.id} className="session-card">
            <div className="session-card-top">
              <span className="session-card-title">{s.todoTitle}</span>
              <span className="session-card-date">{formatDate(s.started_at)}</span>
              <span className="session-card-duration">{formatDuration(s.seconds_spent)}</span>
            </div>
            {s.notes && <p className="session-card-notes">{s.notes}</p>}
          </div>
        ))}
    </div>
  );
}
