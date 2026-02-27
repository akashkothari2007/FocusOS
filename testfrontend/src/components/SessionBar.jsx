import { useState, useEffect, useRef } from 'react';
import { api } from '../api';

function formatTimer(totalSeconds) {
  const m = Math.floor(totalSeconds / 60).toString().padStart(2, '0');
  const s = (totalSeconds % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

export default function SessionBar({ activeSession, setActiveSession }) {
  const [elapsed, setElapsed] = useState(0);
  // notes lives here so typing doesn't bubble up to App on every keystroke
  const [notes, setNotes] = useState('');
  const notesRef = useRef('');

  // keep ref in sync so handleEnd can read current value without stale closure
  function handleNotesChange(e) {
    notesRef.current = e.target.value;
    setNotes(e.target.value);
  }

  // Reset when session changes (e.g. swap)
  useEffect(() => {
    setNotes('');
    notesRef.current = '';
  }, [activeSession.sessionId]);

  // Live timer
  useEffect(() => {
    const start = new Date(activeSession.startedAt).getTime();
    const tick = () => setElapsed(Math.floor((Date.now() - start) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [activeSession.startedAt]);

  async function handleEnd() {
    await api.endSession(activeSession.sessionId, notesRef.current);
    setActiveSession(null);
  }

  return (
    <div className="session-bar">
      <div className="session-bar-info">
        <span className="session-dot" />
        <span className="session-todo-title">{activeSession.todoTitle}</span>
        <span className="session-timer">{formatTimer(elapsed)}</span>
      </div>
      <textarea
        className="session-notes"
        placeholder="Session notes…"
        value={notes}
        onChange={handleNotesChange}
        rows={1}
      />
      <button className="btn-end" onClick={handleEnd}>
        End Session
      </button>
    </div>
  );
}
