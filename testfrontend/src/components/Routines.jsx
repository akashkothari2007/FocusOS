import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';

const BORDER_COLORS = ['#6366f1', '#ec4899', '#f59e0b', '#14b8a6'];
const routineColor = (id) => BORDER_COLORS[id % BORDER_COLORS.length];

function RoutineCard({ routine, borderColor }) {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [editingName, setEditingName] = useState(false);
  const [nameVal, setNameVal] = useState(routine.name);
  const [newItem, setNewItem] = useState('');

  async function handleRename() {
    const trimmed = nameVal.trim();
    if (!trimmed || trimmed === routine.name) {
      setNameVal(routine.name);
      setEditingName(false);
      return;
    }
    queryClient.setQueryData(['routines'], (old = []) =>
      old.map((r) => (r.id === routine.id ? { ...r, name: trimmed } : r))
    );
    setEditingName(false);
    await api.updateRoutine(routine.id, { name: trimmed });
  }

  async function handleDelete(e) {
    e.stopPropagation();
    queryClient.setQueryData(['routines'], (old = []) =>
      old.filter((r) => r.id !== routine.id)
    );
    await api.deleteRoutine(routine.id);
  }

  async function handleAddItem(e) {
    e.preventDefault();
    if (!newItem.trim()) return;
    const updated = [...routine.items, newItem.trim()];
    setNewItem('');
    queryClient.setQueryData(['routines'], (old = []) =>
      old.map((r) => (r.id === routine.id ? { ...r, items: updated } : r))
    );
    await api.updateRoutine(routine.id, { items: updated });
  }

  async function handleRemoveItem(idx) {
    const updated = routine.items.filter((_, i) => i !== idx);
    queryClient.setQueryData(['routines'], (old = []) =>
      old.map((r) => (r.id === routine.id ? { ...r, items: updated } : r))
    );
    await api.updateRoutine(routine.id, { items: updated });
  }

  return (
    <div className="todo-card" style={{ borderLeftColor: borderColor }}>
      <div className="todo-card-header routine-card-header" onClick={() => !editingName && setExpanded((e) => !e)}>
        <div className="todo-card-title-row">
          <span className="routine-chevron">{expanded ? '▾' : '▸'}</span>
          {editingName ? (
            <input
              className="input input-sm todo-title-input"
              value={nameVal}
              autoFocus
              onChange={(e) => setNameVal(e.target.value)}
              onBlur={handleRename}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleRename();
                if (e.key === 'Escape') { setNameVal(routine.name); setEditingName(false); }
              }}
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            <span
              className="todo-title"
              onDoubleClick={(e) => { e.stopPropagation(); setEditingName(true); }}
              title="Double-click to rename"
            >
              {routine.name}
            </span>
          )}
          {routine.items.length > 0 && (
            <span className="due-date">{routine.items.length}</span>
          )}
        </div>
        <button className="routine-delete-btn" onClick={handleDelete} title="Delete routine">✕</button>
      </div>

      {expanded && (
        <div className="todo-card-body">
          <div className="subtasks">
            {routine.items.map((item, idx) => (
              <div key={idx} className="subtask-row">
                <span style={{ flex: 1 }}>{item}</span>
                <button className="subtask-delete" onClick={() => handleRemoveItem(idx)}>✕</button>
              </div>
            ))}
            {routine.items.length === 0 && (
              <p style={{ fontSize: 13, color: '#94a3b8', margin: 0 }}>No items yet.</p>
            )}
          </div>
          <form className="add-subtask-form" onSubmit={handleAddItem} style={{ display: 'flex', gap: 8 }}>
            <input
              className="input input-sm"
              placeholder="Add item..."
              value={newItem}
              onChange={(e) => setNewItem(e.target.value)}
            />
            <button type="submit" className="btn btn-primary btn-sm" disabled={!newItem.trim()}>Add</button>
          </form>
        </div>
      )}
    </div>
  );
}

export default function Routines() {
  const queryClient = useQueryClient();
  const [newName, setNewName] = useState('');

  const { data } = useQuery({
    queryKey: ['routines'],
    queryFn: () => api.getRoutines().then((d) => d.routines),
  });
  const routines = data ?? [];

  async function handleCreate(e) {
    e.preventDefault();
    if (!newName.trim()) return;
    const name = newName.trim();
    setNewName('');
    const created = await api.createRoutine(name);
    queryClient.setQueryData(['routines'], (old = []) => [...old, created]);
  }

  return (
    <div>
      <form onSubmit={handleCreate} className="add-routine-form">
        <input
          className="input"
          placeholder="New routine name..."
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
        />
        <button type="submit" className="btn btn-primary" disabled={!newName.trim()}>Add</button>
      </form>
      <div className="todo-list">
        {routines.map((routine) => (
          <RoutineCard key={routine.id} routine={routine} borderColor={routineColor(routine.id)} />
        ))}
        {routines.length === 0 && (
          <p className="empty-state">No routines yet. Add one above.</p>
        )}
      </div>
    </div>
  );
}
