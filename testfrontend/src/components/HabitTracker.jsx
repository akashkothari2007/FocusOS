import { useState, useEffect } from 'react';
import { api } from '../api';

const DAY_LABELS = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
const WEEK_DAY_LABELS = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

function getTodayStr() {
  return new Date().toISOString().slice(0, 10);
}

function getDayLabel(dateStr) {
  return DAY_LABELS[new Date(dateStr + 'T12:00:00').getDay()];
}

// Returns Mon–Sun of the current week as date strings
function getCurrentWeekDates() {
  const today = new Date();
  const dow = today.getDay();
  const monday = new Date(today);
  monday.setDate(today.getDate() - (dow === 0 ? 6 : dow - 1));
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    return d.toISOString().slice(0, 10);
  });
}

export default function HabitTracker() {
  const [data, setData] = useState(null);
  const [newHabit, setNewHabit] = useState('');
  const [frequency, setFrequency] = useState(7);
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
      await api.createHabit(newHabit.trim(), frequency);
      setNewHabit('');
      setFrequency(7);
      load();
    } finally {
      setAdding(false);
    }
  }

  const today = getTodayStr();
  const weekDates = getCurrentWeekDates();

  const dailyHabits = data?.habits.filter((h) => h.frequency === 7) ?? [];
  const weeklyHabits = data?.habits.filter((h) => h.frequency < 7) ?? [];

  return (
    <div className="habit-tracker">
      <h3 className="habit-tracker-title">Habits</h3>

      {/* ── Daily Section ── */}
      {dailyHabits.length > 0 && (
        <div className="habit-section">
          <div className="habit-section-label habit-section-label-daily">Daily</div>

          <div className="habit-day-labels">
            <div className="habit-name-col" />
            {data.dates.map((d) => (
              <div key={d} className={`habit-day-label${d === today ? ' habit-day-today-daily' : ''}`}>
                {getDayLabel(d)}
              </div>
            ))}
          </div>

          {dailyHabits.map((habit) => {
            const gridMap = Object.fromEntries(habit.grid.map((c) => [c.date, c.completed]));
            return (
              <div key={habit.id} className="habit-row">
                <div className="habit-name-wrap">
                  <span className="habit-name">{habit.name}</span>
                  {habit.streak > 0 && <span className="habit-streak">🔥{habit.streak}</span>}
                </div>
                <div className="habit-grid">
                  {data.dates.map((d) => (
                    <button
                      key={d}
                      className={`habit-cell habit-cell-daily${gridMap[d] ? ' habit-cell-done-daily' : ''}`}
                      onClick={() => handleToggle(habit.id, d)}
                      title={d}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Weekly Goals Section ── */}
      {weeklyHabits.length > 0 && (
        <div className="habit-section">
          <div className="habit-section-label habit-section-label-weekly">Weekly Goals</div>

          <div className="habit-day-labels">
            <div className="habit-name-col" />
            {weekDates.map((d, i) => (
              <div key={d} className={`habit-day-label${d === today ? ' habit-day-today-weekly' : ''}`}>
                {WEEK_DAY_LABELS[i]}
              </div>
            ))}
            <div className="habit-badge-col" />
          </div>

          {weeklyHabits.map((habit) => {
            const gridMap = Object.fromEntries(habit.grid.map((c) => [c.date, c.completed]));
            const goal_met = habit.week_count >= habit.frequency;
            return (
              <div key={habit.id} className="habit-row">
                <div className="habit-name-wrap">
                  <span className="habit-name">{habit.name}</span>
                </div>
                <div className="habit-grid">
                  {weekDates.map((d) => {
                    const future = d > today;
                    return (
                      <button
                        key={d}
                        className={`habit-cell habit-cell-weekly${gridMap[d] ? ' habit-cell-done-weekly' : ''}${future ? ' habit-cell-future' : ''}`}
                        onClick={() => !future && handleToggle(habit.id, d)}
                        disabled={future}
                        title={d}
                      />
                    );
                  })}
                </div>
                <span className={`habit-progress-badge${goal_met ? ' habit-progress-done' : ''}`}>
                  {habit.week_count}/{habit.frequency}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {data && dailyHabits.length === 0 && weeklyHabits.length === 0 && (
        <p className="habit-empty">Add your first habit below.</p>
      )}

      <form className="habit-add-form" onSubmit={handleAdd}>
        <input
          className="input input-sm habit-add-input"
          placeholder="New habit…"
          value={newHabit}
          onChange={(e) => setNewHabit(e.target.value)}
        />
        <select
          className="input input-sm habit-freq-select"
          value={frequency}
          onChange={(e) => setFrequency(Number(e.target.value))}
        >
          <option value={7}>Daily</option>
          {[1, 2, 3, 4, 5, 6].map((n) => (
            <option key={n} value={n}>{n}×/wk</option>
          ))}
        </select>
        <button className="btn btn-primary btn-sm" type="submit" disabled={adding}>
          {adding ? '…' : '+'}
        </button>
      </form>
    </div>
  );
}
