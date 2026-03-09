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
  const [draggingIdx, setDraggingIdx] = useState(null);
  const [dragOverIdx, setDragOverIdx] = useState(null);

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
    const toggled = subtasks.map((s) =>
      s.id === subtaskId ? { ...s, status: s.status === 'done' ? 'pending' : 'done' } : s
    );
    // Completed subtasks sink to the bottom, pending stay on top
    const newSubtasks = [
      ...toggled.filter((s) => s.status === 'pending'),
      ...toggled.filter((s) => s.status === 'done'),
    ];
    const updated = await api.updateTodo(todo.id, { subtasks: newSubtasks });
    onUpdate(updated);
  }

  async function deleteSubtask(index) {
    const newSubtasks = subtasks.filter((_, i) => i !== index);
    const updated = await api.updateTodo(todo.id, { subtasks: newSubtasks });
    onUpdate(updated);
  }

  function handleDragStart(e, index) {
    setDraggingIdx(index);
    e.dataTransfer.effectAllowed = 'move';
  }

  function handleDragOver(e, index) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverIdx(index);
  }

  async function handleDrop(e, targetIndex) {
    e.preventDefault();
    if (draggingIdx === null || draggingIdx === targetIndex) {
      setDraggingIdx(null);
      setDragOverIdx(null);
      return;
    }
    const reordered = [...subtasks];
    const [moved] = reordered.splice(draggingIdx, 1);
    const insertAt = draggingIdx < targetIndex ? targetIndex - 1 : targetIndex;
    reordered.splice(insertAt, 0, moved);
    setDraggingIdx(null);
    setDragOverIdx(null);
    const updated = await api.updateTodo(todo.id, { subtasks: reordered });
    onUpdate(updated);
  }

  function handleDragEnd() {
    setDraggingIdx(null);
    setDragOverIdx(null);
  }

  async function handleAddSubtask(e) {
    e.preventDefault();
    if (!newSubtask.trim()) return;
    const nextId = subtasks.length > 0 ? Math.max(...subtasks.map((s) => s.id)) + 1 : 1;
    const newSubtasks = [
      ...subtasks.filter((s) => s.status === 'pending'),
      { id: nextId, title: newSubtask.trim(), status: 'pending' },
      ...subtasks.filter((s) => s.status === 'done'),
    ];
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
            {subtasks.map((s, i) => (
              <div
                key={s.id}
                className={[
                  'subtask-row',
                  draggingIdx === i ? 'subtask-dragging' : '',
                  dragOverIdx === i && draggingIdx !== i ? 'subtask-drag-over' : '',
                ].join(' ').trim()}
                draggable
                onDragStart={(e) => handleDragStart(e, i)}
                onDragOver={(e) => handleDragOver(e, i)}
                onDrop={(e) => handleDrop(e, i)}
                onDragEnd={handleDragEnd}
              >
                <span className="subtask-drag-handle">⠿</span>
                <input
                  type="checkbox"
                  checked={s.status === 'done'}
                  onChange={() => toggleSubtask(s.id)}
                />
                <span className={s.status === 'done' ? 'subtask-done' : ''}>{s.title}</span>
                <button
                  className="subtask-delete"
                  onClick={() => deleteSubtask(i)}
                  title="Delete subtask"
                >×</button>
              </div>
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
