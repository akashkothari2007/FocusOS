// All requests are proxied to http://localhost:8000 via vite.config.js
// so BASE_URL is just '' here — the URL is defined exactly once (in vite.config.js).
const BASE_URL = '';

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (res.status === 204) return null;
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Request failed');
  return data;
}

export const api = {
  getTodos: (status) =>
    request(`/api/v1/todos${status ? `?status=${status}` : ''}`),

  createTodo: (data) =>
    request('/api/v1/todos', { method: 'POST', body: JSON.stringify(data) }),

  updateTodo: (id, data) =>
    request(`/api/v1/todos/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  deleteTodo: (id) =>
    request(`/api/v1/todos/${id}`, { method: 'DELETE' }),

  getSessions: (todoId) =>
    request(`/api/v1/todos/${todoId}/sessions`),

  startSession: (todoId) =>
    request(`/api/v1/todos/${todoId}/sessions/start`, { method: 'POST' }),

  endSession: (sessionId, notes) =>
    request(`/api/v1/sessions/${sessionId}/end`, {
      method: 'PATCH',
      body: JSON.stringify({ notes }),
    }),
};
