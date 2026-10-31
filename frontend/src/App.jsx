
import { useEffect, useState } from 'react'
import './App.css'
import { authApi, casesApi, investigationsApi, aiApi, learningReferencesApi } from './api'
import Login from './Login'
import ReportsWorkspace from './ReportsWorkspace'

const navigation = [
  {
    section: 'WORKSPACE', items: [
      { label: 'Dashboard', icon: '▦' },
      { label: 'Cases', icon: '▤' },
      { label: 'Investigation Management', icon: '▧' },
      { label: 'Intelligence Processing Agent', icon: '✦' },
      { label: 'Intelligence Reports', icon: '◈' },
      { label: 'Tasking & Operations', icon: '⇄' },
      { label: 'Learning References', icon: '📚' },
    ]
  },
  {
    section: 'MANAGEMENT', items: [
      { label: 'Departments', icon: '▥' },
      { label: 'Users & Access', icon: '♙' },
      { label: 'Audit Logs', icon: '◷' },
    ]
  },
]

function App() {

  const [learningReferences, setLearningReferences] = useState([])

  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('dims_user') || 'null')
    } catch {
      return null
    }
  })
  const [activePage, setActivePage] = useState('Dashboard')
  const [selectedCase, setSelectedCase] = useState(null)
  const [showCaseForm, setShowCaseForm] = useState(false)
  const [caseTitle, setCaseTitle] = useState('')
  const [caseDescription, setCaseDescription] = useState('')
  const [caseSaving, setCaseSaving] = useState(false)
  const [caseFormError, setCaseFormError] = useState('')
  const [cases, setCases] = useState([])
  const [casesLoading, setCasesLoading] = useState(false)
  const [casesError, setCasesError] = useState('')
  const [investigations, setInvestigations] = useState([])
  const [investigationsLoading, setInvestigationsLoading] = useState(false)
  const [investigationsError, setInvestigationsError] = useState('')
  const [showInvestigationForm, setShowInvestigationForm] = useState(false)
  const [editingInvestigationId, setEditingInvestigationId] = useState(null)
  const [investigationStatus, setInvestigationStatus] = useState('draft')
  const [investigationSaving, setInvestigationSaving] = useState(false)
  const [investigationFormError, setInvestigationFormError] = useState('')
  const [investigationCaseId, setInvestigationCaseId] = useState('')
  const [investigationTitle, setInvestigationTitle] = useState('')
  const [investigationSections, setInvestigationSections] = useState({})
  const [selectedInvestigation, setSelectedInvestigation] = useState(null)
  const [aiRawText, setAiRawText] = useState('')
  const [aiCaseId, setAiCaseId] = useState('')
  const [aiBusy, setAiBusy] = useState(false)
  const [aiError, setAiError] = useState('')
  const [aiResult, setAiResult] = useState(null)

  async function loadLearningReferences() {
    try {
      const data = await learningReferencesApi.list()
      setLearningReferences(Array.isArray(data) ? data : [])
    } catch (error) {
      console.error('Learning references error:', error)
    }
  }


  async function handleAIProcessing(event) {
    event.preventDefault()
    setAiBusy(true)
    setAiError('')
    setAiResult(null)
    try {
      const result = await aiApi.processReport({
        raw_text: aiRawText.trim(),
        case_id: aiCaseId ? Number(aiCaseId) : null,
      })
      setAiResult(result)
    } catch (error) {
      setAiError(error.message || 'AI processing failed.')
    } finally {
      setAiBusy(false)
    }
  }

  async function loadCases() {
    setCasesLoading(true)
    setCasesError('')
    try {
      const data = await casesApi.list()
      const records = Array.isArray(data) ? data : data.cases
      setCases(Array.isArray(records) ? records : [])
    } catch (error) {
      setCasesError(error.message || 'Unable to load cases.')
    } finally {
      setCasesLoading(false)
    }
  }

  async function loadInvestigations() {
    setInvestigationsLoading(true)
    setInvestigationsError('')
    try {
      const data = await investigationsApi.list()
      setInvestigations(Array.isArray(data.investigations) ? data.investigations : [])
    } catch (error) {
      setInvestigationsError(error.message || 'Unable to load investigations.')
    } finally {
      setInvestigationsLoading(false)
    }
  }

  function startEditInvestigation(item) {
    setEditingInvestigationId(item.id)
    setInvestigationCaseId(String(item.case_id))
    setInvestigationTitle(item.title || '')
    setInvestigationStatus(item.status || 'draft')
    setInvestigationSections(Object.fromEntries(investigationFields.map(([key]) => [key, item[key] || ''])))
    setInvestigationFormError('')
    setShowInvestigationForm(true)
    setActivePage('Investigation Management')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function resetInvestigationForm() {
    setShowInvestigationForm(false)
    setEditingInvestigationId(null)
    setInvestigationCaseId('')
    setInvestigationTitle('')
    setInvestigationStatus('draft')
    setInvestigationSections({})
    setInvestigationFormError('')
  }

  async function handleCreateInvestigation(event) {
    event.preventDefault()
    setInvestigationSaving(true)
    setInvestigationFormError('')
    const payload = {
      title: investigationTitle.trim(),
      ...investigationSections,
    }
    const savedInvestigationId = editingInvestigationId
    try {
      if (savedInvestigationId !== null) {
        await investigationsApi.update(savedInvestigationId, { ...payload, status: investigationStatus })
      } else {
        await investigationsApi.create({ case_id: Number(investigationCaseId), ...payload, status: investigationStatus })
      }
      resetInvestigationForm()
      await loadInvestigations()
      if (selectedInvestigation && selectedInvestigation.id === savedInvestigationId) {
        const refreshed = await investigationsApi.get(savedInvestigationId)
        setSelectedInvestigation(refreshed)
      }
    } catch (error) {
      setInvestigationFormError(error.message || 'Unable to save investigation.')
    } finally {
      setInvestigationSaving(false)
    }
  }

  const investigationFields = [
    ['introduction', '1. INTRODUCTION'],
    ['facts_of_case', '2. FACTS OF THE CASE'],
    ['objective_of_investigation', '3. OBJECTIVE OF THE INVESTIGATION'],
    ['investigation_activities', '4. INVESTIGATION ACTIVITIES'],
    ['background_check', '5. BACKGROUND CHECK'],
    ['suspect_statements', '6. PROFILE/SUMMARY OF SUSPECT’S STATEMENTS'],
    ['mobile_phone_exploitation', '7. MOBILE PHONE EXPLOITATION'],
    ['findings', '8. FINDINGS'],
    ['conclusion', '9. CONCLUSION'],
  ]

  async function handleCreateCase(event) {
    event.preventDefault()
    setCaseSaving(true)
    setCaseFormError('')

    try {
      await casesApi.create({
        title: caseTitle.trim(),
        description: caseDescription.trim(),
      })

      setCaseTitle('')
      setCaseDescription('')
      setShowCaseForm(false)
      await loadCases()
    } catch (error) {
      setCaseFormError(error.message || 'Unable to register the case.')
    } finally {
      setCaseSaving(false)
    }
  }


  useEffect(() => {
    if (activePage === 'Learning References') {
      loadLearningReferences()
    }
  }, [activePage])

  useEffect(() => {
    if (user && localStorage.getItem('dims_token')) {
      loadCases()
      loadInvestigations()
    }
  }, [user])

  function handleLogin(loggedInUser) {
    setUser(loggedInUser)
    setActivePage('Dashboard')
  }

  function handleLogout() {
    authApi.logout()
    setUser(null)
    setCases([])
    setCasesError('')
    setActivePage('Dashboard')
  }

  if (!user || !localStorage.getItem('dims_token')) {
    return <Login onLogin={handleLogin} />
  }

  const pageDescriptions = {
    Dashboard: 'Your operational overview at a glance.',
    Cases: 'Register, review and manage intelligence cases.',
    'Intelligence Reports': 'Prepare, process and review intelligence reports.',
    'Investigation Management': 'Prepare structured investigation dossiers linked to registered cases.',
    'Intelligence Processing Agent': 'Use AI to structure synthetic raw reports and flag missing information for analyst review.',
    'Tasking & Operations': 'Coordinate task assignments and operational follow-up.',
    Departments: 'View organizational departments and units.',
    'Users & Access': 'Manage users and access roles.',
    'Audit Logs': 'Review recorded system activities and changes.',
    'Learning References': 'Save and manage approved examples for AI report processing.',
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">D</div>
          <div>
            <div className="brand-name">DIMS</div>
            <div className="brand-subtitle">INTELLIGENCE MANAGEMENT</div>
          </div>
        </div>

        <div className="environment">
          <span className="status-dot" />
          INTERNAL WORKSPACE
        </div>

        <nav className="navigation">
          {navigation.map((group) => (
            <div className="nav-group" key={group.section}>
              <div className="nav-heading">{group.section}</div>
              {group.items.map((item) => (
                <button
                  className={`nav-item ${activePage === item.label ? 'active' : ''}`}
                  key={item.label}
                  onClick={() => setActivePage(item.label)}
                >
                  <span className="nav-icon">{item.icon}</span>
                  <span>{item.label}</span>
                </button>
              ))}
            </div>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="security-note">
            <span className="security-icon">◇</span>
            <div>
              <strong>Secure workspace</strong>
              <span>Authorized access only</span>
            </div>
          </div>
          <div className="sidebar-version">DIMS · FRONTEND PROTOTYPE</div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span>
            <span className="breadcrumb-separator">/</span>
            <strong>{activePage}</strong>
          </div>
          <div className="topbar-right">
            <span className="connection-label">
              <span className="status-dot" />
              {user.username} · {user.role}
            </span>
            <button className="primary-button" onClick={handleLogout}>
              Sign out
            </button>
          </div>
        </header>

        <div className="page-content">
          <section className="welcome-row">
            <div>
              <div className="eyebrow">DSS INTELLIGENCE MANAGEMENT SYSTEM</div>
              <h1>{activePage}</h1>
              <p className="page-description">{pageDescriptions[activePage]}</p>
            </div>
            <div className="date-label">Operational workspace</div>
          </section>

          {activePage === 'Dashboard' ? (
            <>
              <section className="metrics-grid">
                <article className="metric-card">
                  <div className="metric-top">
                    <span className="metric-label">TOTAL CASES</span>
                    <span className="metric-icon navy">▤</span>
                  </div>
                  <div className="metric-value">
                    {casesLoading ? '…' : casesError ? '!' : cases.length}
                  </div>
                  <div className="metric-foot">
                    {casesError ? 'Unable to retrieve cases' : 'Cases returned by DIMS'}
                  </div>
                </article>
                <article className="metric-card">
                  <div className="metric-top">
                    <span className="metric-label">INTELLIGENCE REPORTS</span>
                    <span className="metric-icon blue">◈</span>
                  </div>
                  <div className="metric-value">—</div>
                  <div className="metric-foot">Not connected yet</div>
                </article>
                <article className="metric-card">
                  <div className="metric-top">
                    <span className="metric-label">PENDING TASKS</span>
                    <span className="metric-icon amber">⇄</span>
                  </div>
                  <div className="metric-value">—</div>
                  <div className="metric-foot">Not connected yet</div>
                </article>
                <article className="metric-card">
                  <div className="metric-top">
                    <span className="metric-label">REPORTS FOR REVIEW</span>
                    <span className="metric-icon green">✓</span>
                  </div>
                  <div className="metric-value">—</div>
                  <div className="metric-foot">Not connected yet</div>
                </article>
              </section>

              {casesError && (
                <section className="panel cases-error">
                  <strong>Case records could not be loaded.</strong>
                  <p>{casesError}</p>
                  <button className="primary-button" onClick={loadCases}>
                    Retry connection
                  </button>
                </section>
              )}

              <section className="content-grid">
                <article className="panel activity-panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Workspace overview</h2>
                      <p>Choose a workspace area to continue</p>
                    </div>
                  </div>
                  <div className="overview-list">
                    {[
                      ['Cases', '▤', 'Register and track intelligence cases'],
                      ['Intelligence Reports', '◈', 'Submit, process and review reports'],
                      ['Tasking & Operations', '⇄', 'Coordinate task assignments'],
                      ['Audit Logs', '◷', 'Review recorded system activity'],
                    ].map(([label, icon, description]) => (
                      <button
                        key={label}
                        className="overview-item"
                        onClick={() => setActivePage(label)}
                      >
                        <span className="overview-icon navy">{icon}</span>
                        <span className="overview-copy">
                          <strong>{label}</strong>
                          <span>{description}</span>
                        </span>
                        <span className="overview-arrow">→</span>
                      </button>
                    ))}
                  </div>
                </article>

                <article className="panel system-panel">
                  <div className="panel-heading">
                    <div>
                      <h2>System status</h2>
                      <p>Local development environment</p>
                    </div>
                  </div>
                  <div className="system-row">
                    <span>Frontend</span>
                    <strong><span className="status-dot" /> Running</strong>
                  </div>
                  <div className="system-row">
                    <span>Authentication</span>
                    <strong><span className="status-dot" /> Signed in</strong>
                  </div>
                  <div className="system-row">
                    <span>Case API</span>
                    <strong className={casesError ? 'not-connected' : ''}>
                      {casesLoading ? 'Checking…' : casesError ? 'Error' : 'Responding'}
                    </strong>
                  </div>
                  <div className="notice">
                    <span className="notice-icon">i</span>
                    <p>Only case records have been connected so far. Other dashboard figures are not live yet.</p>
                  </div>
                </article>
              </section>
            </>
          ) : activePage === 'Cases' ? (
            <section className="panel cases-panel">
              <div className="panel-heading">
                <div>
                  <h2>Registered Cases</h2>
                  <button
                    className="primary-button"
                    onClick={() => setShowCaseForm(true)}
                  >
                    + Register New Case
                  </button>
                  <p>{casesLoading ? 'Loading records…' : `${cases.length} case record(s)`}</p>
                </div>
                <button className="primary-button" onClick={loadCases} disabled={casesLoading}>
                  {casesLoading ? 'Refreshing…' : 'Refresh records'}
                </button>
              </div>

              {showCaseForm && (
                <form className="case-form" onSubmit={handleCreateCase}>
                  <div className="case-form-heading">
                    <h2>Register New Case</h2>
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => {
                        setShowCaseForm(false)
                        setCaseFormError('')
                      }}
                    >
                      Cancel
                    </button>
                  </div>

                  <label htmlFor="case-title">Case title</label>
                  <input
                    id="case-title"
                    type="text"
                    value={caseTitle}
                    onChange={(event) => setCaseTitle(event.target.value)}
                    placeholder="Enter the case title"
                    required
                    maxLength={200}
                  />

                  <label htmlFor="case-description">Description</label>
                  <textarea
                    id="case-description"
                    value={caseDescription}
                    onChange={(event) => setCaseDescription(event.target.value)}
                    placeholder="Enter the case description"
                    rows={5}
                  />

                  {caseFormError && (
                    <p className="case-form-error">{caseFormError}</p>
                  )}

                  <button
                    type="submit"
                    className="primary-button"
                    disabled={caseSaving}
                  >
                    {caseSaving ? 'Registering…' : 'Save Case'}
                  </button>
                </form>
              )}

              {casesError ? (
                <div className="cases-error">
                  <strong>Unable to retrieve cases</strong>
                  <p>{casesError}</p>
                  <button className="primary-button" onClick={loadCases}>Try again</button>
                </div>
              ) : casesLoading ? (
                <p className="cases-message">Loading case records…</p>
              ) : cases.length === 0 ? (
                <p className="cases-message">No cases were returned by the API.</p>
              ) : (
                <div className="cases-table-wrap">
                  <table className="cases-table">
                    <thead>
                      <tr>
                        <th>Case reference</th>
                        <th>Title and description</th>
                        <th>Status</th>
                        <th>Last updated</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cases.map((item) => (
                        <tr key={item.id}>
                          <td className="case-reference">{item.case_reference}</td>
                          <td>
                            <strong className="case-title">{item.title}</strong>
                            <span className="case-description">
                              {item.description || 'No description provided'}
                            </span>
                          </td>
                          <td>
                            <span className={`case-status ${String(item.status || '').toLowerCase().replace(/\s+/g, '-')}`}>
                              {item.status || 'Unknown'}
                            </span>
                          </td>
                          <td className="case-date">
                            {item.updated_at
                              ? new Date(item.updated_at).toLocaleDateString()
                              : '—'}
                          </td>
                          <td>
                            <button
                              type="button"
                              className="secondary-button"
                              onClick={() => {
                                setSelectedCase(item)
                                setActivePage('Case Details')
                              }}
                            >
                              View
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

          ) : activePage === 'Intelligence Processing Agent' ? (
            <section className="panel ai-processing-panel">
              <div className="panel-heading">
                <div><h2>Intelligence Processing Agent</h2><p>AI-assisted structuring, gap detection and analyst review.</p></div>
              </div>
              <div className="ai-safety-notice"><strong>Prototype safety notice</strong><p>Use synthetic or declassified text only. The AI output is a draft, not verified intelligence. Check all claims against source material.</p></div>
              <form className="ai-processing-form" onSubmit={handleAIProcessing}>
                <label htmlFor="ai-case">Optional linked case</label>
                <select id="ai-case" value={aiCaseId} onChange={e => setAiCaseId(e.target.value)}><option value="">No case context</option>{cases.map(item => <option key={item.id} value={item.id}>{item.case_reference} — {item.title}</option>)}</select>
                <label htmlFor="ai-raw-report">Synthetic raw report</label>
                <textarea id="ai-raw-report" rows={10} minLength={20} maxLength={12000} required value={aiRawText} onChange={e => setAiRawText(e.target.value)} placeholder="Paste a synthetic raw report here. Include only facts you want the agent to process." />
                <div className="ai-form-footer"><span>{aiRawText.length}/12000 characters</span><button className="primary-button" type="submit" disabled={aiBusy || aiRawText.trim().length < 20}>{aiBusy ? 'Processing with AI…' : 'Process Report'}</button></div>
              </form>
              {aiError && <div className="cases-error"><strong>AI processing failed</strong><p>{aiError}</p></div>}
              {aiResult && <section className="ai-result-panel"><div className="panel-heading"><div><h2>AI Processing Result</h2><p>Model: {aiResult.model} · Input tokens: {aiResult.usage?.input_tokens ?? '—'} · Output tokens: {aiResult.usage?.output_tokens ?? '—'}</p></div><button className="secondary-button" onClick={() => navigator.clipboard?.writeText(aiResult.analysis || '')} type="button">Copy draft</button></div><p className="ai-result-notice">{aiResult.notice}</p><pre className="ai-result-text">{aiResult.analysis}</pre></section>}
            </section>
          ) : activePage === 'Investigation Management' ? (
            <section className="panel investigation-panel">
              <div className="panel-heading">
                <div>
                  <h2>Investigation Dossiers</h2>
                  <p>{investigationsLoading ? 'Loading records…' : `${investigations.length} investigation record(s)`}</p>
                </div>
                <div className="investigation-actions">
                  <button className="secondary-button" onClick={loadInvestigations} disabled={investigationsLoading}>Refresh</button>
                  <button className="primary-button" onClick={() => { resetInvestigationForm(); setShowInvestigationForm(true) }}>+ New Investigation</button>
                </div>
              </div>

              {showInvestigationForm && (
                <form className="investigation-form" onSubmit={handleCreateInvestigation}>
                  <div className="case-form-heading">
                    <h2>{editingInvestigationId !== null ? 'Edit Investigation Dossier' : 'New Investigation Dossier'}</h2>
                    <button type="button" className="secondary-button" onClick={resetInvestigationForm}>Cancel</button>
                  </div>
                  {editingInvestigationId === null && <>
                    <label htmlFor="investigation-case">Parent case</label>
                    <select id="investigation-case" value={investigationCaseId} onChange={e => setInvestigationCaseId(e.target.value)} required>
                      <option value="">Select a registered case</option>
                      {cases.map(item => <option key={item.id} value={item.id}>{item.case_reference} — {item.title}</option>)}
                    </select>
                  </>}
                  <label htmlFor="investigation-title">Investigation report title</label>
                  <input id="investigation-title" value={investigationTitle} onChange={e => setInvestigationTitle(e.target.value)} maxLength={500} required minLength={3} placeholder="Enter the formal investigation report title" />
                  <label htmlFor="investigation-status">Investigation status</label>
                  <select id="investigation-status" value={investigationStatus} onChange={e => setInvestigationStatus(e.target.value)}>
                    <option value="draft">Draft</option>
                    <option value="in progress">In Progress</option>
                    <option value="completed">Completed</option>
                  </select>
                  {investigationFields.map(([key, label]) => (
                    <div className="investigation-field" key={key}>
                      <label htmlFor={`inv-${key}`}>{label}</label>
                      <textarea id={`inv-${key}`} rows={4} value={investigationSections[key] || ''} onChange={e => setInvestigationSections(prev => ({ ...prev, [key]: e.target.value }))} placeholder={`Enter content for ${label.toLowerCase()}…`} />
                    </div>
                  ))}
                  {investigationFormError && <p className="case-form-error">{investigationFormError}</p>}
                  <button className="primary-button" type="submit" disabled={investigationSaving}>{investigationSaving ? 'Saving…' : editingInvestigationId !== null ? 'Save Changes' : 'Save Investigation Draft'}</button>
                </form>
              )}

              {investigationsError ? <div className="cases-error"><strong>Unable to retrieve investigations</strong><p>{investigationsError}</p><button className="primary-button" onClick={loadInvestigations}>Try again</button></div> : investigationsLoading ? <p className="cases-message">Loading investigation records…</p> : investigations.length === 0 ? <p className="cases-message">No investigation dossiers yet. Create one and link it to a registered case.</p> : (
                <div className="cases-table-wrap"><table className="cases-table investigation-table"><thead><tr><th>Investigation reference</th><th>Report title</th><th>Parent case</th><th>Status</th><th>Action</th></tr></thead><tbody>
                  {investigations.map(item => { const parent = cases.find(c => c.id === item.case_id); return <tr key={item.id}><td className="case-reference">{item.investigation_reference}</td><td><strong className="case-title">{item.title}</strong></td><td>{parent ? parent.case_reference : `Case ID ${item.case_id}`}</td><td><span className={`case-status ${String(item.status).replace(/\s+/g, '-')}`}>{item.status}</span></td><td><div className="investigation-actions"><button className="secondary-button" onClick={() => { setSelectedInvestigation(item); setActivePage('Investigation Details') }}>View</button><button className="secondary-button" onClick={() => startEditInvestigation(item)}>Edit</button></div></td></tr> })}
                </tbody></table></div>
              )}
            </section>
          ) : activePage === 'Investigation Details' ? (
            <section className="panel investigation-report-view">
              {selectedInvestigation ? <>
                <div className="report-print-heading"><div>DEPARTMENT OF STATE SERVICES</div><h2>{selectedInvestigation.title}</h2><p>{selectedInvestigation.investigation_reference} · Parent case: {cases.find(c => c.id === selectedInvestigation.case_id)?.case_reference || selectedInvestigation.case_id}</p></div>
                {investigationFields.map(([key, label], index) => <section className="report-section" key={key}><h3>{label}</h3><p>{selectedInvestigation[key] || 'Not yet completed.'}</p></section>)}
                <p className="report-closing">Above for your information, please.</p>
                <div className="investigation-actions no-print"><button className="secondary-button" onClick={() => setActivePage('Investigation Management')}>Back to Investigations</button><button className="secondary-button" onClick={() => startEditInvestigation(selectedInvestigation)}>Edit Investigation</button><button className="primary-button" onClick={() => window.print()}>Print / Save as PDF</button></div>
              </> : <p>No investigation selected.</p>}
            </section>
          ) : activePage === 'Case Details' ? (
            <section className="panel case-details">
              {selectedCase ? (
                <>
                  <h2>Case Details</h2>

                  <div className="case-detail-grid">
                    <div>
                      <strong>Case Reference</strong>
                      <p>{selectedCase.case_reference}</p>
                    </div>

                    <div>
                      <strong>Title</strong>
                      <p>{selectedCase.title}</p>
                    </div>

                    <div>
                      <strong>Status</strong>
                      <p>{selectedCase.status}</p>
                    </div>

                    <div>
                      <strong>Last Updated</strong>
                      <p>
                        {selectedCase.updated_at
                          ? new Date(selectedCase.updated_at).toLocaleDateString()
                          : 'Not available'}
                      </p>
                    </div>

                    <div className="case-detail-description">
                      <strong>Description</strong>
                      <p>{selectedCase.description || 'No description provided.'}</p>
                    </div>
                  </div>

                  <button
                    className="primary-button"
                    onClick={() => setActivePage('Cases')}
                  >
                    Back to Cases
                  </button>
                </>
              ) : (
                <>
                  <h2>No Case Selected</h2>
                  <p>Select a case from the Cases page to view its details.</p>
                  <button
                    className="primary-button"
                    onClick={() => setActivePage('Cases')}
                  >
                    Back to Cases
                  </button>
                </>
              )}
            </section>

          ) : activePage === 'Intelligence Reports' ? (
            <ReportsWorkspace user={user} />
          ) : activePage === 'Departments' || activePage === 'Users & Access' ? (
            <ReportsWorkspace user={user} />
          ) : activePage === 'Learning References' ? (
            <section className="panel">
              <h2>Learning References</h2>
              <p>Save approved examples to guide future AI report processing.</p>

              <div className="ai-safety-notice">
                <strong>Prototype safety notice</strong>
                <p>Use synthetic or declassified reports only.</p>
              </div>

              <form
                className="ai-processing-form"
                onSubmit={async (event) => {
                  event.preventDefault()
                  const form = event.currentTarget

                  try {
                    await learningReferencesApi.save({
                      report_category: form.elements['learning-category'].value,
                      title: form.elements['learning-title'].value.trim(),
                      approved_final_text: form.elements['learning-text'].value.trim(),
                    })

                    alert('Learning reference saved successfully.')
                    form.reset()
                    await loadLearningReferences()
                  } catch (error) {
                    alert(`Could not save reference: ${error.message}`)
                  }
                }}
              >
                <label htmlFor="learning-category">Report category</label>
                <select id="learning-category" required defaultValue="">
                  <option value="" disabled>Select a category</option>
                  <option>Incident Intelligence Report</option>
                  <option>Preliminary Investigation Report</option>
                  <option>Coverage Report</option>
                  <option>Command Efforts Report</option>
                  <option>Early Warning Intelligence (EWI)</option>
                  <option>Actionable Intelligence Report</option>
                  <option>Security Meeting Report</option>
                  <option>Other</option>
                </select>

                <label htmlFor="learning-title">Reference title</label>
                <input
                  id="learning-title"
                  type="text"
                  required
                  maxLength={200}
                  placeholder="Enter reference title"
                />

                <label htmlFor="learning-text">Approved final report</label>
                <textarea
                  id="learning-text"
                  rows={12}
                  required
                  minLength={20}
                  maxLength={20000}
                  placeholder="Paste the final synthetic or declassified report here..."
                />

                <button className="primary-button" type="submit">
                  Save Reference
                </button>
              </form>


              <div className="learning-reference-list">
                <h3>Saved Learning References</h3>

                {learningReferences.length === 0 ? (
                  <p>No saved learning references found.</p>
                ) : (
                  learningReferences.map((reference) => (
                    <article key={reference.id} className="panel">
                      <h4>{reference.title}</h4>
                      <p><strong>Category:</strong> {reference.report_category}</p>
                      <p>
                        <strong>Date created:</strong>{' '}
                        {reference.created_at
                          ? new Date(reference.created_at).toLocaleDateString()
                          : 'Not available'}
                      </p>
                      <details>
                        <summary>View approved report text</summary>
                        <p className="learning-reference-text">
                          {reference.approved_final_text}
                        </p>
                      </details>
                    </article>
                  ))
                )}
              </div>


            </section>
          ) : (
            <section className="panel placeholder-page">
              <div className="placeholder-symbol">◇</div>
              <h2>{activePage}</h2>
              <p>This section is prepared in the interface. Its records and actions will be connected to the existing DIMS backend in later steps.</p>
              <button className="primary-button" onClick={() => setActivePage('Dashboard')}>
                Back to dashboard
              </button>
            </section>
          )}


          <footer className="page-footer">
            <span>DIMS · Intelligence Management System</span>
            <span>Internal development prototype</span>
          </footer>
        </div>
      </main>
    </div>
  )
}

export default App
