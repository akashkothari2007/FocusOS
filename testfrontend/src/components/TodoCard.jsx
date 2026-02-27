import { useState } from 'react';
import { api } from '../api';

function formatDate(dt) {
  if (!dt) return null;
  return new Date(dt).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// psycopg returns JSONB as a parsed object, but handle string just in case
function parseSubtasks(raw) {
  if (!raw) return [];
  if (Array.isArray(raw)) return raw;
  try { return JSON.parse(raw); } catch { return []; }
}

export default function TodoCard({ todo, borderColor, isActiveSession, onStartSession, onMarkDone, onUpdate }) {
  const [expanded, setExpanded] = useState(false);
  const [editingDesc, setEditingDesc] = useState(false);
  const [desc, setDesc] = useState(todo.description || '');
  const [newSubtask, setNewSubtask] = useState('');
  const [loading, setLoading] = useState(false);

  const subtasks = parseSubtasks(todo.subtasks);

  async function saveDescription() {
    setEditingDesc(false);
    if (desc === (todo.description || '')) return;
    try {
      const updated = await api.updateTodo(todo.id, { description: desc });
      onUpdate(updated);
    } catch {
      setDesc(todo.description || '');
    }
  }

  async function toggleSubtask(subtaskId) {
    const newSubtasks = subtasks.map((s) =>
      s.id === subtaskId ? { ...s, status: s.status === 'done' ? 'pending' : 'done' } : s
    );
    const updated = await api.updateTodo(todo.id, { subtasks: newSubtasks });
    onUpdate(updated);
  }

  async function handleAddSubtask(e) {
    e.preventDefault();
    if (!newSubtask.trim()) return;
    const nextId = subtasks.length > 0 ? Math.max(...subtasks.map((s) => s.id)) + 1 : 1;
    const newSubtasks = [...subtasks, { id: nextId, title: newSubtask.trim(), status: 'pending' }];
    const updated = await api.updateTodo(todo.id, { subtasks: newSubtasks });
    onUpdate(updated);
    setNewSubtask('');
  }

  async function handleMarkDone() {
    setLoading(true);
    try {
      await api.updateTodo(todo.id, { status: 'done' });
      onMarkDone(todo.id);
    } finally {
      setLoading(false);
    }
  }

  function handlePlayClick(e) {
    e.stopPropagation();
    onStartSession(todo);
  }

  return (
    <div className="todo-card" style={{ borderLeftColor: borderColor }}>
      <div className="todo-card-header" onClick={() => setExpanded((v) => !v)}>
        <div className="todo-card-title-row">
          <span className="todo-title">{todo.title}</span>
          {todo.due_date && <span className="due-date">{formatDate(todo.due_date)}</span>}
        </div>
        <button
          className={`btn-play${isActiveSession ? ' active-session' : ''}`}
          onClick={handlePlayClick}
          title={isActiveSession ? 'Session in progress' : 'Start session'}
        >
          {isActiveSession ? '●' : '▶'}
        </button>
      </div>

      {expanded && (
        <div className="todo-card-body">
          {editingDesc ? (
            <textarea
              className="input textarea"
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              onBlur={saveDescription}
              autoFocus
              rows={3}
            />
          ) : (
            <p className="todo-desc" onClick={() => setEditingDesc(true)} title="Click to edit">
              {desc || <span className="placeholder">Add a description…</span>}
            </p>
          )}

          <div className="subtasks">
            {subtasks.map((s) => (
              <label key={s.id} className="subtask-row">
                <input
                  type="checkbox"
                  checked={s.status === 'done'}
                  onChange={() => toggleSubtask(s.id)}
                />
                <span className={s.status === 'done' ? 'subtask-done' : ''}>{s.title}</span>
              </label>
            ))}
            <form className="add-subtask-form" onSubmit={handleAddSubtask}>
              <input
                className="input input-sm"
                placeholder="Add subtask…"
                value={newSubtask}
                onChange={(e) => setNewSubtask(e.target.value)}
              />
            </form>
          </div>

          <div className="todo-card-footer">
            <button className="btn btn-done" onClick={handleMarkDone} disabled={loading}>
              {loading ? '…' : 'Mark done'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
