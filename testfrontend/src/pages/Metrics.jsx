import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';

// ─── Insights Strip ───────────────────────────────────────────────────────────

function fmtDur(seconds) {
  if (!seconds) return '0m';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0 && m > 0) return `${h}h ${m}m`;
  if (h > 0) return `${h}h`;
  return `${m}m`;
}

function getHabitWeakDay(habitLogs) {
  if (!habitLogs?.habits?.length) return null;
  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  let worstHabit = null, worstDay = null, worstRate = 0;
  for (const habit of habitLogs.habits) {
    if (habit.frequency < 7) continue;
    const miss = new Array(7).fill(0), total = new Array(7).fill(0);
    for (const e of habit.grid) {
      const d = new Date(e.date + 'T12:00:00').getDay();
      total[d]++;
      if (!e.completed) miss[d]++;
    }
    for (let d = 0; d < 7; d++) {
      if (total[d] < 3) continue;
      const r = miss[d] / total[d];
      if (r > worstRate && r >= 0.5) { worstRate = r; worstHabit = habit.name; worstDay = dayNames[d]; }
    }
  }
  return worstHabit ? { habit: worstHabit, day: worstDay } : null;
}

function InsightsStrip() {
  const { data: stats } = useQuery({
    queryKey: ['sessionStats'],
    queryFn: () => api.getSessionStats(),
  });
  const { data: habitLogs } = useQuery({
    queryKey: ['habitLogs', 30],
    queryFn: () => api.getHabitLogs(30, new Date().toLocaleDateString('en-CA')),
  });

  if (!stats || stats.total_sessions_28d === 0) {
    return (
      <div className="insights-strip metrics-card">
        <h2 className="metrics-section-title">Insights</h2>
        <p className="metrics-hint">Log some sessions to see your patterns here.</p>
      </div>
    );
  }

  // Week pace projection (Mon=1 ... Sun=7)
  const elapsed = stats.days_elapsed_in_week || 1;
  const projectedWeek = elapsed < 7
    ? Math.round(stats.this_week_seconds / elapsed * 7)
    : stats.this_week_seconds;
  const weekDelta = stats.this_week_seconds - stats.last_week_same_seconds;

  // DOW chart (Mon–Sun order: dow 1,2,3,4,5,6,0)
  const monFirst = [1, 2, 3, 4, 5, 6, 0].map((i) => stats.by_day_of_week[i]);
  const maxSec = Math.max(...monFirst.map((d) => d.total_seconds), 1);
  const bestDow = stats.by_day_of_week.reduce(
    (b, d) => (d.total_seconds > b.total_seconds ? d : b),
    stats.by_day_of_week[0]
  );
  const bestDowAvgMin = Math.round(bestDow.total_seconds / 4 / 60); // avg over 4 weeks

  // Time-of-day persona
  const tod = stats.time_of_day;
  const todSlots = [
    { key: 'morning',   label: 'Morning',   range: '5am–12pm', count: tod.morning },
    { key: 'afternoon', label: 'Afternoon', range: '12–5pm',   count: tod.afternoon },
    { key: 'evening',   label: 'Evening',   range: '5–10pm',   count: tod.evening },
    { key: 'night',     label: 'Night',     range: '10pm–5am', count: tod.night },
  ];
  const dominantSlot = todSlots.reduce((a, b) => b.count > a.count ? b : a, todSlots[0]);
  const dominantPct = tod.total > 0 ? Math.round((dominantSlot.count / tod.total) * 100) : 0;
  const todMaxCount = Math.max(...todSlots.map((s) => s.count), 1);
  const personaLabel = { morning: 'morning grinder', afternoon: 'afternoon flow', evening: 'evening worker', night: 'night owl' }[dominantSlot.key];

  // Habit weak day
  const habitWeak = getHabitWeakDay(habitLogs);

  const dayLabel = (n) => ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][n] || '';

  return (
    <div className="insights-strip metrics-card">
      <h2 className="metrics-section-title" style={{ marginBottom: 14 }}>Insights</h2>
      <div className="insights-tiles">

        {/* Week pace */}
        <div className="insight-tile">
          <span className="insight-tile-label">This week</span>
          <span className="insight-tile-value">{fmtDur(stats.this_week_seconds)}</span>
          {elapsed < 7 && (
            <span className="insight-tile-sub neutral">on pace for {fmtDur(projectedWeek)}</span>
          )}
          {stats.last_week_same_seconds > 0 ? (
            <span className={`insight-tile-sub ${weekDelta >= 0 ? 'up' : 'down'}`}>
              {weekDelta >= 0 ? '↑' : '↓'} {fmtDur(Math.abs(weekDelta))} vs last {dayLabel(new Date().getDay())}
            </span>
          ) : (
            <span className="insight-tile-sub neutral">no data last week yet</span>
          )}
        </div>

        {/* DOW bar chart */}
        <div className="insight-tile insight-tile-chart">
          <span className="insight-tile-label">Best day (4-wk avg)</span>
          <span className="insight-tile-value">{bestDow.day}s</span>
          <span className="insight-tile-sub neutral">{bestDowAvgMin}m avg · {bestDow.session_count} sessions</span>
          <div className="insight-dow-bars">
            {monFirst.map((d, i) => {
              const pct = Math.round((d.total_seconds / maxSec) * 100);
              return (
                <div key={i} className="insight-dow-bar-col">
                  <div className="insight-dow-bar-track">
                    <div
                      className={`insight-dow-bar-fill${d.dow === bestDow.dow ? ' best' : ''}`}
                      style={{ height: `${Math.max(pct, 4)}%` }}
                    />
                  </div>
                  <span className="insight-dow-label">{d.day[0]}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Streak */}
        <div className="insight-tile">
          <span className="insight-tile-label">Streak</span>
          <span className="insight-tile-value">
            {stats.current_streak_days}
            <span className="insight-tile-unit"> day{stats.current_streak_days !== 1 ? 's' : ''}</span>
          </span>
          {stats.best_streak_days > stats.current_streak_days ? (
            <span className="insight-tile-sub neutral">best: {stats.best_streak_days} days</span>
          ) : stats.current_streak_days >= 3 ? (
            <span className="insight-tile-sub up">personal best!</span>
          ) : (
            <span className="insight-tile-sub neutral">{stats.current_streak_days === 0 ? 'start one today' : 'keep going'}</span>
          )}
        </div>

        {/* Time-of-day persona */}
        {tod.total > 0 && (
          <div className="insight-tile insight-tile-tod">
            <span className="insight-tile-label">You're a</span>
            <span className="insight-tile-value insight-tile-value-sm">{personaLabel}</span>
            <span className="insight-tile-sub neutral">{dominantPct}% in the {dominantSlot.label.toLowerCase()}</span>
            <div className="insight-tod-bars">
              {todSlots.map((s) => (
                <div key={s.key} className="insight-tod-bar-col">
                  <div className="insight-tod-bar-track">
                    <div
                      className={`insight-tod-bar-fill${s.key === dominantSlot.key ? ' best' : ''}`}
                      style={{ height: `${Math.max(Math.round(s.count / todMaxCount * 100), s.count > 0 ? 8 : 0)}%` }}
                    />
                  </div>
                  <span className="insight-dow-label">{s.label[0]}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Session depth */}
        {stats.avg_session_seconds > 0 && (
          <div className="insight-tile">
            <span className="insight-tile-label">Avg session</span>
            <span className="insight-tile-value">{fmtDur(stats.avg_session_seconds)}</span>
            {stats.deep_work_days_this_week > 0 ? (
              <span className="insight-tile-sub up">{stats.deep_work_days_this_week} deep day{stats.deep_work_days_this_week > 1 ? 's' : ''} this week (4h+)</span>
            ) : (
              <span className="insight-tile-sub neutral">no 4h+ days yet this week</span>
            )}
          </div>
        )}

        {/* Most worked project */}
        {stats.most_worked_todo && (
          <div className="insight-tile insight-tile-project">
            <span className="insight-tile-label">Most focus on</span>
            <span className="insight-tile-value insight-tile-value-sm insight-project-name">{stats.most_worked_todo.title}</span>
            <span className="insight-tile-sub neutral">{fmtDur(stats.most_worked_todo.total_seconds)} total</span>
          </div>
        )}

        {/* Habit weak day */}
        {habitWeak && (
          <div className="insight-tile insight-tile-warn">
            <span className="insight-tile-label">Watch out</span>
            <span className="insight-tile-value insight-tile-value-sm">{habitWeak.day}s</span>
            <span className="insight-tile-sub neutral">you skip {habitWeak.habit} most</span>
          </div>
        )}

      </div>
    </div>
  );
}

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

function TodoSessionRow({ todo, onDelete, onRestore }) {
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
          {todo.status === 'done' && (
            <button
              className="metrics-todo-restore"
              onClick={(e) => { e.stopPropagation(); onRestore(todo.id); }}
              title="Restore to pending"
            >↩</button>
          )}
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

// ─── 8-Week Rolling Chart ────────────────────────────────────────────────────

function WeeklyChart() {
  const { data } = useQuery({
    queryKey: ['weeklySummary'],
    queryFn: () => api.getWeeklySummary(),
  });

  if (!data?.weeks) return null;
  const weeks = data.weeks;
  if (!weeks.some((w) => w.total_seconds > 0)) return null;

  const maxSec = Math.max(...weeks.map((w) => w.total_seconds), 1);

  return (
    <div className="metrics-card">
      <h2 className="metrics-section-title">Focus over 8 weeks</h2>
      <div className="weekly-chart">
        {weeks.map((w, i) => {
          const pct = (w.total_seconds / maxSec) * 100;
          const h = w.total_seconds > 0 ? (w.total_seconds / 3600).toFixed(1) : '';
          const label = new Date(w.week_start + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
          return (
            <div key={i} className={`weekly-col${w.is_current ? ' current' : ''}`}>
              <span className="weekly-val">{h ? `${h}h` : ''}</span>
              <div className="weekly-bar-wrap">
                <div className="weekly-bar" style={{ height: `${Math.max(pct, w.total_seconds > 0 ? 3 : 0)}%` }} />
              </div>
              <span className="weekly-lbl">{label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Todo Completion Stats ────────────────────────────────────────────────────

function TodoStats() {
  const { data: todos } = useQuery({
    queryKey: ['todos', 'all'],
    queryFn: () => api.getTodos().then((d) => [
      ...d.todos.filter((t) => t.status === 'pending'),
      ...d.todos.filter((t) => t.status === 'done'),
    ]),
  });

  if (!todos?.length) return null;

  const done = todos.filter((t) => t.status === 'done').length;
  const total = todos.length;
  const pct = Math.round((done / total) * 100);
  const overdue = todos.filter(
    (t) => t.status === 'pending' && t.due_date && new Date(t.due_date) < new Date()
  ).length;
  const allSubs = todos.flatMap((t) => Array.isArray(t.subtasks) ? t.subtasks : []);
  const doneSubs = allSubs.filter((s) => s.status === 'done').length;
  const subPct = allSubs.length > 0 ? Math.round((doneSubs / allSubs.length) * 100) : null;

  // SVG ring: r=15.9, circumference ≈ 100
  const ringPct = pct;

  return (
    <div className="metrics-card">
      <h3 className="metrics-section-title">Todos</h3>
      <div className="todo-stats-row">
        <div className="todo-ring-wrap">
          <svg viewBox="0 0 36 36" className="todo-ring-svg">
            <circle cx="18" cy="18" r="15.9" fill="none" stroke="rgba(99,102,241,0.12)" strokeWidth="3" />
            <circle
              cx="18" cy="18" r="15.9" fill="none"
              stroke="#6366f1" strokeWidth="3"
              strokeDasharray={`${ringPct} ${100 - ringPct}`}
              strokeDashoffset="25"
              strokeLinecap="round"
            />
          </svg>
          <span className="todo-ring-pct">{pct}%</span>
        </div>
        <div className="todo-stat-details">
          <div className="todo-stat-line"><span className="todo-stat-dot done-dot" />{done} completed</div>
          <div className="todo-stat-line"><span className="todo-stat-dot pending-dot" />{total - done} pending</div>
          {overdue > 0 && <div className="todo-stat-line overdue-line">⚠ {overdue} overdue</div>}
          {subPct !== null && <div className="todo-stat-line muted-line">{subPct}% of subtasks done</div>}
        </div>
      </div>
    </div>
  );
}

// ─── Job Pipeline ─────────────────────────────────────────────────────────────

function JobPipeline() {
  const { data } = useQuery({
    queryKey: ['jobs', 'all'],
    queryFn: () => api.getJobs(),
  });

  if (!data?.jobs?.length) return null;
  const jobs = data.jobs;

  const counts = {
    saved:     jobs.filter((j) => j.status === 'saved').length,
    applied:   jobs.filter((j) => j.status === 'applied').length,
    interview: jobs.filter((j) => j.status === 'interview').length,
    rejected:  jobs.filter((j) => j.status === 'rejected').length,
  };

  const stages = [
    { key: 'saved',     label: 'Saved',     color: '#94a3b8' },
    { key: 'applied',   label: 'Applied',   color: '#6366f1' },
    { key: 'interview', label: 'Interview', color: '#14b8a6' },
    { key: 'rejected',  label: 'Rejected',  color: '#e11d48' },
  ];

  const interviewRate = counts.applied > 0
    ? Math.round((counts.interview / counts.applied) * 100)
    : null;

  return (
    <div className="metrics-card">
      <h3 className="metrics-section-title">Job Pipeline</h3>
      <div className="job-pipeline-stages">
        {stages.map((s) => (
          <div key={s.key} className="job-stage-tile" style={{ '--c': s.color }}>
            <span className="job-stage-n">{counts[s.key]}</span>
            <span className="job-stage-lbl">{s.label}</span>
          </div>
        ))}
      </div>
      {interviewRate !== null && (
        <p className="metrics-hint" style={{ marginTop: 10 }}>
          {interviewRate > 0
            ? `${interviewRate}% interview rate · ${counts.applied} application${counts.applied !== 1 ? 's' : ''} sent`
            : `${counts.applied} application${counts.applied !== 1 ? 's' : ''} out · no interviews yet`}
        </p>
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
      <div className="metrics-insights-row">
        <InsightsStrip />
      </div>

      <div className="metrics-insights-row">
        <WeeklyChart />
      </div>

      <div className="metrics-col">
        <TodoStats />
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
              onRestore={(id) => {
                queryClient.setQueryData(['todos', 'all'], (old = []) => old.map((t) => t.id === id ? { ...t, status: 'pending' } : t));
                queryClient.invalidateQueries({ queryKey: ['todos', 'pending'] });
                api.updateTodo(id, { status: 'pending' });
              }}
            />
          ))}
        </div>
      </div>

      <div className="metrics-col">
        <JobPipeline />
        <div className="metrics-card">
          <HabitMetrics />
        </div>
      </div>
    </div>
  );
}
