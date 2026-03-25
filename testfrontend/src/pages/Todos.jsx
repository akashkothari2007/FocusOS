import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import Routines from '../components/Routines';
import {
  DndContext,
  DragOverlay,
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
import AddTodoForm from '../components/AddTodoForm';
import TodoCard from '../components/TodoCard';
import HabitTracker from '../components/HabitTracker';
import TodayStrip from '../components/TodayStrip';
import NewsDigest from '../components/NewsDigest';

const BORDER_COLORS = ['#6366f1', '#ec4899', '#f59e0b', '#14b8a6'];
const todoColor = (id) => BORDER_COLORS[id % BORDER_COLORS.length];

function SuggestionCard({ suggestion, onStart, onDismiss, onDateSet }) {
  const [showDate, setShowDate] = useState(false);
  const [dateValue, setDateValue] = useState('');
  const [saving, setSaving] = useState(false);

  async function handleSetDate() {
    if (!dateValue) return;
    setSaving(true);
    try {
      await api.updateTodo(suggestion.todo_id, { due_date: dateValue });
      onDateSet();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="suggestion-card">
      <span className="suggestion-label">✦ suggested</span>
      <div className="suggestion-title">{suggestion.title}</div>
      <div className="suggestion-reason">{suggestion.reason}</div>
      <div className="suggestion-actions">
        <button className="btn btn-primary btn-sm" onClick={onStart}>Start session</button>
        <button className="btn btn-sm" onClick={() => setShowDate(v => !v)}>Add due date</button>
        <button className="btn btn-sm suggestion-dismiss" onClick={onDismiss}>Dismiss</button>
      </div>
      {showDate && (
        <div className="suggestion-date-row">
          <input
            type="date"
            className="input input-sm"
            value={dateValue}
            onChange={e => setDateValue(e.target.value)}
          />
          <button className="btn btn-sm btn-primary" onClick={handleSetDate} disabled={saving || !dateValue}>
            {saving ? '...' : 'Set'}
          </button>
        </div>
      )}
    </div>
  );
}

function SortableTodoItem({ todo, borderColor, ...cardProps }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: todo.id });

  return (
    <div
      ref={setNodeRef}
      className="todo-sortable-item"
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0 : 1,
      }}
    >
      <TodoCard
        todo={todo}
        borderColor={borderColor}
        dragHandleProps={{ ...attributes, ...listeners }}
        {...cardProps}
      />
    </div>
  );
}

