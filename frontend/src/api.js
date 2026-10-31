const API_BASE = '/api'

async function request(path, options = {}) {
  const token = localStorage.getItem('dims_token')
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (token) headers.Authorization = `Bearer ${token}`
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (!response.ok) {
    const message = await response.text()
    throw new Error(`HTTP ${response.status}: ${message || response.statusText}`)
  }
  if (response.status === 204) return null
  return response.json()
}

export const authApi = {
  async login(username, password) {
    const data = await request('/login', { method: 'POST', body: JSON.stringify({ username, password }) })
    if (!data.access_token) throw new Error('Login succeeded, but no access token was returned.')
    localStorage.setItem('dims_token', data.access_token)
    localStorage.setItem('dims_user', JSON.stringify({
      user_id: data.user_id, username: data.username, role: data.role,
      token_type: data.token_type,
    }))
    return data
  },
  logout() {
    localStorage.removeItem('dims_token')
    localStorage.removeItem('dims_user')
  },
}

export const casesApi = {
  list: () => request('/cases'),
  get: (caseId) => request(`/cases/${caseId}`),
  create: (data) => request('/cases', { method: 'POST', body: JSON.stringify(data) }),
  update: (caseId, data) => request(`/cases/${caseId}`, { method: 'PATCH', body: JSON.stringify(data) }),
  updateStatus: (caseId, status) => request(`/cases/${caseId}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
}

export const investigationsApi = {
  list: (caseId) => request(`/investigations${caseId ? `?case_id=${caseId}` : ''}`),
  get: (id) => request(`/investigations/${id}`),
  create: (data) => request('/investigations', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data) => request(`/investigations/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
}

export const aiApi = {
  processReport: (data) => request('/ai/process-report', { method: 'POST', body: JSON.stringify(data) }),
}

export const learningReferencesApi = {
  list: () => request('/learning-references/manual'),
  save: (data) => request('/learning-references/manual', { method: 'POST', body: JSON.stringify(data) }),
}

export const intelligenceReportsApi = {
  list: () => request('/reports'),
  get: (reportId) => request(`/reports/${reportId}`),
  submit: (data) => request('/reports', { method: 'POST', body: JSON.stringify(data) }),
  process: (reportId, data) => request(`/reports/${reportId}/process`, { method: 'POST', body: JSON.stringify(data) }),
  processingHistory: (reportId) => request(`/reports/${reportId}/processing-history`),
  approve: (reportId) => request(`/reports/${reportId}/approve`, { method: 'POST' }),
  assign: (reportId, data) => request(`/reports/${reportId}/task`, { method: 'POST', body: JSON.stringify(data) }),
  reassign: (reportId, data) => request(`/reports/${reportId}/reassign`, { method: 'POST', body: JSON.stringify(data) }),
  taskingHistory: (reportId) => request(`/reports/${reportId}/tasking-history`),
  myWork: () => request('/taskings/my-work'),
  activeTaskings: () => request('/taskings/active'),
}

export const administrationApi = {
  departments: () => request('/departments'),
  createDepartment: (data) => request('/departments', { method: 'POST', body: JSON.stringify(data) }),
  users: () => request('/users'),
  assignAnalystDepartment: (userId, departmentId) => request(`/users/${userId}/department`, {
    method: 'PATCH', body: JSON.stringify({ department_id: departmentId }),
  }),
}
