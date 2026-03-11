import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';

const DAY_LABELS = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
const WEEK_DAY_LABELS = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

function toLocalDateStr(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function getTodayStr() {
  return toLocalDateStr(new Date());
}

function getDayLabel(dateStr) {
  return DAY_LABELS[new Date(dateStr + 'T12:00:00').getDay()];
}


function getCurrentWeekDates() {
  const today = new Date();
  const dow = today.getDay();
  const monday = new Date(today);
  monday.setDate(today.getDate() - (dow === 0 ? 6 : dow - 1));
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    return toLocalDateStr(d);
  });
}

export default function HabitTracker() {
  const [newHabit, setNewHabit] = useState('');
  const [frequency, setFrequency] = useState(7);
  const queryClient = useQueryClient();
  const QUERY_KEY = ['habitLogs', 7];

  const { data } = useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => api.getHabitLogs(7, getTodayStr()),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ habitId, dateStr }) => api.toggleHabitLog(habitId, dateStr),
    onMutate: async ({ habitId, dateStr }) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEY });
      const prev = queryClient.getQueryData(QUERY_KEY);
      const today = getTodayStr();
      const weekDates = getCurrentWeekDates();
      queryClient.setQueryData(QUERY_KEY, (old) => ({
        ...old,
        habits: old.habits.map((h) => {
          if (h.id !== habitId) return h;
          const wasCompleted = h.grid.find((c) => c.date === dateStr)?.completed ?? false;
          const inWeek = weekDates.includes(dateStr);
          const newGrid = h.grid.map((c) =>
            c.date === dateStr ? { ...c, completed: !c.completed } : c
          );
          const isToday = dateStr === today;
          const streakDelta = isToday ? (wasCompleted ? -1 : 1) : 0;
          return {
            ...h,
            grid: newGrid,
            streak: Math.max(0, h.streak + streakDelta),
            week_count: inWeek
              ? Math.max(0, h.week_count + (wasCompleted ? -1 : 1))
              : h.week_count,
          };
        }),
      }));
      return { prev };
    },
    onError: (_, __, ctx) => queryClient.setQueryData(QUERY_KEY, ctx.prev),
    onSettled: () => queryClient.invalidateQueries({ queryKey: QUERY_KEY }),
  });

  const addMutation = useMutation({
    mutationFn: ({ name, freq }) => api.createHabit(name, freq),
    onSuccess: () => {
      setNewHabit('');
      setFrequency(7);
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });

  const today = getTodayStr();
  const weekDates = getCurrentWeekDates();
  const dailyHabits = data?.habits.filter((h) => h.frequency === 7) ?? [];
  const weeklyHabits = data?.habits.filter((h) => h.frequency < 7) ?? [];

  function handleAdd(e) {
    e.preventDefault();
    if (!newHabit.trim()) return;
    addMutation.mutate({ name: newHabit.trim(), freq: frequency });
  }

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
                      onClick={() => toggleMutation.mutate({ habitId: habit.id, dateStr: d })}
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
                        onClick={() => !future && toggleMutation.mutate({ habitId: habit.id, dateStr: d })}
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
        <button className="btn btn-primary btn-sm" type="submit" disabled={addMutation.isPending}>
          {addMutation.isPending ? '…' : '+'}
        </button>
      </form>
    </div>
  );
}
