import { useState, useRef, useEffect } from 'react';
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  SortableContext,
  verticalListSortingStrategy,
  useSortable,
  arrayMove,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { api } from '../api';

function formatDate(dt) {
  if (!dt) return null;
  return new Date(dt).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function parseSubtasks(raw) {
  if (!raw) return [];
  if (Array.isArray(raw)) return raw;
  try { return JSON.parse(raw); } catch { return []; }
}

function parseLinks(raw) {
  if (!raw) return [];
  if (Array.isArray(raw)) return raw;
  try { return JSON.parse(raw); } catch { return []; }
}

function ensureUrl(val) {
  const s = val.trim();
  if (!s) return '';
  if (/^https?:\/\//i.test(s)) return s;
  return `https://${s}`;
}

function LinkIcon({ size = 14 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
    </svg>
  );
}

function SortableSubtaskRow({ subtask, index, onToggle, onDelete }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: subtask.id });

  return (
    <div
      ref={setNodeRef}
      className={`subtask-row${isDragging ? ' subtask-dragging' : ''}`}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
        zIndex: isDragging ? 10 : 'auto',
      }}
    >
      <span className="subtask-drag-handle" {...attributes} {...listeners}>⠿</span>
      <input
        type="checkbox"
        checked={subtask.status === 'done'}
        onChange={() => onToggle(subtask.id)}
      />
      <span className={subtask.status === 'done' ? 'subtask-done' : ''}>{subtask.title}</span>
      <button
        className="subtask-delete"
        onClick={() => onDelete(index)}
        title="Delete subtask"
      >×</button>
    </div>
  );
}

