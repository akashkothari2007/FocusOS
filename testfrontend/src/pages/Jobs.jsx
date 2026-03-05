import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';

const BORDER_COLORS = ['#6366f1', '#ec4899', '#f59e0b', '#14b8a6'];

const STATUS_STYLE = {
  saved:     { bg: '#f5f5f7', color: '#666' },
  applied:   { bg: '#eff6ff', color: '#2563eb' },
  interview: { bg: '#f0fdf4', color: '#16a34a' },
  rejected:  { bg: '#fff1f2', color: '#dc2626' },
};

function formatDate(dt) {
  if (!dt) return '—';
  return new Date(dt).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  });
}

function parseSummary(summary) {
  if (!summary) return [];
  return summary
    .split('\n')
    .map((s) => s.replace(/^[•·\-*]\s*/, '').trim())
    .filter(Boolean);
}

function AnalysisIndicator({ status }) {
  if (!status || status === 'idle') return null;
  if (status === 'summarizing')
    return <span className="ai-status ai-status-pulse">✦ summarizing...</span>;
  if (status === 'analyzing')
    return <span className="ai-status ai-status-pulse">✦ analyzing...</span>;
  if (status === 'generating_resume')
    return <span className="ai-status ai-status-pulse">✦ generating resume...</span>;
  if (status === 'done')
    return <span className="ai-status ai-status-done">✓ analyzed</span>;
  if (status === 'error')
    return <span className="ai-status ai-status-error">✗ error</span>;
  return null;
}

function ScoreCircle({ score }) {
  const color = score >= 70 ? '#16a34a' : score >= 40 ? '#d97706' : '#dc2626';
  const bg    = score >= 70 ? '#f0fdf4' : score >= 40 ? '#fffbeb' : '#fff1f2';
  return (
    <div style={{
      width: 68, height: 68, borderRadius: '50%',
      background: bg, border: `3px solid ${color}`,
      display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
    }}>
      <span style={{ fontSize: 22, fontWeight: 700, color }}>{score}</span>
    </div>
  );
}

const EMPTY_FORM = { title: '', company: '', status: 'saved', link: '', description: '' };

