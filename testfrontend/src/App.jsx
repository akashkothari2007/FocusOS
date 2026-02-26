import { useState, useEffect } from 'react'

const API = '/api'

const STATUS_OPTIONS = ['saved', 'in progress', 'applied', 'interview', 'rejected']

function App() {
  const [jobs, setJobs] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [company, setCompany] = useState('')
  const [title, setTitle] = useState('')
  const [link, setLink] = useState('')
  const [description, setDescription] = useState('')
  const [loading, setLoading] = useState(false)

  function loadJobs() {
    setLoading(true)
    fetch(`${API}/jobs`)
      .then((r) => r.json())
      .then(setJobs)
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadJobs()
  }, [])

  function handleCreate(e) {
    e.preventDefault()
    fetch(`${API}/jobs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ company, title, link: link || null, description: description || null, status: 'saved' }),
    })
      .then((r) => r.json())
      .then(() => {
        setCompany('')
        setTitle('')
        setLink('')
        setDescription('')
        setShowForm(false)
        loadJobs()
      })
      .catch(console.error)
  }

  function handleStatusChange(jobId, newStatus) {
    fetch(`${API}/jobs/${jobId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus }),
    })
      .then((r) => r.json())
      .then((updated) => {
        setJobs((prev) => prev.map((j) => (j.id === jobId ? { ...j, status: updated.status } : j)))
      })
      .catch(console.error)
  }

  function handleDelete(jobId) {
    fetch(`${API}/jobs/${jobId}`, { method: 'DELETE' })
      .then(() => setJobs((prev) => prev.filter((j) => j.id !== jobId)))
      .catch(console.error)
  }

  return (
    <div style={{ padding: 20, fontFamily: 'sans-serif' }}>
      <h1>Jobs (test)</h1>
      <button type="button" onClick={() => setShowForm((s) => !s)}>
        {showForm ? 'Cancel' : '+'} Add job
      </button>
      {showForm && (
        <form onSubmit={handleCreate} style={{ marginTop: 12, marginBottom: 20 }}>
          <div>
            <input placeholder="Company" value={company} onChange={(e) => setCompany(e.target.value)} required />
          </div>
          <div>
            <input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} required />
          </div>
          <div>
            <input placeholder="Link (optional)" value={link} onChange={(e) => setLink(e.target.value)} />
          </div>
          <div>
            <textarea placeholder="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} rows={3} style={{ width: 300 }} />
          </div>
          <button type="submit">Create</button>
        </form>
      )}
      {loading ? (
        <p>Loading...</p>
      ) : (
        <table border={1} cellPadding={8} cellSpacing={0} style={{ borderCollapse: 'collapse', marginTop: 12 }}>
          <thead>
            <tr>
              <th>ID</th>
              <th>Company</th>
              <th>Title</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id}>
                <td>{job.id}</td>
                <td>{job.company}</td>
                <td>{job.title}</td>
                <td>
                  <select
                    value={job.status}
                    onChange={(e) => handleStatusChange(job.id, e.target.value)}
                  >
                    {STATUS_OPTIONS.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </td>
                <td>
                  <button type="button" onClick={() => handleDelete(job.id)} title="Delete">🗑</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default App
