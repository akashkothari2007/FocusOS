import { useState, useEffect } from 'react';
import { api } from '../api';

const DAY_LABELS = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

function getDayLabel(dateStr) {
  return DAY_LABELS[new Date(dateStr + 'T12:00:00').getDay()];
}

function getTodayStr() {
  return new Date().toISOString().slice(0, 10);
}

export default function HabitTracker() {
  const [data, setData] = useState(null); // { habits, dates }
  const [newHabit, setNewHabit] = useState('');
  const [adding, setAdding] = useState(false);

  async function load() {
    const d = await api.getHabitLogs(7);
    setData(d);
  }

  useEffect(() => { load(); }, []);

  async function handleToggle(habitId, dateStr) {
    await api.toggleHabitLog(habitId, dateStr);
    load();
  }

  async function handleAdd(e) {
    e.preventDefault();
    if (!newHabit.trim()) return;
    setAdding(true);
    try {
      await api.createHabit(newHabit.trim());
      setNewHabit('');
      load();
    } finally {
      setAdding(false);
    }
  }

  async function handleDeactivate(habitId) {
    await api.updateHabit(habitId, { is_active: false });
    load();
  }

  const today = getTodayStr();

  return (
    <div className="habit-tracker">
      <div className="habit-tracker-header">
        <h3 className="habit-tracker-title">Habits</h3>
        <span className="habit-subtitle">Last 7 days</span>
      </div>

      {data && data.dates && (
        <div className="habit-day-labels">
          <div className="habit-name-col" />
          {data.dates.map((d) => (
            <div
              key={d}
              className={`habit-day-label${d === today ? ' habit-day-today' : ''}`}
            >
              {getDayLabel(d)}
            </div>
          ))}
          <div className="habit-action-col" />
        </div>
      )}

      {data && data.habits.length === 0 && (
        <p className="habit-empty">Add your first habit below.</p>
      )}

      {data && data.habits.map((habit) => (
        <div key={habit.id} className="habit-row">
          <span className="habit-name" title={habit.name}>{habit.name}</span>
          <div className="habit-grid">
            {habit.grid.map((cell) => (
              <button
                key={cell.date}
                className={`habit-cell${cell.completed ? ' habit-cell-done' : ''}${cell.date === today ? ' habit-cell-today' : ''}`}
                onClick={() => handleToggle(habit.id, cell.date)}
                title={cell.date}
              />
            ))}
          </div>
          <button
            className="habit-remove"
            onClick={() => handleDeactivate(habit.id)}
            title="Remove habit"
          >
            ×
          </button>
        </div>
      ))}

      <form className="habit-add-form" onSubmit={handleAdd}>
        <input
          className="input input-sm habit-add-input"
          placeholder="New habit…"
          value={newHabit}
          onChange={(e) => setNewHabit(e.target.value)}
        />
        <button className="btn btn-primary btn-sm" type="submit" disabled={adding}>
          {adding ? '…' : '+'}
        </button>
      </form>
    </div>
  );
}
