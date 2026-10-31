import { useEffect, useMemo, useState } from 'react'
import { administrationApi, intelligenceReportsApi } from './api'
import './ReportsWorkspace.css'

const TASKING_INSTRUCTIONS = ['Process', 'Treat', 'Peruse', 'FNA', 'Collate', 'File', 'Update']

function ReportsWorkspace({ user }) {
  const role = String(user?.role || '').toLowerCase()
  const isManagement = role === 'management'
  const isAnalyst = role === 'analyst'
  const isAdmin = role === 'admin'
  const [reports, setReports] = useState([])
  const [work, setWork] = useState([])
  const [departments, setDepartments] = useState([])
  const [users, setUsers] = useState([])
  const [selected, setSelected] = useState(null)
  const [history, setHistory] = useState(null)
  const [taskHistory, setTaskHistory] = useState(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [showSubmit, setShowSubmit] = useState(false)
  const [rawText, setRawText] = useState('')
  const [title, setTitle] = useState('')
  const [location, setLocation] = useState('')
  const [lga, setLga] = useState('')
  const [stateName, setStateName] = useState('Borno')
  const [incidentDate, setIncidentDate] = useState('')
  const [incidentTime, setIncidentTime] = useState('')
  const [taskDepartment, setTaskDepartment] = useState('')
  const [instruction, setInstruction] = useState('Process')
  const [taskNote, setTaskNote] = useState('')
  const [heading, setHeading] = useState('')
  const [body, setBody] = useState('')
  const [comment, setComment] = useState('')
  const [newDepartment, setNewDepartment] = useState('')
  const [newDepartmentDescription, setNewDepartmentDescription] = useState('')
  const [assignUserId, setAssignUserId] = useState('')
  const [assignDepartmentId, setAssignDepartmentId] = useState('')

  async function loadWorkspace() {
    setLoading(true)
    setError('')
    try {
      if (isAnalyst) {
        const data = await intelligenceReportsApi.myWork()
        setWork(data.assigned_reports || [])
        setReports([])
      } else if (isAdmin) {
        const [deptData, userData] = await Promise.all([
          administrationApi.departments(), administrationApi.users(),
        ])
        setDepartments(Array.isArray(deptData) ? deptData : [])
        setUsers(Array.isArray(userData) ? userData : [])
      } else {
        const data = await intelligenceReportsApi.list()
        setReports(data.reports || [])
        if (isManagement) {
          const [deptData, taskData] = await Promise.all([
            administrationApi.departments(), intelligenceReportsApi.activeTaskings(),
          ])
          setDepartments(Array.isArray(deptData) ? deptData : [])
          setWork(taskData.active_taskings || [])
        }
      }
    } catch (err) {
      setError(err.message || 'Unable to load intelligence reports.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadWorkspace() }, [])

  async function openReport(id) {
    setError('')
    setNotice('')
    setHistory(null)
    setTaskHistory(null)
    try {
      const detail = await intelligenceReportsApi.get(id)
      setSelected(detail)
      setHeading(detail.heading || '')
      const [processingData, taskData] = await Promise.all([
        intelligenceReportsApi.processingHistory(id),
        isManagement ? intelligenceReportsApi.taskingHistory(id) : Promise.resolve(null),
      ])
      setHistory(processingData)
      setTaskHistory(taskData)
    } catch (err) {
      setError(err.message || 'Unable to open this report.')
    }
  }

  async function submitReport(event) {
    event.preventDefault()
    setSaving(true); setError(''); setNotice('')
    try {
      const result = await intelligenceReportsApi.submit({
        title: title.trim() || null,
        raw_text: rawText.trim(),
        location: location.trim() || null,
        lga: lga.trim() || null,
        state: stateName.trim() || null,
        incident_date: incidentDate || null,
        incident_time: incidentTime.trim() || null,
      })
      setNotice(`Report submitted successfully. Reference: ${result.report_reference}`)
      setShowSubmit(false); setRawText(''); setTitle(''); setLocation(''); setLga(''); setIncidentDate(''); setIncidentTime('')
      await loadWorkspace()
    } catch (err) { setError(err.message || 'Report submission failed.') }
    finally { setSaving(false) }
  }

  async function saveTasking(event) {
    event.preventDefault()
    if (!selected || !taskDepartment) return
    setSaving(true); setError(''); setNotice('')
    try {
      const payload = { department_id: Number(taskDepartment), instruction, tasking_note: taskNote.trim() || null }
      const active = taskHistory?.tasking_history?.some(item => item.is_active)
      const result = active
        ? await intelligenceReportsApi.reassign(selected.report_id, payload)
        : await intelligenceReportsApi.assign(selected.report_id, payload)
      setNotice(result.message || 'Departmental tasking saved.')
      setTaskNote('')
      await openReport(selected.report_id)
      await loadWorkspace()
    } catch (err) { setError(err.message || 'Unable to save departmental tasking.') }
    finally { setSaving(false) }
  }

  async function saveProcessing(event) {
    event.preventDefault()
    if (!selected) return
    setSaving(true); setError(''); setNotice('')
    try {
      const result = await intelligenceReportsApi.process(selected.report_id, { heading: heading.trim(), body: body.trim(), comment: comment.trim() || null })
      setNotice(result.message || 'Processing saved successfully.')
      setBody(''); setComment('')
      await openReport(selected.report_id)
      await loadWorkspace()
    } catch (err) { setError(err.message || 'Unable to save processing.') }
    finally { setSaving(false) }
  }

  async function approveReport() {
    if (!selected || !window.confirm('Approve this processed report as the official report?')) return
    setSaving(true); setError(''); setNotice('')
    try {
      const result = await intelligenceReportsApi.approve(selected.report_id)
      setNotice(result.message || 'Report approved successfully.')
      await openReport(selected.report_id); await loadWorkspace()
    } catch (err) { setError(err.message || 'Approval failed.') }
    finally { setSaving(false) }
  }

  async function createDepartment(event) {
    event.preventDefault(); setSaving(true); setError(''); setNotice('')
    try {
      await administrationApi.createDepartment({ name: newDepartment.trim(), description: newDepartmentDescription.trim() || null })
      setNewDepartment(''); setNewDepartmentDescription(''); setNotice('Department created successfully.'); await loadWorkspace()
    } catch (err) { setError(err.message || 'Unable to create department.') }
    finally { setSaving(false) }
  }

  async function assignAnalyst(event) {
    event.preventDefault(); setSaving(true); setError(''); setNotice('')
    try {
      await administrationApi.assignAnalystDepartment(Number(assignUserId), Number(assignDepartmentId))
      setNotice('Analyst department assignment saved.'); await loadWorkspace()
    } catch (err) { setError(err.message || 'Unable to assign department.') }
    finally { setSaving(false) }
  }

  const analystUsers = useMemo(() => users.filter(item => String(item.role).toLowerCase() === 'analyst'), [users])
  const list = isAnalyst ? work : reports

  return (
    <section className="panel report-workspace">
      <div className="report-workspace-head">
        <div><h2>{isAnalyst ? 'My Assigned Reports' : isAdmin ? 'Department Administration' : 'Intelligence Reports'}</h2>
          <p>{isAnalyst ? 'Reports currently assigned to your department.' : isAdmin ? 'Create departments and assign Analyst accounts.' : 'Submit, task, process and review intelligence reports.'}</p></div>
        <div className="report-actions">
          {!isAnalyst && !isAdmin && <button className="primary-button" onClick={() => setShowSubmit(v => !v)}>+ Submit Report</button>}
          <button className="secondary-button" onClick={loadWorkspace} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh'}</button>
        </div>
      </div>

      {error && <div className="report-alert error">{error}</div>}
      {notice && <div className="report-alert success">{notice}</div>}

      {isAdmin ? <div className="report-admin-grid">
        <form className="report-form" onSubmit={createDepartment}>
          <h3>Create Department</h3>
          <label>Department name</label><input value={newDepartment} onChange={e => setNewDepartment(e.target.value)} required minLength={2} maxLength={100}/>
          <label>Description</label><input value={newDepartmentDescription} onChange={e => setNewDepartmentDescription(e.target.value)} maxLength={255}/>
          <button className="primary-button" disabled={saving}>{saving ? 'Saving…' : 'Create Department'}</button>
        </form>
        <form className="report-form" onSubmit={assignAnalyst}>
          <h3>Assign Analyst to Department</h3>
          <label>Analyst account</label><select value={assignUserId} onChange={e => setAssignUserId(e.target.value)} required><option value="">Select Analyst</option>{analystUsers.map(item => <option key={item.user_id} value={item.user_id}>{item.username} (ID {item.user_id})</option>)}</select>
          <label>Department</label><select value={assignDepartmentId} onChange={e => setAssignDepartmentId(e.target.value)} required><option value="">Select department</option>{departments.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
          <button className="primary-button" disabled={saving}>{saving ? 'Saving…' : 'Save Assignment'}</button>
        </form>
        <div className="report-list-card"><h3>Active Departments</h3>{departments.map(item => <div className="report-list-row" key={item.id}><strong>{item.name}</strong><span>ID {item.id}</span></div>)}</div>
        <div className="report-list-card"><h3>Analyst Accounts</h3>{analystUsers.map(item => <div className="report-list-row" key={item.user_id}><strong>{item.username}</strong><span>{item.department || 'No department assigned'}</span></div>)}</div>
      </div> : <>
        {showSubmit && <form className="report-form report-submit-form" onSubmit={submitReport}>
          <div className="submission-heading">
            <div>
              <span className="submission-kicker">NEW SUBMISSION</span>
              <h3>Submit Intelligence Report</h3>
              <p>Enter the incident details and paste the original report. Management will review and assign it to the appropriate department.</p>
            </div>
            <span className="submission-step">Operative submission</span>
          </div>

          <div className="submission-section">
            <h4>1. Incident details</h4>
            <p className="submission-help">Provide the details available to you. Leave a field blank if the information is not yet known.</p>
            <div className="report-form-grid">
              <div><label htmlFor="report-title">Report title <span className="optional-label">Optional</span></label><input id="report-title" value={title} onChange={e => setTitle(e.target.value)} maxLength={255} placeholder="Brief description of the incident" /></div>
              <div><label htmlFor="incident-date">Incident date <span className="optional-label">Optional</span></label><input id="incident-date" type="date" value={incidentDate} onChange={e => setIncidentDate(e.target.value)} /></div>
              <div><label htmlFor="incident-time">Incident time <span className="optional-label">Optional</span></label><input id="incident-time" type="time" value={incidentTime} onChange={e => setIncidentTime(e.target.value)} /></div>
              <div><label htmlFor="incident-location">Location <span className="optional-label">Optional</span></label><input id="incident-location" value={location} onChange={e => setLocation(e.target.value)} placeholder="Village, town or specific location" /></div>
              <div><label htmlFor="incident-lga">LGA <span className="optional-label">Optional</span></label><input id="incident-lga" value={lga} onChange={e => setLga(e.target.value)} placeholder="Local Government Area" /></div>
              <div><label htmlFor="incident-state">State <span className="optional-label">Optional</span></label><input id="incident-state" value={stateName} onChange={e => setStateName(e.target.value)} placeholder="State" /></div>
            </div>
          </div>

          <div className="submission-section source-entry-section">
            <h4>2. Original report</h4>
            <p className="submission-help">Paste or type the report as received. Preserve the source information and do not add assumptions or unverified details.</p>
            <label htmlFor="raw-report-text">Raw intelligence report <span className="required-label">Required</span></label>
            <textarea id="raw-report-text" rows={9} minLength={10} required value={rawText} onChange={e => setRawText(e.target.value)} placeholder="Enter the original report here..." />
            <small className="submission-safety-note">Prototype reminder: use synthetic or declassified information only. Do not enter classified or live operational information.</small>
          </div>

          <div className="submission-footer">
            <span>Case reference and receiving department are not required at submission.</span>
            <div className="report-actions">
              <button className="primary-button" disabled={saving || rawText.trim().length < 10}>{saving ? 'Submitting…' : 'Submit Report'}</button>
              <button type="button" className="secondary-button" onClick={() => setShowSubmit(false)} disabled={saving}>Cancel</button>
            </div>
          </div>
        </form>}

        <div className="report-columns">
          <div className="report-list-card">
            <h3>{isAnalyst ? 'Department Tasking Queue' : isManagement ? 'All Submitted Reports' : 'My Submitted Reports'}</h3>
            {loading ? <p>Loading reports…</p> : list.length === 0 ? <p className="report-empty">No reports available.</p> : list.map(item => {
              const id = item.report_id
              return <button className={`report-list-item ${selected?.report_id === id ? 'selected' : ''}`} key={id} onClick={() => openReport(id)}>
                <span className="report-list-top"><strong>{item.report_reference || `Report ${id}`}</strong><span className={`report-status ${String(item.report_status || item.status || '').toLowerCase()}`}>{item.report_status || item.status || 'Submitted'}</span></span>
                <span>{item.heading || item.title || 'Untitled report'}</span>
                <small>{item.location || item.unit || 'Location not stated'} {item.lga ? `· ${item.lga}` : ''}</small>
                {isAnalyst && <small>Instruction: {item.instruction} · {item.tasking_note || 'No tasking note'}</small>}
              </button>
            })}
          </div>

          <div className="report-detail-card">
            {!selected ? <div className="report-empty-state"><strong>Select a report</strong><span>Report details and available actions will appear here.</span></div> : <>
              <div className="report-detail-head"><div><span className="report-reference">{selected.report_reference}</span><h3>{selected.heading || selected.title || 'Intelligence Report'}</h3></div><span className={`report-status ${String(selected.status).toLowerCase()}`}>{selected.status}</span></div>
              <div className="report-facts"><span><b>Location</b>{selected.location || 'Not stated'}</span><span><b>LGA</b>{selected.lga || 'Not stated'}</span><span><b>State</b>{selected.state || 'Not stated'}</span><span><b>Incident date</b>{selected.incident_date ? new Date(selected.incident_date).toLocaleDateString() : 'Not stated'}</span></div>
              <section className="report-source"><h4>Original Submission</h4><pre>{selected.raw_text || 'Original text is not available.'}</pre></section>

              {isManagement && <form className="report-form compact" onSubmit={saveTasking}><h4>Departmental Tasking</h4><label>Assign to department</label><select value={taskDepartment} onChange={e => setTaskDepartment(e.target.value)} required><option value="">Select department</option>{departments.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select><label>Tasking instruction</label><select value={instruction} onChange={e => setInstruction(e.target.value)}>{TASKING_INSTRUCTIONS.map(item => <option key={item}>{item}</option>)}</select><label>Tasking note</label><textarea rows={2} value={taskNote} onChange={e => setTaskNote(e.target.value)} placeholder="Management instruction or guidance"/><button className="primary-button" disabled={saving}>{saving ? 'Saving…' : taskHistory?.tasking_history?.some(item => item.is_active) ? 'Reassign Department' : 'Assign Department'}</button></form>}

              {isAnalyst && <form className="report-form compact" onSubmit={saveProcessing}><h4>Intelligence Processing</h4><label>Report heading</label><input value={heading} onChange={e => setHeading(e.target.value)} required minLength={3} maxLength={500}/><label>Processed report body</label><textarea rows={7} value={body} onChange={e => setBody(e.target.value)} required placeholder="Enter the processed intelligence report."/><label>Comment / Assessment</label><textarea rows={3} value={comment} onChange={e => setComment(e.target.value)} placeholder="Assessment and action taken, where applicable."/><button className="primary-button" disabled={saving}>{saving ? 'Saving…' : 'Save Processed Report'}</button></form>}

              {isManagement && selected.status === 'processed' && <div className="report-approve"><p>This report has been processed and is awaiting Management approval.</p><button className="primary-button" onClick={approveReport} disabled={saving}>{saving ? 'Approving…' : 'Approve Official Report'}</button></div>}
              {selected.status === 'approved' && <div className="report-alert success">This report has been approved by Management.</div>}

              <section className="report-history"><h4>Processing History</h4>{history?.original_submissions?.map((item, index) => <div className="history-entry" key={`raw-${index}`}><strong>Original submission {index + 1}</strong><pre>{item.raw_text}</pre></div>)}{history?.processing_history?.length ? history.processing_history.map(item => <div className="history-entry" key={item.processed_report_id}><strong>Processed version #{item.processed_report_id}</strong><p><b>Heading:</b> {item.heading}</p><p>{item.body}</p><p><b>Comment:</b> {item.comment || 'None'}</p><small>Processed by user ID {item.processed_by} · {item.processed_at ? new Date(item.processed_at).toLocaleString() : ''}</small></div>) : <p>No processing versions recorded yet.</p>}</section>
              {isManagement && taskHistory && <section className="report-history"><h4>Tasking History</h4>{taskHistory.tasking_history?.length ? taskHistory.tasking_history.map(item => <div className="history-entry" key={item.tasking_id}><strong>{item.unit} · {item.instruction}</strong><p>{item.tasking_note || 'No tasking note'}</p><small>{item.is_active ? 'Active assignment' : 'Previous assignment'} · {item.assigned_by}</small></div>) : <p>No departmental tasking recorded.</p>}</section>}
            </>}
          </div>
        </div>
        {isManagement && work.length > 0 && <div className="report-list-card report-active-taskings"><h3>Active Departmental Taskings</h3>{work.map(item => <div className="report-list-row" key={item.tasking_id}><strong>{item.report_reference}</strong><span>{item.unit} · {item.instruction}</span></div>)}</div>}
      </>}
    </section>
  )
}

export default ReportsWorkspace
