import { useState, useEffect } from 'react';
import { api } from '../api';

function formatDate(dt) {
  if (!dt) return '—';
  return new Date(dt).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  });
}

const EMPTY_FORM = { title: '', content: '' };

export default function Docs() {
  const [docs, setDocs]           = useState([]);
  const [showForm, setShowForm]   = useState(false);
  const [editingDoc, setEditingDoc] = useState(null);
  const [form, setForm]           = useState(EMPTY_FORM);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState(null);

  useEffect(() => {
    api.getDocs().then((data) => setDocs(data.docs));
  }, []);

  function openCreate() {
    setEditingDoc(null);
    setForm(EMPTY_FORM);
    setError(null);
    setShowForm(true);
  }

  function openEdit(doc) {
    setEditingDoc(doc);
    setForm({ title: doc.title, content: doc.content || '' });
    setError(null);
    setShowForm(true);
  }

  function cancelForm() {
    setShowForm(false);
    setEditingDoc(null);
    setError(null);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      if (editingDoc) {
        const patch = {};
        if (form.title   !== editingDoc.title)          patch.title   = form.title;
        if (form.content !== (editingDoc.content || '')) patch.content = form.content;
        if (Object.keys(patch).length === 0) { cancelForm(); return; }
        const updated = await api.updateDoc(editingDoc.id, patch);
        setDocs((prev) => prev.map((d) => (d.id === editingDoc.id ? updated : d)));
      } else {
        const created = await api.createDoc({ title: form.title, content: form.content });
        setDocs((prev) => [created, ...prev]);
      }
      cancelForm();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSetPrimary(docId) {
    try {
      await api.setPrimaryDoc(docId);
      setDocs((prev) => prev.map((d) => ({ ...d, is_primary: d.id === docId })));
    } catch (err) {
      alert(err.message);
    }
  }

  async function handleDelete(docId) {
    if (!window.confirm('Delete this doc?')) return;
    try {
      await api.deleteDoc(docId);
      setDocs((prev) => prev.filter((d) => d.id !== docId));
      if (editingDoc?.id === docId) cancelForm();
    } catch (err) {
      alert(err.message);
    }
  }

  return (
    <div className="page">
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h2 className="page-title">Docs</h2>
        <button
          className="btn btn-primary"
          onClick={showForm ? cancelForm : openCreate}
        >
          {showForm ? 'Cancel' : '+ New Doc'}
        </button>
      </div>

      {/* Create / edit form */}
      {showForm && (
        <form className="add-form" onSubmit={handleSubmit}>
          <input
            className="input"
            placeholder="Title *"
            required
            value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
          />
          <textarea
            className="input textarea"
            placeholder="LaTeX content..."
            rows={12}
            value={form.content}
            onChange={(e) => setForm((f) => ({ ...f, content: e.target.value }))}
            style={{ fontFamily: 'monospace', fontSize: 13 }}
          />
          {error && <p style={{ color: '#dc2626', fontSize: 13 }}>{error}</p>}
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button className="btn btn-primary" type="submit" disabled={loading}>
              {loading ? '...' : editingDoc ? 'Save Changes' : 'Create Doc'}
            </button>
          </div>
        </form>
      )}

      {/* Doc list */}
      <div className="todo-list">
        {docs.map((doc) => (
          <div
            key={doc.id}
            className="todo-card"
            style={{ borderLeftColor: doc.is_primary ? '#6366f1' : '#e0e0e4' }}
          >
            <div className="todo-card-header" style={{ cursor: 'default' }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="todo-card-title-row">
                  <span className="todo-title">{doc.title}</span>
                  {doc.is_primary && (
                    <span style={{
                      fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 5,
                      background: '#eef0ff', color: '#6366f1', letterSpacing: '0.5px',
                      flexShrink: 0, textTransform: 'uppercase',
                    }}>
                      Primary
                    </span>
                  )}
                </div>
                <div style={{ fontSize: 13, color: '#888', marginTop: 3 }}>
                  {formatDate(doc.created_at)}
                </div>
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                {!doc.is_primary && (
                  <button
                    className="btn"
                    style={{ fontSize: 12, padding: '5px 11px', background: '#f0f0f2', color: '#555' }}
                    onClick={() => handleSetPrimary(doc.id)}
                  >
                    Set Primary
                  </button>
                )}
                <button
                  className="btn"
                  style={{ fontSize: 12, padding: '5px 11px', background: '#f0f0f2', color: '#555' }}
                  onClick={() => openEdit(doc)}
                >
                  Edit
                </button>
                <button
                  className="btn"
                  style={{ fontSize: 12, padding: '5px 11px', background: '#fff1f2', color: '#dc2626' }}
                  onClick={() => handleDelete(doc.id)}
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        ))}

        {docs.length === 0 && (
          <p className="empty-state">No docs yet. Create one above.</p>
        )}
      </div>
    </div>
  );
}
