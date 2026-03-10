import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import AddTodoForm from '../components/AddTodoForm';
import TodoCard from '../components/TodoCard';
import HabitTracker from '../components/HabitTracker';

const BORDER_COLORS = ['#6366f1', '#ec4899', '#f59e0b', '#14b8a6'];

export default function Todos({ activeSession, setActiveSession }) {
  const queryClient = useQueryClient();

  const { data } = useQuery({
    queryKey: ['todos', 'pending'],
    queryFn: () => api.getTodos('pending').then((d) => d.todos),
  });
  const todos = data ?? [];

  function handleMarkDone(todoId) {
    queryClient.setQueryData(['todos', 'pending'], (old = []) =>
      old.filter((t) => t.id !== todoId)
    );
  }

  function handleUpdate(updatedTodo) {
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

    const session = await api.startSession(todo.id);
    setActiveSession({
      sessionId: session.id,
      todoId: todo.id,
      todoTitle: todo.title,
      startedAt: session.started_at,
    });
  }

  return (
    <div className="todos-page">
      <div className="todos-main">
        <AddTodoForm />
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
      <aside className="todos-sidebar">
        <HabitTracker />
      </aside>
    </div>
  );
}
