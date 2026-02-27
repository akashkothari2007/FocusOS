import { useEffect } from 'react';
import { api } from '../api';
import AddTodoForm from '../components/AddTodoForm';
import TodoCard from '../components/TodoCard';

const BORDER_COLORS = ['#6366f1', '#ec4899', '#f59e0b', '#14b8a6'];

export default function Todos({ todos, setTodos, activeSession, setActiveSession }) {
  useEffect(() => {
    api.getTodos('pending').then((data) => setTodos(data.todos));
  }, []);

  function handleAddTodo(newTodo) {
    setTodos((prev) => [newTodo, ...prev]);
  }

  function handleMarkDone(todoId) {
    setTodos((prev) => prev.filter((t) => t.id !== todoId));
  }

  function handleUpdate(updatedTodo) {
    setTodos((prev) => prev.map((t) => (t.id === updatedTodo.id ? updatedTodo : t)));
  }

  async function handleStartSession(todo) {
    if (activeSession) {
      const ok = window.confirm(
        `End session for "${activeSession.todoTitle}" and start one for "${todo.title}"?`
      );
      if (!ok) return;
      // End current session (notes are local in SessionBar — we end without notes here)
      await api.endSession(activeSession.sessionId, null);
    }

    const session = await api.startSession(todo.id);
    setActiveSession({
      sessionId: session.id,
      todoId: todo.id,
      todoTitle: todo.title,
      startedAt: session.started_at,
    });
  }

  return (
    <div className="page">
      <AddTodoForm onAdd={handleAddTodo} />
      <div className="todo-list">
        {todos.map((todo, i) => (
          <TodoCard
            key={todo.id}
            todo={todo}
            borderColor={BORDER_COLORS[i % BORDER_COLORS.length]}
            isActiveSession={activeSession?.todoId === todo.id}
            onStartSession={handleStartSession}
            onMarkDone={handleMarkDone}
            onUpdate={handleUpdate}
          />
        ))}
        {todos.length === 0 && (
          <p className="empty-state">No pending todos. Add one above.</p>
        )}
      </div>
    </div>
  );
}
