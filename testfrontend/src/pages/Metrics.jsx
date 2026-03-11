import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';

function formatDuration(seconds) {
  if (!seconds) return '0m';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m`;
  return `${seconds}s`;
}

function formatDate(dt) {
  if (!dt) return '—';
  return new Date(dt).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  });
}

function formatTime(dt) {
  if (!dt) return '';
  return new Date(dt).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
}

// ─── Todo Sessions Section ────────────────────────────────────────────────────

function TodoSessionRow({ todo, onDelete }) {
  const [expanded, setExpanded] = useState(false);
  const [sessions, setSessions] = useState(null);

  async function handleExpand() {
    if (!expanded && sessions === null) {
      const data = await api.getSessions(todo.id);
      setSessions(data.sessions);
    }
    setExpanded((v) => !v);
  }

  function handleDelete(e) {
    e.stopPropagation();
    if (!window.confirm(`Delete "${todo.title}" and all its sessions?`)) return;
    onDelete(todo.id);
    api.deleteTodo(todo.id);
  }

  const totalSeconds = sessions
    ? sessions.reduce((sum, s) => sum + (s.seconds_spent || 0), 0)
    : null;

  return (
    <div className={`metrics-todo-row${expanded ? ' expanded' : ''}`}>
      <button className="metrics-todo-header" onClick={handleExpand}>
        <div className="metrics-todo-left">
          <span className={`metrics-todo-status ${todo.status}`} />
          <span className="metrics-todo-title">{todo.title}</span>
        </div>
        <div className="metrics-todo-right">
          {totalSeconds !== null && (
            <span className="metrics-total-time">{formatDuration(totalSeconds)}</span>
          )}
          {sessions !== null && (
            <span className="metrics-session-count">{sessions.length} session{sessions.length !== 1 ? 's' : ''}</span>
          )}
          <span className="metrics-chevron">{expanded ? '▲' : '▼'}</span>
          <button className="metrics-todo-delete" onClick={handleDelete} title="Delete todo">×</button>
        </div>
      </button>

      {expanded && sessions !== null && (
        <div className="metrics-sessions-list">
          {sessions.length === 0 && (
            <p className="metrics-no-sessions">No sessions yet.</p>
          )}
          {sessions.map((s) => (
            <div key={s.id} className="metrics-session-item">
              <div className="metrics-session-item-top">
                <span className="metrics-session-date">{formatDate(s.started_at)}</span>
                <span className="metrics-session-time-range">
                  {formatTime(s.started_at)}{s.ended_at ? ` → ${formatTime(s.ended_at)}` : ' (in progress)'}
                </span>
                <span className="metrics-session-duration">{formatDuration(s.seconds_spent)}</span>
              </div>
              {s.notes && <p className="metrics-session-notes">{s.notes}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Habit Metrics Section ────────────────────────────────────────────────────

function HabitMetrics() {
  const [newHabit, setNewHabit] = useState('');
  const queryClient = useQueryClient();

  const { data: habitLogs } = useQuery({
    queryKey: ['habitLogs', 30],
    queryFn: () => api.getHabitLogs(30, new Date().toLocaleDateString('en-CA')),
  });

  const { data: habitsData } = useQuery({
    queryKey: ['habits'],
    queryFn: () => api.getHabits(),
  });
  const allHabits = habitsData?.habits ?? null;

  function invalidateHabits() {
    queryClient.invalidateQueries({ queryKey: ['habitLogs'] });
    queryClient.invalidateQueries({ queryKey: ['habits'] });
  }

  const addMutation = useMutation({
    mutationFn: (name) => api.createHabit(name),
    onSuccess: () => { setNewHabit(''); invalidateHabits(); },
  });

  const deleteMutation = useMutation({
    mutationFn: (id) => api.deleteHabit(id),
    onMutate: (id) => {
      queryClient.setQueryData(['habits'], (old) =>
        old ? { ...old, habits: old.habits.filter((h) => h.id !== id) } : old
      );
      queryClient.setQueryData(['habitLogs', 30], (old) =>
        old ? { ...old, habits: old.habits.filter((h) => h.id !== id) } : old
      );
    },
    onSettled: invalidateHabits,
  });

  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, isActive }) => api.updateHabit(id, { is_active: !isActive }),
    onMutate: ({ id, isActive }) => {
      queryClient.setQueryData(['habits'], (old) =>
        old ? { ...old, habits: old.habits.map((h) => h.id === id ? { ...h, is_active: !isActive } : h) } : old
      );
    },
    onSettled: invalidateHabits,
  });

  async function handleAdd(e) {
    e.preventDefault();
    if (!newHabit.trim()) return;
    addMutation.mutate(newHabit.trim());
  }

  async function handleDelete(id) {
    if (!window.confirm('Permanently delete this habit and all its logs?')) return;
    deleteMutation.mutate(id);
  }

  async function handleToggleActive(id, isActive) {
    toggleActiveMutation.mutate({ id, isActive });
  }

  return (
    <div className="metrics-habits">
      <h3 className="metrics-section-title">Habits</h3>

      {habitLogs && habitLogs.habits.length > 0 && (
        <div className="metrics-habit-list">
          {habitLogs.habits.map((habit) => {
            const total = habit.grid.length;
            const done = habit.grid.filter((c) => c.completed).length;
            const pct = total > 0 ? Math.round((done / total) * 100) : 0;
            return (
              <div key={habit.id} className="metrics-habit-row">
                <div className="metrics-habit-info">
                  <div className="metrics-habit-name-wrap">
                    <span className={`metrics-habit-name${habit.frequency < 7 ? ' metrics-habit-name-weekly' : ''}`}>{habit.name}</span>
                    {habit.frequency === 7 ? (
                      habit.streak > 0 && <span className="habit-streak">🔥{habit.streak}</span>
                    ) : (
                      <span className={`habit-progress-badge${habit.week_count >= habit.frequency ? ' habit-progress-done' : ''}`} style={{textAlign:'left', marginLeft:0}}>
                        {habit.week_count}/{habit.frequency}/wk
                      </span>
                    )}
                  </div>
                  <div className="metrics-habit-bar-wrap">
                    <div className="metrics-habit-bar" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="metrics-habit-pct">{pct}%</span>
                  <span className="metrics-habit-count">{done}/{total} days</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {allHabits && (
        <div className="metrics-habit-manage">
          <p className="metrics-manage-label">Manage habits</p>
          {allHabits.map((h) => (
            <div key={h.id} className="metrics-manage-row">
              <span className={`metrics-manage-name${h.is_active ? '' : ' inactive'}`}>{h.name}</span>
              <div className="metrics-manage-actions">
                <button
                  className={`btn-tag ${h.is_active ? 'btn-tag-warn' : 'btn-tag-ok'}`}
                  onClick={() => handleToggleActive(h.id, h.is_active)}
                >
                  {h.is_active ? 'Deactivate' : 'Reactivate'}
                </button>
                <button
                  className="btn-tag btn-tag-danger"
                  onClick={() => handleDelete(h.id)}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <form className="habit-add-form metrics-add-form" onSubmit={handleAdd}>
        <input
          className="input input-sm habit-add-input"
          placeholder="Add new habit…"
          value={newHabit}
          onChange={(e) => setNewHabit(e.target.value)}
        />
        <button className="btn btn-primary btn-sm" type="submit" disabled={addMutation.isPending}>
          {addMutation.isPending ? '…' : 'Add'}
        </button>
      </form>
    </div>
  );
}

// ─── Main Metrics Page ────────────────────────────────────────────────────────

export default function Metrics() {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['todos', 'all'],
    queryFn: () => api.getTodos().then((d) => [
      ...d.todos.filter((t) => t.status === 'pending'),
      ...d.todos.filter((t) => t.status === 'done'),
    ]),
  });
  const todos = data ?? [];

  return (
    <div className="metrics-page">
      <div className="metrics-col">
        <div className="metrics-card">
          <h2 className="metrics-section-title">Sessions by Todo</h2>
          <p className="metrics-hint">Click a todo to see its sessions and total time.</p>
          {isLoading && <p className="empty-state">Loading…</p>}
          {!isLoading && todos.length === 0 && (
            <p className="empty-state">No todos yet.</p>
          )}
          {!isLoading && todos.map((todo) => (
            <TodoSessionRow
              key={todo.id}
              todo={todo}
              onDelete={(id) => queryClient.setQueryData(['todos', 'all'], (old = []) => old.filter((t) => t.id !== id))}
            />
          ))}
        </div>
      </div>

      <div className="metrics-col">
        <div className="metrics-card">
          <HabitMetrics />
        </div>
      </div>
    </div>
  );
}
