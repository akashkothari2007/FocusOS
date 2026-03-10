import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';

export default function AddTodoForm() {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [dueDate, setDueDate] = useState('');
  const queryClient = useQueryClient();

  const addMutation = useMutation({
    mutationFn: (payload) => api.createTodo(payload),
    onMutate: async (payload) => {
      await queryClient.cancelQueries({ queryKey: ['todos', 'pending'] });
      const prev = queryClient.getQueryData(['todos', 'pending']);
      const temp = { id: `temp-${Date.now()}`, subtasks: [], status: 'pending', ...payload };
      queryClient.setQueryData(['todos', 'pending'], (old = []) => [temp, ...old]);
      return { prev };
    },
    onError: (_, __, ctx) => queryClient.setQueryData(['todos', 'pending'], ctx.prev),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['todos', 'pending'] }),
  });

  function handleSubmit(e) {
    e.preventDefault();
    if (!title.trim()) return;
    addMutation.mutate(
      {
        title: title.trim(),
        description: description.trim() || undefined,
        due_date: dueDate || undefined,
      },
      {
        onSuccess: () => {
          setTitle('');
          setDescription('');
          setDueDate('');
        },
      }
    );
  }

  return (
    <form className="add-form" onSubmit={handleSubmit}>
      <div className="add-form-row">
        <input
          className="input"
          placeholder="New todo..."
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
        />
        <input
          className="input input-date"
          type="date"
          value={dueDate}
          onChange={(e) => setDueDate(e.target.value)}
        />
        <button className="btn btn-primary" type="submit" disabled={addMutation.isPending}>
          {addMutation.isPending ? '...' : 'Add'}
        </button>
      </div>
      <textarea
        className="input textarea"
        placeholder="Description (optional)"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        rows={2}
      />
      {addMutation.isError && (
        <p style={{ color: '#e11d48', fontSize: 13 }}>{addMutation.error.message}</p>
      )}
    </form>
  );
}
