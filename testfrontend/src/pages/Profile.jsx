import { useState, useEffect, useRef } from 'react';
import { api } from '../api';

// Module-level key counter — gives every list item a stable, unique React key
let _k = 0;
const newKey = () => ++_k;

function wrap(obj)    { return { _key: newKey(), ...obj }; }
function blankProject()    { return wrap({ title: '', bulletsText: '', link: '', tech: '' }); }
function blankExperience() { return wrap({ company: '', role: '', date: '', location: '', bulletsText: '' }); }

// bullets array → "• line1\n• line2"
function toBulletsText(bullets) {
  return (bullets || []).filter(Boolean).map(b => '• ' + b).join('\n');
}

// "• line1\n• line2" → ["line1", "line2"]
function fromBulletsText(text) {
  return text.split('\n').map(s => s.replace(/^•\s*/, '').trim()).filter(Boolean);
}

// Ensure every non-empty line starts with "• " as user types
function autoBullet(value) {
  return value.split('\n').map(line =>
    line && !line.startsWith('• ') ? '• ' + line.replace(/^•\s*/, '') : line
  ).join('\n');
}

// Convert a project from the API shape → local editable shape
function fromApiProject(p) {
  const bullets = p.bullets || (p.description ? p.description.split('\n') : []);
  return wrap({ title: p.title || '', link: p.link || '', tech: p.tech || '', bulletsText: toBulletsText(bullets) });
}

// Convert an experience from the API shape → local editable shape
function fromApiExp(e) {
  return wrap({ ...e, bulletsText: toBulletsText(e.bullets || []) });
}

// Section header used by all three sections
function SectionHeader({ title, onAdd }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
      <h3 style={{ fontSize: 16, fontWeight: 700, color: '#111' }}>{title}</h3>
      <button
        type="button"
        className="btn"
        style={{ fontSize: 13, padding: '5px 12px', background: '#f0f0f2', color: '#555' }}
        onClick={onAdd}
      >
        + Add
      </button>
    </div>
  );
}

// Red remove button reused on every card
function RemoveBtn({ onClick }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
      <button
        type="button"
        className="btn"
        style={{ fontSize: 12, padding: '4px 12px', background: '#fff1f2', color: '#dc2626' }}
        onClick={onClick}
      >
        Remove
      </button>
    </div>
  );
}