export default function Todos({ activeSession, setActiveSession }) {
  const queryClient = useQueryClient();
  const [activeId, setActiveId] = useState(null);
  const [view, setView] = useState('todos');

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  );

  const { data } = useQuery({
    queryKey: ['todos', 'pending'],
    queryFn: () => api.getTodos('pending').then((d) => d.todos),
  });
  const todos = data ?? [];

  const { data: suggestionData, refetch: refetchSuggestion } = useQuery({
    queryKey: ['suggestion'],
    queryFn: () => api.getSuggestion(),
    enabled: !activeSession && view === 'todos',
    staleTime: Infinity,
    retry: false,
  });
  const suggestion = suggestionData?.suggestion ?? null;

  const pinned = todos.filter((t) => t.due_date);
  const undated = todos.filter((t) => !t.due_date);

  const activeTodo = activeId ? undated.find((t) => t.id === activeId) : null;
  const activeIdx = activeId ? undated.findIndex((t) => t.id === activeId) : -1;

  function handleMarkDone(todoId) {
    queryClient.setQueryData(['todos', 'pending'], (old = []) =>
      old.filter((t) => t.id !== todoId)
    );
  }

  function handleUpdate(updatedTodo) {
    queryClient.cancelQueries({ queryKey: ['todos', 'pending'] });
    queryClient.setQueryData(['todos', 'pending'], (old = []) =>
      old.map((t) => (t.id === updatedTodo.id ? updatedTodo : t))
    );
  }

  async function handleStartSession(todo) {
    if (activeSession) {
      const ok = window.confirm(
        `End session for "${activeSession.todoTitle}" and start one for "${todo.title}"?`
      );
      if (!ok) return;
      await api.endSession(activeSession.sessionId, null);
    }

    setActiveSession({
      sessionId: null,
      todoId: todo.id,
      todoTitle: todo.title,
      startedAt: new Date().toISOString(),
    });
    try {
      const session = await api.startSession(todo.id);
      setActiveSession({
        sessionId: session.id,
        todoId: todo.id,
        todoTitle: todo.title,
        startedAt: session.started_at,
      });
    } catch {
      setActiveSession(null);
    }
  }

  function hideSuggestion() {
    queryClient.setQueryData(['suggestion'], { suggestion: null });
  }

  async function handleDismissSuggestion() {
    await api.dismissSuggestion(suggestion.todo_id);
    hideSuggestion();
  }

  async function handleStartSuggestion() {
    hideSuggestion();
    await handleStartSession({ id: suggestion.todo_id, title: suggestion.title });
  }

  function handleDragStart({ active }) {
    setActiveId(active.id);
  }

  async function handleDragEnd({ active, over }) {
    setActiveId(null);
    if (!over || active.id === over.id) return;

    const oldIdx = undated.findIndex((t) => t.id === active.id);
    const newIdx = undated.findIndex((t) => t.id === over.id);
    const reordered = arrayMove(undated, oldIdx, newIdx);

    // Cancel any in-flight refetches so they don't snap the list back
    await queryClient.cancelQueries({ queryKey: ['todos', 'pending'] });

    // Optimistic update
    queryClient.setQueryData(['todos', 'pending'], [...pinned, ...reordered]);

    const ids = reordered.map((t) => t.id);
    try {
      await api.reorderTodos(ids);
    } catch {
      // Rollback on failure
      queryClient.invalidateQueries({ queryKey: ['todos', 'pending'] });
    }
  }

  function handleDragCancel() {
    setActiveId(null);
  }

  return (
    <div className="todos-page">
      <TodayStrip activeSession={activeSession} setActiveSession={setActiveSession} />
      <div className="todos-main">
        <div className="view-toggle">
          <button className={`view-toggle-btn${view === 'todos' ? ' active' : ''}`} onClick={() => setView('todos')}>Todos</button>
          <button className={`view-toggle-btn${view === 'routines' ? ' active' : ''}`} onClick={() => setView('routines')}>Routines</button>
        </div>

        {view === 'routines' ? <Routines /> : <>
        {suggestion && (
          <SuggestionCard
            suggestion={suggestion}
            onStart={handleStartSuggestion}
            onDismiss={handleDismissSuggestion}
            onDateSet={hideSuggestion}
          />
        )}
        <AddTodoForm />
        <div className="todo-list">
          {/* Pinned (dated) todos — not draggable */}
          {pinned.map((todo) => (
            <TodoCard
              key={todo.id}
              todo={todo}
              borderColor={todoColor(todo.id)}
              isActiveSession={activeSession?.todoId === todo.id}
              onStartSession={handleStartSession}
              onMarkDone={handleMarkDone}
              onUpdate={handleUpdate}
            />
          ))}

          {/* Undated todos — draggable */}
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
            onDragCancel={handleDragCancel}
          >
            <SortableContext
              items={undated.map((t) => t.id)}
              strategy={verticalListSortingStrategy}
            >
              <div className="todo-list-undated">
                {undated.map((todo) => (
                  <SortableTodoItem
                    key={todo.id}
                    todo={todo}
                    borderColor={todoColor(todo.id)}
                    isActiveSession={activeSession?.todoId === todo.id}
                    onStartSession={handleStartSession}
                    onMarkDone={handleMarkDone}
                    onUpdate={handleUpdate}
                  />
                ))}
              </div>
            </SortableContext>

            <DragOverlay dropAnimation={null}>
              {activeTodo && (
                <div className="todo-drag-overlay">
                  <TodoCard
                    todo={activeTodo}
                    borderColor={todoColor(activeTodo.id)}
                    isActiveSession={activeSession?.todoId === activeTodo.id}
                    onStartSession={handleStartSession}
                    onMarkDone={handleMarkDone}
                    onUpdate={handleUpdate}
                  />
                </div>
              )}
            </DragOverlay>
          </DndContext>

          {todos.length === 0 && (
            <p className="empty-state">No pending todos. Add one above.</p>
          )}
        </div>

        <NewsDigest />
        </>}
      </div>
      <aside className="todos-sidebar">
        <HabitTracker />
      </aside>
    </div>
  );
}
