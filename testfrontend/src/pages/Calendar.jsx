import { useState, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';

const SESSION_COLORS = ['#6366f1', '#ec4899', '#f59e0b', '#14b8a6'];
const FREEFORM_COLOR = '#8b5cf6';
const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const HOUR_PX = 60;           // 60px per hour = 1px per minute
const TOTAL_HEIGHT = 24 * HOUR_PX; // 1440px
const HOURS = Array.from({ length: 24 }, (_, i) => i);

function sessionColor(s) {
  if (!s.todo_id) return FREEFORM_COLOR;
  return SESSION_COLORS[s.todo_id % SESSION_COLORS.length];
}

function toLocalDateStr(date) {
  return date.toLocaleDateString('en-CA');
}

function getMonday(date) {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  const day = d.getDay();
  d.setDate(d.getDate() - (day === 0 ? 6 : day - 1));
  return d;
}

function formatHour(h) {
  if (h === 0) return '12am';
  if (h < 12) return `${h}am`;
  if (h === 12) return '12pm';
  return `${h - 12}pm`;
}

// Returns top (px from midnight) and height (px) for a session block
function getBlockStyle(session, nowMs) {
  const start = new Date(session.started_at);
  const startMin = start.getHours() * 60 + start.getMinutes();

  let endMin;
  if (session.ended_at) {
    const end = new Date(session.ended_at);
    endMin = end.getHours() * 60 + end.getMinutes();
  } else {
    const now = new Date(nowMs);
    endMin = now.getHours() * 60 + now.getMinutes();
  }

  const height = Math.max(20, endMin - startMin);
  return { top: startMin, height };
}

export default function Calendar({ activeSession, setActiveSession }) {
  const queryClient = useQueryClient();
  const todayStr = toLocalDateStr(new Date());
  const [weekStart, setWeekStart] = useState(() => toLocalDateStr(getMonday(new Date())));
  const [popover, setPopover] = useState(null); // { session, x, y }
  const [showFreeformInput, setShowFreeformInput] = useState(false);
  const [freeformTitle, setFreeformTitle] = useState('');
  const [starting, setStarting] = useState(false);
  const [nowMs, setNowMs] = useState(Date.now());
  const scrollRef = useRef(null);

  // Update nowMs every 30s so active session block grows in real time
  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 30000);
    return () => clearInterval(id);
  }, []);

  // Scroll to 8am on mount
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = 8 * HOUR_PX - 40;
  }, []);

  // Close popover on outside click
  useEffect(() => {
    if (!popover) return;
    function handle() { setPopover(null); }
    document.addEventListener('click', handle);
    return () => document.removeEventListener('click', handle);
  }, [popover]);

  // Refresh when active session changes
  useEffect(() => {
    queryClient.invalidateQueries({ queryKey: ['sessions', 'week'] });
  }, [activeSession?.sessionId, queryClient]);

  const { data } = useQuery({
    queryKey: ['sessions', 'week', weekStart],
    queryFn: () => api.getWeekSessions(weekStart).then((d) => d.sessions),
    refetchInterval: 60000,
  });
  const sessions = data ?? [];

  const weekDays = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(weekStart + 'T00:00:00');
    d.setDate(d.getDate() + i);
    return toLocalDateStr(d);
  });

  function prevWeek() {
    const d = new Date(weekStart + 'T00:00:00');
    d.setDate(d.getDate() - 7);
    setWeekStart(toLocalDateStr(d));
  }

  function nextWeek() {
    const d = new Date(weekStart + 'T00:00:00');
    d.setDate(d.getDate() + 7);
    setWeekStart(toLocalDateStr(d));
  }

  function weekLabel() {
    const s = new Date(weekStart + 'T00:00:00');
    const e = new Date(weekStart + 'T00:00:00');
    e.setDate(e.getDate() + 6);
    return `${s.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} – ${e.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`;
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
    setActiveSession({ sessionId: null, todoId: null, todoTitle: title, startedAt: new Date().toISOString() });

    try {
      const session = await api.startFreeformSession(title);
      setActiveSession({ sessionId: session.id, todoId: null, todoTitle: title, startedAt: session.started_at });
      queryClient.invalidateQueries({ queryKey: ['sessions', 'week', weekStart] });
    } catch {
      setActiveSession(null);
    } finally {
      setStarting(false);
      setFreeformTitle('');
      setShowFreeformInput(false);
    }
  }

  function handleBlockClick(e, s) {
    e.stopPropagation();
    const rect = e.currentTarget.getBoundingClientRect();
    setPopover({
      session: s,
      x: rect.right + 8,
      y: Math.min(rect.top, window.innerHeight - 160),
    });
  }

  // Current time line position in px
  const nowDate = new Date(nowMs);
  const nowLinePx = nowDate.getHours() * 60 + nowDate.getMinutes();

  return (
    <div className="calendar-page">
      {/* Top bar */}
      <div className="calendar-header">
        <button className="cal-nav-btn" onClick={prevWeek}>‹ Prev</button>
        <span className="cal-week-label">{weekLabel()}</span>
        <button className="cal-nav-btn" onClick={nextWeek}>Next ›</button>
        <button
          className="cal-start-btn"
          onClick={() => { setShowFreeformInput((v) => !v); setFreeformTitle(''); }}
        >
          {showFreeformInput ? '× Cancel' : '+ Session'}
        </button>
      </div>

      {showFreeformInput && (
        <div className="freeform-input-row cal-freeform-header">
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

      {/* Day headers (fixed, outside scroll) */}
      <div className="cal-header-row">
        <div className="cal-gutter-spacer" />
        {weekDays.map((dayStr, i) => {
          const isToday = dayStr === todayStr;
          const dayNum = new Date(dayStr + 'T00:00:00').getDate();
          return (
            <div key={dayStr} className={`cal-day-header-cell${isToday ? ' is-today' : ''}`}>
              <span className="cal-day-name">{DAY_NAMES[i]}</span>
              <span className={`cal-day-num${isToday ? ' is-today' : ''}`}>{dayNum}</span>
            </div>
          );
        })}
      </div>

      {/* Scrollable time grid */}
      <div className="cal-scroll-body" ref={scrollRef}>
        <div className="cal-inner">
          {/* Time gutter */}
          <div className="cal-time-gutter">
            {HOURS.map((h) => (
              <div key={h} className="cal-hour-label" style={{ top: h * HOUR_PX }}>
                {formatHour(h)}
              </div>
            ))}
          </div>

          {/* Day columns */}
          <div className="cal-columns">
            {weekDays.map((dayStr) => {
              const isToday = dayStr === todayStr;
              const daySessions = sessions.filter(
                (s) => toLocalDateStr(new Date(s.started_at)) === dayStr
              );

              return (
                <div key={dayStr} className={`cal-day-col${isToday ? ' is-today' : ''}`}>
                  <div className="cal-timeline" style={{ height: TOTAL_HEIGHT }}>
                    {/* Hour lines */}
                    {HOURS.map((h) => (
                      <div key={h} className="cal-hour-line" style={{ top: h * HOUR_PX }} />
                    ))}

                    {/* Current time indicator */}
                    {isToday && (
                      <div className="cal-now-line" style={{ top: nowLinePx }} />
                    )}

                    {/* Session blocks */}
                    {daySessions.map((s) => {
                      const color = sessionColor(s);
                      const { top, height } = getBlockStyle(s, nowMs);
                      const isActive = activeSession?.sessionId === s.id;

                      return (
                        <div
                          key={s.id}
                          className={`cal-block${isActive ? ' is-active' : ''}`}
                          style={{ top, height, background: color }}
                          onClick={(e) => handleBlockClick(e, s)}
                        >
                          <span className="cal-block-title">
                            {s.todo_title || s.title || 'Session'}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Fixed-position popover — won't be clipped by overflow */}
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
          <p className="sp-title">
            {popover.session.todo_title || popover.session.title || 'Session'}
          </p>
          {popover.session.notes
            ? <p className="sp-notes">{popover.session.notes}</p>
            : <p className="sp-notes-empty">No notes</p>
          }
        </div>
      )}
    </div>
  );
}