export default function Jobs() {
  const [jobs, setJobs]                   = useState([]);
  const [expandedIds, setExpandedIds]     = useState([]);
  const [jobDetails, setJobDetails]       = useState({});
  const [showAddForm, setShowAddForm]     = useState(false);
  const [form, setForm]                   = useState(EMPTY_FORM);
  const [formLoading, setFormLoading]     = useState(false);
  const [formError, setFormError]         = useState(null);
  const [docs, setDocs]                   = useState([]);
  const [analyzePickerId, setAnalyzePickerId] = useState(null);
  const [selectedDocId, setSelectedDocId]    = useState('');
  const [actionLoading, setActionLoading]    = useState({});
  // planEdits[jobId] = { exp: { [idx]: bool }, proj: { [idx]: bool } }
  // true = apply swap, false = revert to keep
  const [planEdits, setPlanEdits]            = useState({});
  const pollingRef = useRef({});

  function initPlanEdits(jobId, suggestions) {
    if (!suggestions || Array.isArray(suggestions)) return;
    setPlanEdits((prev) => {
      if (prev[jobId]) return prev; // already initialized
      const exp = {}, proj = {};
      if (Array.isArray(suggestions.experiences)) {
        // New format: recommended=true → include, recommended=false → skip
        suggestions.experiences.forEach((e, idx) => { exp[idx] = e.recommended !== false; });
        (suggestions.projects || []).forEach((p, idx) => { proj[idx] = p.recommended !== false; });
      } else {
        // Old format: swap entries start as applied
        (suggestions.experience_plan || []).forEach((ep, idx) => { if (ep.action === 'swap') exp[idx] = true; });
        (suggestions.project_plan    || []).forEach((pp, idx) => { if (pp.action === 'swap') proj[idx] = true; });
      }
      return { ...prev, [jobId]: { exp, proj } };
    });
  }

  function togglePlanSwap(jobId, type, idx) {
    setPlanEdits((prev) => {
      const cur = prev[jobId] || { exp: {}, proj: {} };
      const section = type === 'exp' ? cur.exp : cur.proj;
      return { ...prev, [jobId]: { ...cur, [type]: { ...section, [idx]: !section[idx] } } };
    });
  }

  function buildEffectivePlan(jobId, suggestions) {
    if (!suggestions || Array.isArray(suggestions)) return {};
    const edits = planEdits[jobId] || { exp: {}, proj: {} };

    // New format: send selected_experiences / selected_projects
    if (Array.isArray(suggestions.experiences)) {
      const selected_experiences = (suggestions.experiences || [])
        .filter((_, idx) => edits.exp[idx] !== false)
        .map((e) => ({ role: e.role, company: e.company }));
      const selected_projects = (suggestions.projects || [])
        .filter((_, idx) => edits.proj[idx] !== false)
        .map((p) => ({ title: p.title }));
      return { selected_experiences, selected_projects };
    }

    // Old format: keep/swap plan
    const experience_plan = (suggestions.experience_plan || []).map((ep, idx) =>
      ep.action === 'swap' && edits.exp[idx] === false
        ? { action: 'keep', role: ep.remove_role, company: ep.remove_company,
            notes: ['Rewrite bullets to be stronger and more specific. Weave in relevant job keywords only where they genuinely and truthfully apply to the actual work done — do not invent or exaggerate.'] }
        : ep
    );
    const project_plan = (suggestions.project_plan || []).map((pp, idx) =>
      pp.action === 'swap' && edits.proj[idx] === false
        ? { action: 'keep', title: pp.remove,
            notes: ['Rewrite bullets to be stronger and more specific. Weave in relevant job keywords only where they genuinely and truthfully apply to the actual work done — do not invent or exaggerate.'] }
        : pp
    );
    return { experience_plan, project_plan };
  }

  // Initial load
  useEffect(() => {
    api.getJobs().then((data) => {
      setJobs(data.jobs);
      data.jobs.forEach((j) => {
        if (['summarizing', 'analyzing', 'generating_resume'].includes(j.analysis_status)) {
          startPolling(j.id);
        }
      });
    });
    return () => {
      Object.values(pollingRef.current).forEach(clearInterval);
    };
  }, []);

  function startPolling(jobId) {
    if (pollingRef.current[jobId]) return;
    const intervalId = setInterval(async () => {
      try {
        const detail = await api.getJob(jobId);
        setJobs((prev) =>
          prev.map((j) =>
            j.id === jobId
              ? { ...j, analysis_status: detail.analysis_status, summary: detail.summary, keywords: detail.keywords }
              : j
          )
        );
        setJobDetails((prev) => ({ ...prev, [jobId]: detail }));
        initPlanEdits(jobId, detail.suggestions);
        if (!['summarizing', 'analyzing', 'generating_resume'].includes(detail.analysis_status)) {
          clearInterval(pollingRef.current[jobId]);
          delete pollingRef.current[jobId];
        }
      } catch {
        // Network error — keep polling
      }
    }, 3000);
    pollingRef.current[jobId] = intervalId;
  }

  async function toggleExpand(jobId) {
    if (expandedIds.includes(jobId)) {
      setExpandedIds((prev) => prev.filter((id) => id !== jobId));
    } else {
      setExpandedIds((prev) => [...prev, jobId]);
      if (!jobDetails[jobId]) {
        const detail = await api.getJob(jobId);
        setJobDetails((prev) => ({ ...prev, [jobId]: detail }));
        initPlanEdits(jobId, detail.suggestions);
      }
    }
  }

  async function handleStatusChange(jobId, status) {
    const updated = await api.updateJob(jobId, { status });
    setJobs((prev) => prev.map((j) => (j.id === jobId ? { ...j, status: updated.status } : j)));
    setJobDetails((prev) =>
      prev[jobId] ? { ...prev, [jobId]: { ...prev[jobId], status: updated.status } } : prev
    );
  }

  async function handleDelete(jobId) {
    if (!window.confirm('Delete this job?')) return;
    await api.deleteJob(jobId);
    clearInterval(pollingRef.current[jobId]);
    delete pollingRef.current[jobId];
    setJobs((prev) => prev.filter((j) => j.id !== jobId));
    setExpandedIds((prev) => prev.filter((id) => id !== jobId));
    setJobDetails((prev) => { const n = { ...prev }; delete n[jobId]; return n; });
    if (analyzePickerId === jobId) setAnalyzePickerId(null);
  }

  async function handleAddJob(e) {
    e.preventDefault();
    setFormLoading(true);
    setFormError(null);
    try {
      const payload = {
        title: form.title.trim(),
        company: form.company.trim(),
        status: form.status,
        ...(form.link.trim()        && { link: form.link.trim() }),
        ...(form.description.trim() && { description: form.description.trim() }),
      };
      const job = await api.createJob(payload);
      setJobs((prev) => [job, ...prev]);
      setShowAddForm(false);
      setForm(EMPTY_FORM);
      if (['summarizing', 'analyzing'].includes(job.analysis_status)) {
        startPolling(job.id);
      }
    } catch (err) {
      setFormError(err.message);
    } finally {
      setFormLoading(false);
    }
  }

  async function openAnalyzePicker(jobId) {
    if (docs.length === 0) {
      const data = await api.getDocs();
      setDocs(data.docs);
    }
    setSelectedDocId('');
    setAnalyzePickerId(jobId);
  }

  async function handleGenerateResume(jobId) {
    setActionLoading((prev) => ({ ...prev, [`resume_${jobId}`]: true }));
    try {
      const detail = jobDetails[jobId];
      const plan = buildEffectivePlan(jobId, detail?.suggestions);
      await api.generateResume(jobId, plan);
      setJobs((prev) =>
        prev.map((j) => (j.id === jobId ? { ...j, analysis_status: 'generating_resume' } : j))
      );
      startPolling(jobId);
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading((prev) => ({ ...prev, [`resume_${jobId}`]: false }));
    }
  }

  async function handleRunAnalysis(jobId) {
    if (!selectedDocId) return;
    setActionLoading((prev) => ({ ...prev, [jobId]: true }));
    try {
      await api.analyzeJob(jobId, parseInt(selectedDocId));
      // Optimistically mark analyzing so the badge shows immediately
      setJobs((prev) =>
        prev.map((j) => (j.id === jobId ? { ...j, analysis_status: 'analyzing' } : j))
      );
      const detail = await api.getJob(jobId);
      setJobDetails((prev) => ({
        ...prev,
        [jobId]: { ...detail, analysis_status: 'analyzing' },
      }));
      setPlanEdits((prev) => { const n = { ...prev }; delete n[jobId]; return n; });
      setAnalyzePickerId(null);
      startPolling(jobId);
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading((prev) => ({ ...prev, [jobId]: false }));
    }
  }

  return (
    <div className="page">
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h2 className="page-title">Job Portal</h2>
        <button
          className="btn btn-primary"
          onClick={() => { setShowAddForm((v) => !v); setFormError(null); }}
        >
          {showAddForm ? 'Cancel' : '+ Add Job'}
        </button>
      </div>

      {/* Add job form */}
      {showAddForm && (
        <form className="add-form" onSubmit={handleAddJob}>
          <div className="add-form-row">
            <input
              className="input"
              placeholder="Title *"
              required
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
            />
            <input
              className="input"
              placeholder="Company *"
              required
              value={form.company}
              onChange={(e) => setForm((f) => ({ ...f, company: e.target.value }))}
            />
          </div>
          <div className="add-form-row">
            <input
              className="input"
              placeholder="Link (optional)"
              value={form.link}
              onChange={(e) => setForm((f) => ({ ...f, link: e.target.value }))}
            />
            <select
              className="input select"
              value={form.status}
              onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}
            >
              <option value="saved">Saved</option>
              <option value="applied">Applied</option>
              <option value="interview">Interview</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>
          <textarea
            className="input textarea"
            placeholder="Job description — paste the full JD here for an AI summary (optional)"
            rows={5}
            value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
          />
          {formError && <p style={{ color: '#dc2626', fontSize: 13 }}>{formError}</p>}
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button className="btn btn-primary" type="submit" disabled={formLoading}>
              {formLoading ? '...' : 'Save Job'}
            </button>
          </div>
        </form>
      )}

      {/* Job list */}
      <div className="todo-list">
        {jobs.map((job, i) => {
          const isExpanded  = expandedIds.includes(job.id);
          const detail      = jobDetails[job.id];
          const ss          = STATUS_STYLE[job.status] || STATUS_STYLE.saved;
          const isAiActive  = ['summarizing', 'analyzing', 'generating_resume'].includes(job.analysis_status);

          return (
            <div
              key={job.id}
              className="todo-card"
              style={{ borderLeftColor: BORDER_COLORS[i % BORDER_COLORS.length] }}
            >
              {/* Card header */}
              <div className="todo-card-header" onClick={() => toggleExpand(job.id)}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="todo-card-title-row">
                    <span className="todo-title">{job.title}</span>
                    <span style={{
                      fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 6,
                      background: ss.bg, color: ss.color, flexShrink: 0,
                    }}>
                      {job.status}
                    </span>
                    <AnalysisIndicator status={job.analysis_status} />
                  </div>
                  <div style={{ fontSize: 13, color: '#888', marginTop: 3 }}>
                    {job.company} · {formatDate(job.created_at)}
                  </div>
                </div>
                <span style={{ fontSize: 11, color: '#ccc', marginLeft: 10, flexShrink: 0 }}>
                  {isExpanded ? '▲' : '▼'}
                </span>
              </div>

              {/* Expanded body */}
              {isExpanded && (
                <div className="todo-card-body">

                  {/* Link */}
                  {(detail?.link) && (
                    <a
                      href={detail.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ fontSize: 13, color: '#6366f1', wordBreak: 'break-all' }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      {detail.link} ↗
                    </a>
                  )}

                  {/* Description */}
                  {detail?.description && (
                    <div>
                      <p style={{ fontSize: 11, fontWeight: 600, color: '#aaa', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                        Description
                      </p>
                      <p style={{ fontSize: 13, color: '#555', whiteSpace: 'pre-wrap', lineHeight: 1.6, maxHeight: 180, overflowY: 'auto' }}>
                        {detail.description}
                      </p>
                    </div>
                  )}

                  {/* AI Summary */}
                  {(detail?.summary || job.summary) && (
                    <div style={{ background: '#f8f8ff', border: '1px solid #e8e8ff', borderRadius: 10, padding: '12px 14px' }}>
                      <p style={{ fontSize: 11, fontWeight: 600, color: '#6366f1', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                        AI Summary
                      </p>
                      <ul style={{ paddingLeft: 16, display: 'flex', flexDirection: 'column', gap: 4 }}>
                        {parseSummary(detail?.summary || job.summary).map((line, idx) => (
                          <li key={idx} style={{ fontSize: 13, color: '#444', lineHeight: 1.5 }}>{line}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Keywords — available as soon as first AI call completes */}
                  {(detail?.keywords?.length > 0 || job.keywords?.length > 0) && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {(detail?.keywords || job.keywords).map((kw, idx) => (
                        <span key={idx} style={{
                          fontSize: 12, padding: '3px 10px', borderRadius: 20,
                          background: '#eef0ff', color: '#6366f1',
                        }}>
                          {kw}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Status edit */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: 13, color: '#888', flexShrink: 0 }}>Status:</span>
                    <select
                      className="input select"
                      style={{ width: 'auto' }}
                      value={detail?.status || job.status}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => handleStatusChange(job.id, e.target.value)}
                    >
                      <option value="saved">Saved</option>
                      <option value="applied">Applied</option>
                      <option value="interview">Interview</option>
                      <option value="rejected">Rejected</option>
                    </select>
                  </div>

                  {/* Analysis section */}
                  <div style={{ borderTop: '1px solid #f0f0f2', paddingTop: 14 }}>
                    <p style={{ fontSize: 11, fontWeight: 600, color: '#aaa', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                      Analysis
                    </p>

                    {detail?.match_score != null ? (
                      /* Analysis row exists */
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                          <ScoreCircle score={detail.match_score} />
                          <div>
                            <p style={{ fontSize: 14, fontWeight: 600, color: '#333' }}>Match score</p>
                            {detail.input_doc_id && (
                              <p style={{ fontSize: 12, color: '#aaa', marginTop: 2 }}>
                                Doc #{detail.input_doc_id}
                                {detail.analysis_updated_at && ` · updated ${formatDate(detail.analysis_updated_at)}`}
                              </p>
                            )}
                          </div>
                        </div>

                        {detail.suggestions && (
                          <SuggestionsPanel
                            suggestions={detail.suggestions}
                            edits={planEdits[job.id] || { exp: {}, proj: {} }}
                            onToggle={(type, idx) => togglePlanSwap(job.id, type, idx)}
                          />
                        )}

                        {/* Re-run (disabled while AI is active) */}
                        {!isAiActive && (
                          analyzePickerId === job.id ? (
                            <DocPicker
                              docs={docs}
                              selectedDocId={selectedDocId}
                              setSelectedDocId={setSelectedDocId}
                              loading={actionLoading[job.id]}
                              onRun={() => handleRunAnalysis(job.id)}
                              onCancel={() => setAnalyzePickerId(null)}
                              label="Run"
                            />
                          ) : (
                            <button
                              className="btn"
                              style={{ background: '#f5f5f7', color: '#555', alignSelf: 'flex-start' }}
                              onClick={() => openAnalyzePicker(job.id)}
                            >
                              Re-run Analysis
                            </button>
                          )
                        )}
                      </div>
                    ) : isAiActive ? (
                      /* No row yet but AI is running */
                      <p style={{ fontSize: 13, color: '#9ca3af' }}>Analysis in progress...</p>
                    ) : (
                      /* No analysis at all */
                      analyzePickerId === job.id ? (
                        <DocPicker
                          docs={docs}
                          selectedDocId={selectedDocId}
                          setSelectedDocId={setSelectedDocId}
                          loading={actionLoading[job.id]}
                          onRun={() => handleRunAnalysis(job.id)}
                          onCancel={() => setAnalyzePickerId(null)}
                          label="Analyze"
                        />
                      ) : (
                        <button className="btn btn-primary" onClick={() => openAnalyzePicker(job.id)}>
                          Run Analysis
                        </button>
                      )
                    )}
                  </div>

                  {/* Tailored resume section — visible once analysis exists */}
                  {detail?.match_score != null && (
                    <div style={{ borderTop: '1px solid #f0f0f2', paddingTop: 14 }}>
                      <p style={{ fontSize: 11, fontWeight: 600, color: '#aaa', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                        Tailored Resume
                      </p>

                      {job.analysis_status === 'generating_resume' ? (
                        <span className="ai-status ai-status-pulse">✦ generating resume...</span>
                      ) : detail?.output_doc_id ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                          <Link
                            to={`/docs?highlight=${detail.output_doc_id}`}
                            style={{ fontSize: 13, color: '#6366f1', fontWeight: 500 }}
                            onClick={(e) => e.stopPropagation()}
                          >
                            View Resume ↗
                          </Link>
                          <button
                            className="btn"
                            style={{ background: '#f5f5f7', color: '#555' }}
                            disabled={actionLoading[`resume_${job.id}`]}
                            onClick={() => handleGenerateResume(job.id)}
                          >
                            {actionLoading[`resume_${job.id}`] ? '...' : 'Regenerate'}
                          </button>
                        </div>
                      ) : job.analysis_status === 'done' ? (
                        <button
                          className="btn btn-primary"
                          disabled={actionLoading[`resume_${job.id}`]}
                          onClick={() => handleGenerateResume(job.id)}
                        >
                          {actionLoading[`resume_${job.id}`] ? '...' : 'Generate Resume'}
                        </button>
                      ) : null}
                    </div>
                  )}

                  {/* Delete */}
                  <div className="todo-card-footer">
                    <button
                      className="btn"
                      style={{ background: '#fff1f2', color: '#dc2626', fontSize: 13, padding: '6px 14px', borderRadius: 8 }}
                      onClick={() => handleDelete(job.id)}
                    >
                      Delete Job
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {jobs.length === 0 && (
          <p className="empty-state">No jobs yet. Add one above.</p>
        )}
      </div>
    </div>
  );
}

function ItemRow({ included, onToggle, label, notes }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', gap: 10,
      background: included ? '#fafafa' : '#f5f5f5',
      border: `1px solid ${included ? '#e0e7ff' : '#e5e7eb'}`,
      borderRadius: 8, padding: '7px 12px',
      opacity: included ? 1 : 0.65,
    }}>
      <button
        onClick={onToggle}
        style={{
          flexShrink: 0, marginTop: 1, fontSize: 10, fontWeight: 700,
          padding: '2px 7px', borderRadius: 4, border: 'none', cursor: 'pointer',
          background: included ? '#f0fdf4' : '#f3f4f6',
          color: included ? '#16a34a' : '#9ca3af',
        }}
      >
        {included ? 'KEEP' : 'SKIP'}
      </button>
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontSize: 12, fontWeight: 500, color: included ? '#333' : '#777' }}>{label}</p>
        {notes && (
          <p style={{ fontSize: 11, color: '#777', lineHeight: 1.4, marginTop: 2 }}>{notes}</p>
        )}
      </div>
    </div>
  );
}

function SuggestionsPanel({ suggestions, edits = { exp: {}, proj: {} }, onToggle }) {
  // Backward compat: old flat array format
  if (Array.isArray(suggestions)) {
    if (suggestions.length === 0) return null;
    return (
      <div>
        <p style={{ fontSize: 11, fontWeight: 600, color: '#aaa', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Suggestions</p>
        <ol style={{ paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 5 }}>
          {suggestions.map((s, idx) => (
            <li key={idx} style={{ fontSize: 13, color: '#444', lineHeight: 1.5 }}>{s}</li>
          ))}
        </ol>
      </div>
    );
  }

  const { overall } = suggestions;

  // New format: flat experiences/projects arrays
  if (Array.isArray(suggestions.experiences) || Array.isArray(suggestions.projects)) {
    const experiences = suggestions.experiences || [];
    const projects = suggestions.projects || [];
    const selExpCount = experiences.filter((_, idx) => edits.exp[idx] !== false).length;
    const selProjCount = projects.filter((_, idx) => edits.proj[idx] !== false).length;

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {overall && (
          <p style={{ fontSize: 13, color: '#555', lineHeight: 1.55, borderLeft: '3px solid #6366f1', paddingLeft: 10, fontStyle: 'italic' }}>
            {overall}
          </p>
        )}

        {experiences.length > 0 && (
          <div>
            <p style={{ fontSize: 11, fontWeight: 600, color: '#aaa', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Experiences{' '}
              <span style={{ color: '#6366f1', textTransform: 'none', letterSpacing: 0 }}>
                ({selExpCount}/{experiences.length} selected)
              </span>
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {experiences.map((exp, idx) => {
                const included = edits.exp[idx] !== false;
                return (
                  <ItemRow
                    key={idx}
                    included={included}
                    onToggle={() => onToggle?.('exp', idx)}
                    label={<>{exp.role} <span style={{ fontWeight: 400, color: '#888' }}>@ {exp.company}</span></>}
                    notes={exp.notes}
                  />
                );
              })}
            </div>
          </div>
        )}

        {projects.length > 0 && (
          <div>
            <p style={{ fontSize: 11, fontWeight: 600, color: '#aaa', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Projects{' '}
              <span style={{ color: '#6366f1', textTransform: 'none', letterSpacing: 0 }}>
                ({selProjCount}/{projects.length} selected)
              </span>
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              {projects.map((proj, idx) => {
                const included = edits.proj[idx] !== false;
                return (
                  <ItemRow
                    key={idx}
                    included={included}
                    onToggle={() => onToggle?.('proj', idx)}
                    label={proj.title}
                    notes={proj.notes}
                  />
                );
              })}
            </div>
          </div>
        )}
      </div>
    );
  }

  // Old format: experience_plan/project_plan
  const { experience_plan, experience_notes = [], project_plan = [] } = suggestions;
  const expPlan = experience_plan || (experience_notes.length > 0
    ? experience_notes.map(en => ({ action: 'keep', role: en.role, company: en.company, notes: en.notes }))
    : []);
  if (!overall && expPlan.length === 0 && project_plan.length === 0) return null;

  function PlanRow({ item, type, idx, isSwap, applied }) {
    const toggled = isSwap && applied === false;
    return (
      <div style={{
        display: 'flex', alignItems: 'flex-start', gap: 10,
        background: toggled ? '#f9f9f9' : '#fafafa',
        border: `1px solid ${toggled ? '#e5e7eb' : '#f0f0f2'}`,
        borderRadius: 8, padding: '7px 12px',
        opacity: toggled ? 0.6 : 1,
      }}>
        {isSwap ? (
          <button
            onClick={() => onToggle?.(type, idx)}
            style={{
              flexShrink: 0, marginTop: 1, fontSize: 10, fontWeight: 700,
              padding: '2px 7px', borderRadius: 4, border: 'none', cursor: 'pointer',
              background: applied === false ? '#f3f4f6' : '#fff7ed',
              color: applied === false ? '#9ca3af' : '#c2410c',
            }}
          >
            {applied === false ? 'SKIP' : 'SWAP'}
          </button>
        ) : (
          <span style={{
            fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 4, flexShrink: 0, marginTop: 1,
            background: '#f0fdf4', color: '#16a34a',
          }}>
            KEEP
          </span>
        )}
        <div style={{ flex: 1, minWidth: 0 }}>
          {isSwap ? (
            <p style={{ fontSize: 12, color: '#555' }}>
              {type === 'exp' ? (
                <>
                  <span style={{ textDecoration: toggled ? 'none' : 'line-through', color: '#bbb' }}>{item.remove_role} @ {item.remove_company}</span>
                  {!toggled && <>{' → '}<span style={{ fontWeight: 600, color: '#333' }}>{item.add_role} @ {item.add_company}</span></>}
                  {toggled && <span style={{ color: '#6b7280', marginLeft: 6 }}>(keeping {item.remove_role})</span>}
                </>
              ) : (
                <>
                  <span style={{ textDecoration: toggled ? 'none' : 'line-through', color: '#bbb' }}>{item.remove}</span>
                  {!toggled && <>{' → '}<span style={{ fontWeight: 600, color: '#333' }}>{item.add}</span></>}
                  {toggled && <span style={{ color: '#6b7280', marginLeft: 6 }}>(keeping {item.remove})</span>}
                </>
              )}
            </p>
          ) : (
            <p style={{ fontSize: 12, fontWeight: 500, color: '#333' }}>
              {type === 'exp'
                ? <>{item.role} <span style={{ fontWeight: 400, color: '#888' }}>@ {item.company}</span></>
                : item.title}
            </p>
          )}
          {item.notes?.length > 0 && (
            <ul style={{ paddingLeft: 12, marginTop: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
              {item.notes.map((n, ni) => (
                <li key={ni} style={{ fontSize: 11, color: '#777', lineHeight: 1.4 }}>{n}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {overall && (
        <p style={{ fontSize: 13, color: '#555', lineHeight: 1.55, borderLeft: '3px solid #6366f1', paddingLeft: 10, fontStyle: 'italic' }}>
          {overall}
        </p>
      )}

      {expPlan.length > 0 && (
        <div>
          <p style={{ fontSize: 11, fontWeight: 600, color: '#aaa', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Experience Plan</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {expPlan.map((ep, idx) => (
              <PlanRow key={idx} item={ep} type="exp" idx={idx}
                isSwap={ep.action === 'swap'} applied={edits.exp[idx]} />
            ))}
          </div>
        </div>
      )}

      {project_plan.length > 0 && (
        <div>
          <p style={{ fontSize: 11, fontWeight: 600, color: '#aaa', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Project Plan</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            {project_plan.map((p, idx) => (
              <PlanRow key={idx} item={p} type="proj" idx={idx}
                isSwap={p.action === 'swap'} applied={edits.proj[idx]} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Small reusable doc picker used for both "Run" and "Re-run"
function DocPicker({ docs, selectedDocId, setSelectedDocId, loading, onRun, onCancel, label }) {
  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
      <select
        className="input select"
        value={selectedDocId}
        onChange={(e) => setSelectedDocId(e.target.value)}
      >
        <option value="">Select doc...</option>
        {docs.map((d) => (
          <option key={d.id} value={d.id}>
            {d.title}{d.is_primary ? ' ★' : ''}
          </option>
        ))}
      </select>
      <button
        className="btn btn-primary"
        disabled={!selectedDocId || loading}
        onClick={onRun}
      >
        {loading ? '...' : label}
      </button>
      <button
        className="btn"
        style={{ background: '#f5f5f7', color: '#555' }}
        onClick={onCancel}
      >
        Cancel
      </button>
    </div>
  );
}
