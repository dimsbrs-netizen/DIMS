import { useEffect, useState } from 'react'
import { adminDashboardApi } from './api'

const roles = ['operative', 'analyst', 'supervisor', 'management', 'admin']

export default function AdminDashboard({ user }) {
  const [users, setUsers] = useState([])
  const [departments, setDepartments] = useState([])
  const [summary, setSummary] = useState({})
  const [logs, setLogs] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [form, setForm] = useState({ username: '', password: '', role: 'operative', full_name: '', designation: '', formation: '', department_id: '' })
  const [departmentName, setDepartmentName] = useState('')
  const [departmentDescription, setDepartmentDescription] = useState('')

  async function load() {
    setBusy(true); setError('')
    try {
      const [u, d, s, a] = await Promise.all([adminDashboardApi.users(), adminDashboardApi.departments(), adminDashboardApi.summary(), adminDashboardApi.auditLogs()])
      setUsers(Array.isArray(u) ? u : []); setDepartments(Array.isArray(d) ? d : []); setSummary(s || {}); setLogs(a.audit_logs || [])
    } catch (e) { setError(e.message || 'Unable to load Admin Dashboard.') }
    finally { setBusy(false) }
  }
  useEffect(() => { load() }, [])
  const change = (key, value) => setForm(old => ({ ...old, [key]: value }))

  async function createUser(e) {
    e.preventDefault(); setBusy(true); setError(''); setNotice('')
    try {
      await adminDashboardApi.createUser({ ...form, department_id: form.department_id ? Number(form.department_id) : null })
      setForm({ username: '', password: '', role: 'operative', full_name: '', designation: '', formation: '', department_id: '' })
      setNotice('User account created. The new user must change the temporary password at first sign-in.'); await load()
    } catch (err) { setError(err.message || 'Unable to create user.') }
    finally { setBusy(false) }
  }
  async function createDepartment(e) {
    e.preventDefault(); setBusy(true); setError(''); setNotice('')
    try { await adminDashboardApi.createDepartment({ name: departmentName.trim(), description: departmentDescription.trim() || null }); setDepartmentName(''); setDepartmentDescription(''); setNotice('Department created successfully.'); await load() }
    catch (err) { setError(err.message || 'Unable to create department.') }
    finally { setBusy(false) }
  }
  async function editProfile(u) {
    const full_name = window.prompt('Full name:', u.full_name || '')
    if (full_name === null) return
    const designation = window.prompt('Official designation:', u.designation || '')
    if (designation === null) return
    const formation = window.prompt('Formation:', u.formation || '')
    if (formation === null) return
    await updateUser(u.user_id, { full_name, designation, formation }, 'User profile updated.')
  }
  async function resetPassword(u) {
    const temporary_password = window.prompt(`Enter a temporary password for ${u.username}. They must change it at next sign-in. Use at least 8 characters:`)
    if (temporary_password === null) return
    if (temporary_password.length < 8) { setError('Temporary password must contain at least 8 characters.'); return }
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await adminDashboardApi.resetPassword(u.user_id, temporary_password)
      setNotice(result.message || 'Password reset successfully.')
      await load()
    } catch (err) { setError(err.message || 'Unable to reset password.') }
    finally { setBusy(false) }
  }

  async function updateUser(id, data, message) {
    setBusy(true); setError(''); setNotice('')
    try { if (data.role) await adminDashboardApi.updateRole(id, data.role); else if (data.is_active !== undefined) await adminDashboardApi.updateStatus(id, data.is_active); else await adminDashboardApi.updateUser(id, data); setNotice(message); await load() }
    catch (err) { setError(err.message || 'Unable to update user.') }
    finally { setBusy(false) }
  }

  return <section className="panel admin-dashboard">
    <div className="panel-heading"><div><h2>Admin Dashboard</h2><p>Manage test accounts, system roles, departments and account activity.</p></div><button className="secondary-button" onClick={load} disabled={busy}>{busy ? 'Refreshing…' : 'Refresh'}</button></div>
    <div className="ai-safety-notice"><strong>Prototype data only</strong><p>Use synthetic or declassified information. Do not enter classified or live operational information.</p></div>
    {error && <div className="report-alert error">{error}</div>}{notice && <div className="report-alert success">{notice}</div>}
    <div className="admin-metrics"><div><small>Total accounts</small><strong>{summary.users ?? '—'}</strong></div><div><small>Active accounts</small><strong>{summary.active_users ?? '—'}</strong></div><div><small>Departments</small><strong>{summary.departments ?? '—'}</strong></div><div><small>Unassigned analysts</small><strong>{summary.analysts_unassigned ?? '—'}</strong></div></div>
    <div className="admin-grid">
      <form className="report-form" onSubmit={createUser}><h3>Create User Account</h3>
        <label>Username</label><input required minLength={3} value={form.username} onChange={e => change('username', e.target.value)} />
        <label>Temporary password</label><input type="password" required minLength={8} value={form.password} onChange={e => change('password', e.target.value)} />
        <label>System role</label><select value={form.role} onChange={e => change('role', e.target.value)}>{roles.map(r => <option key={r} value={r}>{r}</option>)}</select>
        <label>Full name</label><input value={form.full_name} onChange={e => change('full_name', e.target.value)} />
        <label>Official designation</label><input value={form.designation} onChange={e => change('designation', e.target.value)} placeholder="e.g. Assistant Director" />
        <label>Formation</label><input value={form.formation} onChange={e => change('formation', e.target.value)} placeholder="Department / Formation" />
        {form.role === 'analyst' && <><label>Department</label><select required value={form.department_id} onChange={e => change('department_id', e.target.value)}><option value="">Select department</option>{departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select></>}
        <button className="primary-button" disabled={busy}>{busy ? 'Saving…' : 'Create Account'}</button>
      </form>
      <form className="report-form" onSubmit={createDepartment}><h3>Create Department</h3><label>Department name</label><input required minLength={2} value={departmentName} onChange={e => setDepartmentName(e.target.value)} /><label>Description</label><input value={departmentDescription} onChange={e => setDepartmentDescription(e.target.value)} /><button className="primary-button" disabled={busy}>Create Department</button>
        <h3 className="admin-subheading">Active Departments</h3>{departments.map(d => <div className="report-list-row" key={d.id}><strong>{d.name}</strong><span>ID {d.id}</span></div>)}
      </form>
    </div>
    <div className="report-list-card admin-users"><div className="panel-heading"><div><h3>User Accounts</h3><p>Update roles, account status and analyst department assignment.</p></div></div>
      <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Account</th><th>Role</th><th>Designation / Formation</th><th>Department</th><th>Status</th><th>Actions</th></tr></thead><tbody>{users.map(u => <tr key={u.user_id}><td><strong>{u.full_name || u.username}</strong><small>{u.username} · ID {u.user_id}</small></td><td><select value={u.role} disabled={busy || u.user_id === user?.user_id} onChange={e => updateUser(u.user_id, { role: e.target.value }, 'User role updated.')}>{roles.map(r => <option key={r}>{r}</option>)}</select></td><td>{u.designation || 'Not set'}<small>{u.formation || ''}</small></td><td>{u.role === 'analyst' ? <select value={u.department_id || ''} disabled={busy} onChange={e => updateUser(u.user_id, { department_id: Number(e.target.value) }, 'Analyst department updated.')}><option value="">Unassigned</option>{departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select> : (u.department || '—')}</td><td><span className={`report-status ${u.is_active ? 'approved' : 'discarded'}`}>{u.is_active ? 'Active' : 'Inactive'}</span></td><td><button className="secondary-button" disabled={busy || u.user_id === user?.user_id} onClick={() => editProfile(u)}>Edit</button> <button className="secondary-button" disabled={busy || u.user_id === user?.user_id} onClick={() => resetPassword(u)}>Reset password</button> <button className="secondary-button" disabled={busy || u.user_id === user?.user_id} onClick={() => updateUser(u.user_id, { is_active: !u.is_active }, `Account ${u.is_active ? 'deactivated' : 'activated'}.`)}>{u.is_active ? 'Deactivate' : 'Activate'}</button></td></tr>)}</tbody></table></div>
    </div>
    <div className="report-list-card"><h3>Recent Administrative Activity</h3>{logs.slice(0, 15).map(log => <div className="report-list-row" key={log.id}><strong>{log.action}</strong><span>{log.actor_username} · {log.created_at ? new Date(log.created_at).toLocaleString() : ''}</span></div>)}{!logs.length && <p>No administrative activity recorded yet.</p>}</div>
  </section>
}
