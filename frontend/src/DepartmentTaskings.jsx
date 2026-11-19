import { useEffect, useState } from 'react'
import { intelligenceReportsApi } from './api'

export default function DepartmentTaskings() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function load() {
    setLoading(true)
    setError('')
    try {
      const result = await intelligenceReportsApi.activeTaskings()
      setItems(result.active_taskings || [])
    } catch (err) {
      setError(err.message || 'Unable to retrieve departmental taskings.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  return <section className="panel department-taskings-page">
    <div className="panel-heading">
      <div><h2>Departmental Taskings</h2><p>Reports currently assigned to departments for action.</p></div>
      <button className="secondary-button" onClick={load} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh'}</button>
    </div>
    {error && <div className="report-alert error">{error}</div>}
    <div className="admin-metrics"><div><small>Active taskings</small><strong>{items.length}</strong></div></div>
    {loading && !items.length ? <p>Loading taskings…</p> : !items.length ? <p>No active departmental taskings.</p> : <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Report reference</th><th>Report heading</th><th>Department</th><th>Instruction</th><th>Management note</th><th>Assigned by</th><th>Date assigned</th></tr></thead><tbody>
      {items.map(item => <tr key={item.tasking_id}><td><strong>{item.report_reference}</strong></td><td>{item.report_heading || 'Title not yet processed'}</td><td>{item.unit || 'Not stated'}</td><td><span className="report-status processed">{item.instruction}</span></td><td>{item.tasking_note || 'No note'}</td><td>{item.assigned_by || 'Not recorded'}</td><td>{item.assigned_at ? new Date(item.assigned_at).toLocaleString() : 'Not recorded'}</td></tr>)}
    </tbody></table></div>}
  </section>
}