export default function Profile() {
  const [projects, setProjects]       = useState([]);
  const [experiences, setExperiences] = useState([]);
  const [skills, setSkills]           = useState('');
  const [loading, setLoading]         = useState(true);
  const [saving, setSaving]           = useState(false);
  const [saveMsg, setSaveMsg]         = useState('');   // '' | 'saved' | error text
  const [authError, setAuthError]     = useState(false);
  const [emailStatus, setEmailStatus] = useState(null); // null | { connected, email }

  useEffect(() => {
    // Check for ?auth_error=true from OAuth redirect
    const params = new URLSearchParams(window.location.search);
    if (params.get('auth_error') === 'true') {
      setAuthError(true);
      // Clean the URL param without reload
      const clean = window.location.pathname;
      window.history.replaceState({}, '', clean);
      setTimeout(() => setAuthError(false), 5000);
    }

    api.getProfile()
      .then((data) => {
        setProjects((data.projects || []).map(fromApiProject));
        setExperiences((data.experiences || []).map(fromApiExp));
        setSkills(data.skills || '');
      })
      .catch(() => {
        // 404 = profile row not seeded yet — just leave empty state
      })
      .finally(() => setLoading(false));

    api.getEmailStatus()
      .then((data) => setEmailStatus(data))
      .catch(() => setEmailStatus({ connected: false }));
  }, []);

  // ── Projects ─────────────────────────────────────────────
  function updateProject(key, field, value) {
    setProjects((prev) => prev.map((p) => (p._key === key ? { ...p, [field]: value } : p)));
  }

  // ── Experiences ───────────────────────────────────────────
  function updateExperience(key, field, value) {
    setExperiences((prev) => prev.map((e) => (e._key === key ? { ...e, [field]: value } : e)));
  }

  // ── Save ──────────────────────────────────────────────────
  async function handleSave() {
    setSaving(true);
    setSaveMsg('');
    try {
      const payload = {
        projects: projects.map(({ _key, bulletsText, ...p }) => ({
          ...p,
          bullets: fromBulletsText(bulletsText),
        })),
        experiences: experiences.map(({ _key, bulletsText, ...e }) => ({
          ...e,
          bullets: fromBulletsText(bulletsText),
        })),
        skills,
      };
      await api.updateProfile(payload);
      setSaveMsg('saved');
      setTimeout(() => setSaveMsg(''), 2500);
    } catch (err) {
      setSaveMsg(err.message);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="page"><p className="empty-state">Loading...</p></div>;

  const isError = saveMsg && saveMsg !== 'saved';

  return (
    <div className="page">
      {/* Auth error banner */}
      {authError && (
        <div style={{
          background: '#fff1f2',
          border: '1px solid #fecaca',
          borderRadius: 8,
          padding: '12px 16px',
          marginBottom: 20,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 16 }}>⚠️</span>
            <span style={{ fontSize: 14, color: '#dc2626', fontWeight: 500 }}>
              Microsoft connection failed, please try again
            </span>
          </div>
          <button
            type="button"
            onClick={() => setAuthError(false)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#dc2626', fontSize: 18, lineHeight: 1 }}
          >
            ×
          </button>
        </div>
      )}

      {/* Page header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 36 }}>
        <h2 className="page-title">Profile</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {saveMsg === 'saved' && (
            <span style={{ fontSize: 13, color: '#16a34a', fontWeight: 500 }}>Saved!</span>
          )}
          {isError && (
            <span style={{ fontSize: 13, color: '#dc2626' }}>{saveMsg}</span>
          )}
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      {/* ── Projects ─────────────────────────────────────── */}
      <section style={{ marginBottom: 40 }}>
        <SectionHeader title="Projects" onAdd={() => setProjects((p) => [...p, blankProject()])} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {projects.map((p) => (
            <div key={p._key} className="todo-card" style={{ borderLeftColor: '#6366f1' }}>
              <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div className="add-form-row">
                  <input
                    className="input"
                    placeholder="Title"
                    value={p.title}
                    onChange={(e) => updateProject(p._key, 'title', e.target.value)}
                  />
                  <input
                    className="input"
                    placeholder="Link"
                    value={p.link}
                    onChange={(e) => updateProject(p._key, 'link', e.target.value)}
                  />
                </div>
                <input
                  className="input"
                  placeholder="Tech (comma separated — React, FastAPI, PostgreSQL...)"
                  value={p.tech}
                  onChange={(e) => updateProject(p._key, 'tech', e.target.value)}
                />
                <textarea
                  className="input textarea"
                  placeholder={'Bullets (one per line)\n• Built X that did Y\n• Reduced latency by 40%'}
                  rows={3}
                  value={p.bulletsText}
                  onChange={(e) => updateProject(p._key, 'bulletsText', autoBullet(e.target.value))}
                />
                <RemoveBtn onClick={() => setProjects((prev) => prev.filter((x) => x._key !== p._key))} />
              </div>
            </div>
          ))}
          {projects.length === 0 && (
            <p style={{ fontSize: 14, color: '#aaa', padding: '8px 0' }}>No projects yet.</p>
          )}
        </div>
      </section>

      {/* ── Experiences ──────────────────────────────────── */}
      <section style={{ marginBottom: 40 }}>
        <SectionHeader title="Experiences" onAdd={() => setExperiences((e) => [...e, blankExperience()])} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {experiences.map((e) => (
            <div key={e._key} className="todo-card" style={{ borderLeftColor: '#14b8a6' }}>
              <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div className="add-form-row">
                  <input
                    className="input"
                    placeholder="Company"
                    value={e.company}
                    onChange={(ev) => updateExperience(e._key, 'company', ev.target.value)}
                  />
                  <input
                    className="input"
                    placeholder="Role"
                    value={e.role}
                    onChange={(ev) => updateExperience(e._key, 'role', ev.target.value)}
                  />
                  <input
                    className="input"
                    placeholder="Date (e.g. Jun 2023 – Present)"
                    value={e.date}
                    onChange={(ev) => updateExperience(e._key, 'date', ev.target.value)}
                    style={{ maxWidth: 220 }}
                  />
                  <input
                    className="input"
                    placeholder="Location (e.g. San Francisco, CA)"
                    value={e.location || ''}
                    onChange={(ev) => updateExperience(e._key, 'location', ev.target.value)}
                    style={{ maxWidth: 220 }}
                  />
                </div>
                <textarea
                  className="input textarea"
                  placeholder={'Bullets (one per line)\nBuilt X that did Y\nImproved Z by 30%'}
                  rows={4}
                  value={e.bulletsText}
                  onChange={(ev) => updateExperience(e._key, 'bulletsText', autoBullet(ev.target.value))}
                />
                <RemoveBtn onClick={() => setExperiences((prev) => prev.filter((x) => x._key !== e._key))} />
              </div>
            </div>
          ))}
          {experiences.length === 0 && (
            <p style={{ fontSize: 14, color: '#aaa', padding: '8px 0' }}>No experiences yet.</p>
          )}
        </div>
      </section>

      {/* ── Skills ───────────────────────────────────────── */}
      <section style={{ marginBottom: 40 }}>
        <h3 style={{ fontSize: 16, fontWeight: 700, color: '#111', marginBottom: 12 }}>Skills</h3>
        <textarea
          className="input textarea"
          placeholder="Python, React, PostgreSQL, Docker, FastAPI, AWS..."
          rows={3}
          value={skills}
          onChange={(e) => setSkills(e.target.value)}
        />
      </section>

      {/* ── Connected Accounts ───────────────────────────── */}
      <section style={{ marginBottom: 40 }}>
        <h3 style={{ fontSize: 16, fontWeight: 700, color: '#111', marginBottom: 4 }}>Connected Accounts</h3>
        <p style={{ fontSize: 13, color: '#888', marginBottom: 16 }}>
          Link an email account to scan your inbox for job leads and action items.
        </p>
        <div style={{
          border: '1px solid #e5e7eb',
          borderRadius: 10,
          overflow: 'hidden',
        }}>
          {/* Microsoft / Outlook row */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px 20px',
            background: '#fff',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              {/* Microsoft logo (SVG) */}
              <svg width="22" height="22" viewBox="0 0 22 22" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="0" y="0" width="10.5" height="10.5" fill="#F25022"/>
                <rect x="11.5" y="0" width="10.5" height="10.5" fill="#7FBA00"/>
                <rect x="0" y="11.5" width="10.5" height="10.5" fill="#00A4EF"/>
                <rect x="11.5" y="11.5" width="10.5" height="10.5" fill="#FFB900"/>
              </svg>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#111' }}>Microsoft / Outlook</div>
                {emailStatus?.connected ? (
                  <div style={{ fontSize: 12, color: '#16a34a', marginTop: 2 }}>
                    Connected · {emailStatus.email}
                  </div>
                ) : (
                  <div style={{ fontSize: 12, color: '#aaa', marginTop: 2 }}>Not connected</div>
                )}
              </div>
            </div>

            {emailStatus?.connected ? (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                background: '#f0fdf4',
                border: '1px solid #bbf7d0',
                borderRadius: 20,
                padding: '5px 14px',
                fontSize: 13,
                color: '#15803d',
                fontWeight: 500,
              }}>
                <span style={{ fontSize: 11 }}>●</span> Connected
              </div>
            ) : (
              <a
                href="http://localhost:8000/auth/login"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  background: '#111',
                  color: '#fff',
                  fontSize: 13,
                  fontWeight: 500,
                  padding: '7px 16px',
                  borderRadius: 7,
                  textDecoration: 'none',
                  transition: 'background 0.15s',
                }}
                onMouseEnter={e => e.currentTarget.style.background = '#333'}
                onMouseLeave={e => e.currentTarget.style.background = '#111'}
              >
                Connect
              </a>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
