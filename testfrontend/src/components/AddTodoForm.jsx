import { useState } from 'react';
import { api } from '../api';

export default function AddTodoForm({ onAdd }) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!title.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const todo = await api.createTodo({
        title: title.trim(),
        description: description.trim() || undefined,
        due_date: dueDate || undefined,
      });
      onAdd(todo);
      setTitle('');
      setDescription('');
      setDueDate('');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
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
        <button className="btn btn-primary" type="submit" disabled={loading}>
          {loading ? '...' : 'Add'}
        </button>
      </div>
      <textarea
        className="input textarea"
        placeholder="Description (optional)"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        rows={2}
      />
      {error && <p style={{ color: '#e11d48', fontSize: 13 }}>{error}</p>}
    </form>
  );
}
