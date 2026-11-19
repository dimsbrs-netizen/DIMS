import { useEffect, useState } from 'react'
import { adminDashboardApi } from './api'

export default function AuditLogs() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function load() {
    setLoading(true)
    setError('')
    try {
      const result = await adminDashboardApi.auditLogs()
      setLogs(result.audit_logs || [])
    } catch (err) {
      setError(err.message || 'Unable to retrieve audit logs.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  return <section className="panel audit-page">
    <div className="panel-heading">
      <div><h2>Audit Logs</h2><p>Recorded user activity and changes across DIMS.</p></div>
      <button className="secondary-button" onClick={load} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh'}</button>
    </div>
    <div className="ai-safety-notice"><strong>Audit record integrity</strong><p>Entries are retrieved from the DIMS backend. This page does not create or modify audit records.</p></div>
    {error && <div className="report-alert error">{error}</div>}
    {loading && !logs.length ? <p>Loading audit records…</p> : !logs.length ? <p>No audit records are available.</p> : <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Date and time</th><th>User</th><th>Action</th><th>Entity</th><th>Record ID</th><th>Details</th></tr></thead><tbody>
      {logs.map(log => <tr key={log.id}><td>{log.created_at ? new Date(log.created_at).toLocaleString() : 'Not recorded'}</td><td>{log.actor_username || 'System'}</td><td><strong>{log.action}</strong></td><td>{log.entity_type || '—'}</td><td>{log.entity_id ?? '—'}</td><td>{log.details || '—'}</td></tr>)}
    </tbody></table></div>}
    <p className="submission-help">Showing the latest {logs.length} records returned by the server.</p>
  </section>
}