export default function TodoCard({ todo, borderColor, isActiveSession, onStartSession, onMarkDone, onUpdate, dragHandleProps }) {
  const [expanded, setExpanded] = useState(false);
  const [editingTitle, setEditingTitle] = useState(false);
  const [title, setTitle] = useState(todo.title || '');
  const [editingDesc, setEditingDesc] = useState(false);
  const [desc, setDesc] = useState(todo.description || '');
  const [editingDueDate, setEditingDueDate] = useState(false);
  const [newSubtask, setNewSubtask] = useState('');
  const [linksOpen, setLinksOpen] = useState(false);
  const [newLinkUrl, setNewLinkUrl] = useState('');
  const [newLinkLabel, setNewLinkLabel] = useState('');
  const linksRef = useRef(null);

  const subtaskSensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } })
  );

  const subtasks = parseSubtasks(todo.subtasks);
  const links = parseLinks(todo.links);

  useEffect(() => {
    if (!linksOpen) return;
    function onMouseDown(e) {
      if (linksRef.current && !linksRef.current.contains(e.target)) {
        setLinksOpen(false);
      }
    }
    document.addEventListener('mousedown', onMouseDown);
    return () => document.removeEventListener('mousedown', onMouseDown);
  }, [linksOpen]);

  async function saveTitle() {
    setEditingTitle(false);
    const trimmed = title.trim();
    if (!trimmed || trimmed === todo.title) return;
    try {
      const updated = await api.updateTodo(todo.id, { title: trimmed });
      onUpdate(updated);
    } catch {
      setTitle(todo.title || '');
    }
  }

  function formatDateInput(dt) {
    if (!dt) return '';
    return new Date(dt).toISOString().slice(0, 10);
  }

  async function saveDueDate(value) {
    setEditingDueDate(false);
    const newDate = value || null;
    const currentDate = todo.due_date ? new Date(todo.due_date).toISOString().slice(0, 10) : null;
    if (newDate === currentDate) return;
    try {
      const updated = await api.updateTodo(todo.id, { due_date: newDate });
      onUpdate(updated);
    } catch { /* ignore */ }
  }

  async function saveDescription() {
    setEditingDesc(false);
    if (desc === (todo.description || '')) return;
    try {
      const updated = await api.updateTodo(todo.id, { description: desc });
      onUpdate(updated);
    } catch {
      setDesc(todo.description || '');
    }
  }

  function applySubtasks(newSubtasks) {
    onUpdate({ ...todo, subtasks: newSubtasks });
    api.updateTodo(todo.id, { subtasks: newSubtasks })
      .then(onUpdate)
      .catch(() => onUpdate(todo));
  }

  function applyLinks(newLinks) {
    onUpdate({ ...todo, links: newLinks });
    api.updateTodo(todo.id, { links: newLinks })
      .then(onUpdate)
      .catch(() => onUpdate(todo));
  }

  function toggleSubtask(subtaskId) {
    const toggled = subtasks.map((s) =>
      s.id === subtaskId ? { ...s, status: s.status === 'done' ? 'pending' : 'done' } : s
    );
    applySubtasks([
      ...toggled.filter((s) => s.status === 'pending'),
      ...toggled.filter((s) => s.status === 'done'),
    ]);
  }

  function deleteSubtask(index) {
    applySubtasks(subtasks.filter((_, i) => i !== index));
  }

  function handleSubtaskDragEnd({ active, over }) {
    if (!over || active.id === over.id) return;
    const oldIdx = subtasks.findIndex((s) => s.id === active.id);
    const newIdx = subtasks.findIndex((s) => s.id === over.id);
    applySubtasks(arrayMove(subtasks, oldIdx, newIdx));
  }

  function handleAddSubtask(e) {
    e.preventDefault();
    if (!newSubtask.trim()) return;
    const nextId = subtasks.length > 0 ? Math.max(...subtasks.map((s) => s.id)) + 1 : 1;
    setNewSubtask('');
    applySubtasks([
      ...subtasks.filter((s) => s.status === 'pending'),
      { id: nextId, title: newSubtask.trim(), status: 'pending' },
      ...subtasks.filter((s) => s.status === 'done'),
    ]);
  }

  function handleAddLink(e) {
    e.preventDefault();
    if (!newLinkUrl.trim()) return;
    const url = ensureUrl(newLinkUrl);
    const nextId = links.length > 0 ? Math.max(...links.map((l) => l.id)) + 1 : 1;
    setNewLinkUrl('');
    setNewLinkLabel('');
    applyLinks([...links, { id: nextId, url, label: newLinkLabel.trim() || null }]);
  }

  function deleteLink(linkId) {
    applyLinks(links.filter((l) => l.id !== linkId));
  }

  function handleMarkDone() {
    onMarkDone(todo.id);
    api.updateTodo(todo.id, { status: 'done' });
  }

  function handlePlayClick(e) {
    e.stopPropagation();
    onStartSession(todo);
  }

  return (
    <div className="todo-card" style={{ borderLeftColor: borderColor, position: 'relative', zIndex: linksOpen ? 100 : 'auto' }}>
      <div
        className={`todo-card-header${dragHandleProps ? ' todo-card-header--draggable' : ''}`}
        onClick={() => setExpanded((v) => !v)}
        {...(dragHandleProps || {})}
      >
        <div className="todo-card-title-row">
          {editingTitle ? (
            <input
              className="input input-sm todo-title-input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              onBlur={saveTitle}
              onKeyDown={(e) => { if (e.key === 'Enter') saveTitle(); if (e.key === 'Escape') { setTitle(todo.title); setEditingTitle(false); } }}
              onClick={(e) => e.stopPropagation()}
              autoFocus
            />
          ) : (
            <span
              className="todo-title"
              onDoubleClick={(e) => { e.stopPropagation(); setEditingTitle(true); }}
              title="Double-click to rename"
            >{title}</span>
          )}
          {todo.due_date && <span className="due-date">{formatDate(todo.due_date)}</span>}
        </div>
        <div className="links-btn-wrap" ref={linksRef}>
          <button
            className={`btn-links${linksOpen ? ' active' : ''}`}
            onClick={(e) => { e.stopPropagation(); setLinksOpen((v) => !v); }}
            title={links.length > 0 ? `${links.length} link${links.length !== 1 ? 's' : ''}` : 'Add links'}
          >
            <LinkIcon size={14} />
            {links.length > 0 && <span className="links-badge">{links.length}</span>}
          </button>
          {linksOpen && (
            <div className="links-dropdown" onClick={(e) => e.stopPropagation()}>
              <span className="links-dropdown-title">Links</span>
              {links.length === 0 ? (
                <p className="links-empty">No links yet — add one below.</p>
              ) : (
                <div className="links-list">
                  {links.map((link) => (
                    <div key={link.id} className="link-item">
                      <span className="link-item-icon"><LinkIcon size={12} /></span>
                      <div className="link-item-text">
                        {link.label && <span className="link-item-label">{link.label}</span>}
                        <a
                          href={link.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className={`link-item-url${!link.label ? ' solo' : ''}`}
                        >
                          {link.url.replace(/^https?:\/\//, '')}
                        </a>
                      </div>
                      <button className="link-delete" onClick={() => deleteLink(link.id)} title="Remove">×</button>
                    </div>
                  ))}
                </div>
              )}
              <div className="links-divider" />
              <form className="links-add-form" onSubmit={handleAddLink}>
                <input
                  className="input input-sm"
                  placeholder="Paste a URL…"
                  value={newLinkUrl}
                  onChange={(e) => setNewLinkUrl(e.target.value)}
                />
                <div className="links-add-row">
                  <input
                    className="input input-sm"
                    placeholder="Label (optional)"
                    value={newLinkLabel}
                    onChange={(e) => setNewLinkLabel(e.target.value)}
                  />
                  <button type="submit" className="btn-add-link">Add</button>
                </div>
              </form>
            </div>
          )}
        </div>
        <button
          className={`btn-play${isActiveSession ? ' active-session' : ''}`}
          onClick={handlePlayClick}
          title={isActiveSession ? 'Session in progress' : 'Start session'}
        >
          {isActiveSession ? '●' : '▶'}
        </button>
      </div>

      {expanded && (
        <div className="todo-card-body">
          {editingDesc ? (
            <textarea
              className="input textarea"
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              onBlur={saveDescription}
              autoFocus
              rows={3}
            />
          ) : (
            <p className="todo-desc" onClick={() => setEditingDesc(true)} title="Click to edit">
              {desc || <span className="placeholder">Add a description…</span>}
            </p>
          )}

          <div className="todo-due-date-row">
            {editingDueDate ? (
              <input
                type="date"
                className="input input-sm"
                defaultValue={formatDateInput(todo.due_date)}
                onBlur={(e) => saveDueDate(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') saveDueDate(e.target.value);
                  if (e.key === 'Escape') setEditingDueDate(false);
                }}
                autoFocus
              />
            ) : (
              <span
                className={`todo-due-date-label${!todo.due_date ? ' placeholder' : ''}`}
                onClick={() => setEditingDueDate(true)}
                title="Click to set due date"
              >
                {todo.due_date ? `Due: ${formatDate(todo.due_date)}` : 'Set due date…'}
              </span>
            )}
            {todo.due_date && !editingDueDate && (
              <button className="subtask-delete" onClick={() => saveDueDate('')} title="Remove due date">×</button>
            )}
          </div>

          <div className="subtasks">
            <form className="add-subtask-form" onSubmit={handleAddSubtask}>
              <input
                className="input input-sm"
                placeholder="Add subtask…"
                value={newSubtask}
                onChange={(e) => setNewSubtask(e.target.value)}
              />
            </form>
            <DndContext
              sensors={subtaskSensors}
              collisionDetection={closestCenter}
              onDragEnd={handleSubtaskDragEnd}
            >
              <SortableContext
                items={subtasks.map((s) => s.id)}
                strategy={verticalListSortingStrategy}
              >
                {subtasks.map((s, i) => (
                  <SortableSubtaskRow
                    key={s.id}
                    subtask={s}
                    index={i}
                    onToggle={toggleSubtask}
                    onDelete={deleteSubtask}
                  />
                ))}
              </SortableContext>
            </DndContext>
          </div>

          <div className="todo-card-footer">
            <button className="btn btn-done" onClick={handleMarkDone}>Mark done</button>
          </div>
        </div>
      )}
    </div>
  );
}
