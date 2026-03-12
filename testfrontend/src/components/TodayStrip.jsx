import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';

const SESSION_COLORS = ['#6366f1', '#ec4899', '#f59e0b', '#14b8a6'];
const FREEFORM_COLOR = '#8b5cf6';
const HOUR_PX = 48;  // px per hour (0.8px per minute)
const TOTAL_HEIGHT = 24 * HOUR_PX;
const PPM = HOUR_PX / 60;  // pixels per minute
const HOURS = Array.from({ length: 24 }, (_, i) => i);

function sessionColor(s) {
  if (!s.todo_id) return FREEFORM_COLOR;
  return SESSION_COLORS[s.todo_id % SESSION_COLORS.length];
}

function fmtElapsed(startedAt, nowMs) {
  const secs = Math.max(0, Math.floor((nowMs - new Date(startedAt)) / 1000));
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

function formatHour(h) {
  if (h === 0) return '12a';
  if (h < 12) return `${h}a`;
  if (h === 12) return '12p';
  return `${h - 12}p`;
}

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
  const durationMins = endMin - startMin;
  return {
    top: startMin * PPM,
    height: Math.max(4, durationMins * PPM),
    showTitle: durationMins >= 20,
  };
}

export default function TodayStrip({ activeSession, setActiveSession }) {
  const queryClient = useQueryClient();
  const todayStr = toLocalDateStr(new Date());
  const [viewDate, setViewDate] = useState(todayStr);
  const [popover, setPopover] = useState(null);
  const [showFreeformInput, setShowFreeformInput] = useState(false);
  const [freeformTitle, setFreeformTitle] = useState('');
  const [starting, setStarting] = useState(false);
  const [nowMs, setNowMs] = useState(Date.now());
  const scrollRef = useRef(null);

  const isToday = viewDate === todayStr;

  // Update every second for elapsed timer + active block growth
  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  // Scroll to current time (or 8am for past days) when day changes
  useEffect(() => {
    if (!scrollRef.current) return;
    const now = new Date();
    const scrollTo = isToday
      ? Math.max(0, (now.getHours() * 60 + now.getMinutes()) * PPM - 80)
      : 8 * HOUR_PX - 40;
    scrollRef.current.scrollTop = scrollTo;
  }, [viewDate, isToday]);

  // Close popover on outside click
  useEffect(() => {
    if (!popover) return;
    function handle() { setPopover(null); }
    document.addEventListener('click', handle);
    return () => document.removeEventListener('click', handle);
  }, [popover]);

  // Refresh when active session changes
  useEffect(() => {
    queryClient.invalidateQueries({ queryKey: ['sessions', 'day', todayStr] });
  }, [activeSession?.sessionId, queryClient, todayStr]);

  const { data } = useQuery({
    queryKey: ['sessions', 'day', viewDate],
    queryFn: () => api.getTodaySessions(viewDate).then((d) => d.sessions),
    refetchInterval: isToday ? 30000 : false,
  });
  const sessions = data ?? [];

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
      const ok = window.confirm(`End "${activeSession.todoTitle}" and start "${title}"?`);
      if (!ok) return;
      await api.endSession(activeSession.sessionId, null);
    }
    setStarting(true);
    setActiveSession({ sessionId: null, todoId: null, todoTitle: title, startedAt: new Date().toISOString() });
    try {
      const session = await api.startFreeformSession(title);
      setActiveSession({ sessionId: session.id, todoId: null, todoTitle: title, startedAt: session.started_at });
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

  async function handleDelete(e, s) {
    e.stopPropagation();
    await api.deleteSession(s.id);
    if (activeSession?.sessionId === s.id) setActiveSession(null);
    queryClient.invalidateQueries({ queryKey: ['sessions', 'day', viewDate] });
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

  const nowDate = new Date(nowMs);
  const nowLinePx = (nowDate.getHours() * 60 + nowDate.getMinutes()) * PPM;
  const activeInList = activeSession && sessions.some((s) => s.id === activeSession.sessionId);
  const activeColor = activeSession?.todoId
    ? SESSION_COLORS[activeSession.todoId % SESSION_COLORS.length]
    : FREEFORM_COLOR;

  return (
    <div className="today-strip">
      {/* Day navigation */}
      <div className="today-strip-header">
        <button className="today-nav-btn" onClick={prevDay}>‹</button>
        <span className="today-label">{formatDayLabel(viewDate)}</span>
        <button className="today-nav-btn" onClick={nextDay} disabled={viewDate >= todayStr}>›</button>
        {isToday && (
          <button
            className="today-add-btn"
            onClick={() => { setShowFreeformInput((v) => !v); setFreeformTitle(''); }}
          >
            {showFreeformInput ? '×' : '+'}
          </button>
        )}
      </div>

      {/* Active session pill — always visible regardless of scroll */}
      {isToday && activeSession && (
        <div className="today-active-pill" style={{ background: activeColor }}>
          <span className="tap-dot" />
          <span className="tap-title">{activeSession.todoTitle}</span>
          <span className="tap-timer">{fmtElapsed(activeSession.startedAt, nowMs)}</span>
          <button className="tap-end" onClick={handleEndSession}>End</button>
        </div>
      )}

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

      {/* Mini time grid */}
      <div className="today-time-grid" ref={scrollRef}>
        <div className="today-time-inner">
          {/* Hour labels */}
          <div className="today-time-gutter">
            {HOURS.map((h) => (
              <div key={h} className="today-hour-label" style={{ top: h * HOUR_PX }}>
                {formatHour(h)}
              </div>
            ))}
          </div>

          {/* Day column */}
          <div className="today-day-col">
            <div style={{ position: 'relative', height: TOTAL_HEIGHT }}>
              {/* Hour lines */}
              {HOURS.map((h) => (
                <div key={h} className="today-hour-line" style={{ top: h * HOUR_PX }} />
              ))}

              {/* Current time indicator */}
              {isToday && <div className="today-now-line" style={{ top: nowLinePx }} />}

              {/* Optimistic active block (before query refetches) */}
              {isToday && activeSession && !activeInList && (() => {
                const { top, height, showTitle } = getBlockStyle(
                  { started_at: activeSession.startedAt, ended_at: null },
                  nowMs
                );
                return (
                  <div
                    className="cal-block is-active"
                    style={{ top, height, background: activeColor }}
                  >
                    {showTitle && <span className="cal-block-title">{activeSession.todoTitle}</span>}
                  </div>
                );
              })()}

              {/* Session blocks */}
              {sessions.map((s) => {
                const color = sessionColor(s);
                const isActive = activeSession?.sessionId === s.id;
                const { top, height, showTitle } = getBlockStyle(s, nowMs);
                return (
                  <div
                    key={s.id}
                    className={`cal-block${isActive ? ' is-active' : ''}`}
                    style={{ top, height, background: color }}
                    onClick={(e) => openPopover(e, s)}
                  >
                    {showTitle && (
                      <span className="cal-block-title">
                        {s.todo_title || s.title || 'Session'}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Fixed-position popover — portalled to body to escape stacking contexts */}
      {popover && createPortal(
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
          <button
            className="sp-delete-btn"
            onClick={async (e) => {
              e.stopPropagation();
              await handleDelete(e, popover.session);
              setPopover(null);
            }}
          >Delete session</button>
        </div>,
        document.body
      )}
    </div>
  );
}
