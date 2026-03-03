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

  // Jobs
  getJobs: (status) =>
    request(`/api/v1/jobs${status ? `?status=${status}` : ''}`),

  getJob: (id) =>
    request(`/api/v1/jobs/${id}`),

  createJob: (data) =>
    request('/api/v1/jobs', { method: 'POST', body: JSON.stringify(data) }),

  updateJob: (id, data) =>
    request(`/api/v1/jobs/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  deleteJob: (id) =>
    request(`/api/v1/jobs/${id}`, { method: 'DELETE' }),

  analyzeJob: (id, input_doc_id) =>
    request(`/api/v1/jobs/${id}/analyze`, {
      method: 'POST',
      body: JSON.stringify({ input_doc_id }),
    }),

  deleteAnalysis: (id) =>
    request(`/api/v1/jobs/${id}/analysis`, { method: 'DELETE' }),

  // Docs
  getDocs: () =>
    request('/api/v1/docs'),

  createDoc: (data) =>
    request('/api/v1/docs', { method: 'POST', body: JSON.stringify(data) }),

  updateDoc: (id, data) =>
    request(`/api/v1/docs/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  setPrimaryDoc: (id) =>
    request(`/api/v1/docs/${id}/set-primary`, { method: 'PATCH' }),

  deleteDoc: (id) =>
    request(`/api/v1/docs/${id}`, { method: 'DELETE' }),

  // Profile
  getProfile: () =>
    request('/api/v1/profile'),

  updateProfile: (data) =>
    request('/api/v1/profile', { method: 'PATCH', body: JSON.stringify(data) }),
};
