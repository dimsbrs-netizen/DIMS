const API_BASE = 'https://dims-5fam.onrender.com'
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
      full_name: data.full_name, designation: data.designation, formation: data.formation,
      token_type: data.token_type, must_change_password: Boolean(data.must_change_password),
    }))
    return data
  },
  async changePassword(current_password, new_password) {
    const result = await request('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password, new_password }),
    })
    const storedUser = JSON.parse(localStorage.getItem('dims_user') || '{}')
    localStorage.setItem('dims_user', JSON.stringify({ ...storedUser, must_change_password: false }))
    return result
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

export const adminDashboardApi = {
  summary: () => request('/admin/summary'),
  users: () => request('/users'),
  createUser: (data) => request('/admin/users', { method: 'POST', body: JSON.stringify(data) }),
  updateUser: (id, data) => request(`/admin/users/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  resetPassword: (id, temporary_password) => request(`/admin/users/${id}/reset-password`, { method: 'POST', body: JSON.stringify({ temporary_password }) }),
  updateRole: (id, role) => request(`/users/${id}/role`, { method: 'PATCH', body: JSON.stringify({ role }) }),
  updateStatus: (id, is_active) => request(`/users/${id}/status`, { method: 'PATCH', body: JSON.stringify({ is_active }) }),
  departments: () => request('/departments'),
  createDepartment: (data) => request('/departments', { method: 'POST', body: JSON.stringify(data) }),
  auditLogs: () => request('/audit-logs?limit=100'),
}

export const reviewWorkflowApi = {
  pending: () => request('/workflow/pending'),
  reviewed: () => request('/workflow/reviewed'),
  reviewers: () => request('/workflow/reviewers'),
  forward: (reportId, data) => request(`/reports/${reportId}/forward`, { method: 'POST', body: JSON.stringify(data) }),
  workflow: (reportId) => request(`/reports/${reportId}/workflow`),
  notifications: () => request('/notifications'),
  markRead: (id) => request(`/notifications/${id}/read`, { method: 'PATCH' }),
  discard: (reportId, reason) => request(`/reports/${reportId}/discard`, { method: 'POST', body: JSON.stringify({ reason }) }),
}
