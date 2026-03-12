import { useState, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';

const SESSION_COLORS = ['#6366f1', '#ec4899', '#f59e0b', '#14b8a6'];
const FREEFORM_COLOR = '#8b5cf6';

function sessionColor(s) {
  if (!s.todo_id) return FREEFORM_COLOR;
  return SESSION_COLORS[s.todo_id % SESSION_COLORS.length];
}

function fmtDuration(seconds) {
  if (!seconds) return '0m';
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}m`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

function fmtElapsed(startedAt) {
  const secs = Math.max(0, Math.floor((Date.now() - new Date(startedAt)) / 1000));
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function toLocalDateStr(date) {
  return date.toLocaleDateString('en-CA');
}

function formatDayLabel(dateStr) {
  const today = toLocalDateStr(new Date());
  if (dateStr === today) return 'Today';
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  if (dateStr === toLocalDateStr(yesterday)) return 'Yesterday';
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

export default function TodayStrip({ activeSession, setActiveSession }) {
  const queryClient = useQueryClient();
  const todayStr = toLocalDateStr(new Date());
  const [viewDate, setViewDate] = useState(todayStr);
  const [popover, setPopover] = useState(null); // { session, x, y }
  const [showFreeformInput, setShowFreeformInput] = useState(false);
  const [freeformTitle, setFreeformTitle] = useState('');
  const [starting, setStarting] = useState(false);
  const [elapsed, setElapsed] = useState('00:00');

  const isToday = viewDate === todayStr;

  const { data } = useQuery({
    queryKey: ['sessions', 'day', viewDate],
    queryFn: () => api.getTodaySessions(viewDate).then((d) => d.sessions),
    refetchInterval: isToday ? 30000 : false,
  });
  const sessions = data ?? [];

  // Live timer for active session
  useEffect(() => {
    if (!activeSession) return;
    const tick = () => setElapsed(fmtElapsed(activeSession.startedAt));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [activeSession?.startedAt]);

  // Refresh today's list when active session changes
  useEffect(() => {
    queryClient.invalidateQueries({ queryKey: ['sessions', 'day', todayStr] });
  }, [activeSession?.sessionId, queryClient, todayStr]);

  // Close popover on outside click
  useEffect(() => {
    if (!popover) return;
    function handle() { setPopover(null); }
    document.addEventListener('click', handle);
    return () => document.removeEventListener('click', handle);
  }, [popover]);

  function prevDay() {
    const d = new Date(viewDate + 'T00:00:00');
    d.setDate(d.getDate() - 1);
    setViewDate(toLocalDateStr(d));
  }

  function nextDay() {
    const d = new Date(viewDate + 'T00:00:00');
    d.setDate(d.getDate() + 1);
    const next = toLocalDateStr(d);
    if (next <= todayStr) setViewDate(next);
  }

  async function handleStartFreeform() {
    const title = freeformTitle.trim();
    if (!title) return;

    if (activeSession) {
      const ok = window.confirm(
        `End session for "${activeSession.todoTitle}" and start "${title}"?`
      );
      if (!ok) return;
      await api.endSession(activeSession.sessionId, null);
    }

    setStarting(true);
    setActiveSession({
      sessionId: null,
      todoId: null,
      todoTitle: title,
      startedAt: new Date().toISOString(),
    });

    try {
      const session = await api.startFreeformSession(title);
      setActiveSession({
        sessionId: session.id,
        todoId: null,
        todoTitle: title,
        startedAt: session.started_at,
      });
    } catch {
      setActiveSession(null);
    } finally {
      setStarting(false);
      setFreeformTitle('');
      setShowFreeformInput(false);
    }
  }

  async function handleEndSession(e) {
    e?.stopPropagation();
    if (!activeSession?.sessionId) return;
    await api.endSession(activeSession.sessionId, null);
    setActiveSession(null);
    queryClient.invalidateQueries({ queryKey: ['sessions', 'day', todayStr] });
  }

  function openPopover(e, s) {
    e.stopPropagation();
    const rect = e.currentTarget.getBoundingClientRect();
    setPopover({
      session: s,
      x: rect.right + 8,
      y: Math.min(rect.top, window.innerHeight - 160),
    });
  }

  const activeInList = activeSession && sessions.some((s) => s.id === activeSession.sessionId);

  return (
    <div className="today-strip">
      {/* Day navigation */}
      <div className="today-strip-header">
        <button className="today-nav-btn" onClick={prevDay}>‹</button>
        <span className="today-label">{formatDayLabel(viewDate)}</span>
        <button
          className="today-nav-btn"
          onClick={nextDay}
          disabled={viewDate >= todayStr}
        >›</button>
        {isToday && (
          <button
            className="today-add-btn"
            onClick={() => { setShowFreeformInput((v) => !v); setFreeformTitle(''); }}
            title="Start freeform session"
          >
            {showFreeformInput ? '×' : '+'}
          </button>
        )}
      </div>

      {/* Freeform input */}
      {showFreeformInput && (
        <div className="freeform-input-row">
          <input
            className="input input-sm"
            placeholder="Session title…"
            value={freeformTitle}
            onChange={(e) => setFreeformTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleStartFreeform();
              if (e.key === 'Escape') { setShowFreeformInput(false); setFreeformTitle(''); }
            }}
            autoFocus
          />
          <button
            className="btn btn-primary btn-sm"
            onClick={handleStartFreeform}
            disabled={!freeformTitle.trim() || starting}
          >
            {starting ? '…' : 'Start'}
          </button>
        </div>
      )}

      {/* Session list */}
      <div className="today-sessions-list">
        {/* Optimistic active block before query catches up */}
        {isToday && activeSession && !activeInList && (
          <div
            className="session-strip-block is-active"
            style={{
              borderLeftColor: activeSession.todoId
                ? SESSION_COLORS[activeSession.todoId % SESSION_COLORS.length]
                : FREEFORM_COLOR,
            }}
          >
            <span className="ssb-title">{activeSession.todoTitle}</span>
            <span
              className="ssb-duration"
              style={{
                color: activeSession.todoId
                  ? SESSION_COLORS[activeSession.todoId % SESSION_COLORS.length]
                  : FREEFORM_COLOR,
              }}
            >
              {elapsed}
            </span>
            <button className="ssb-end-btn" onClick={handleEndSession}>End</button>
          </div>
        )}

        {sessions.map((s) => {
          const isActive = activeSession?.sessionId === s.id;
          const color = sessionColor(s);

          return (
            <div
              key={s.id}
              className={`session-strip-block${isActive ? ' is-active' : ''}`}
              style={{ borderLeftColor: color }}
              onClick={(e) => openPopover(e, s)}
            >
              <span className="ssb-title">{s.todo_title || s.title || 'Session'}</span>
              <span className="ssb-duration" style={{ color }}>
                {isActive ? elapsed : fmtDuration(s.seconds_spent)}
              </span>
              {isActive && (
                <button className="ssb-end-btn" onClick={handleEndSession}>End</button>
              )}
            </div>
          );
        })}

        {sessions.length === 0 && !(isToday && activeSession && !activeInList) && (
          <p className="today-empty">No sessions {isToday ? 'yet' : 'this day'}</p>
        )}
      </div>

      {/* Fixed-position popover — escapes overflow clipping */}
      {popover && (
        <div
          className="session-popover-fixed"
          style={{
            left: Math.min(popover.x, window.innerWidth - 244),
            top: popover.y,
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <button className="sp-close" onClick={() => setPopover(null)}>×</button>
          <p className="sp-title">{popover.session.todo_title || popover.session.title || 'Session'}</p>
          {popover.session.notes
            ? <p className="sp-notes">{popover.session.notes}</p>
            : <p className="sp-notes-empty">No notes</p>
          }
        </div>
      )}
    </div>
  );
}
