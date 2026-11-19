import { useState } from 'react'
import { authApi } from './api'
import './Login.css'

function Login({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [mustChangePassword, setMustChangePassword] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setNotice('')
    setLoading(true)

    try {
      const user = await authApi.login(username.trim(), password)
      if (user.must_change_password) {
        setMustChangePassword(true)
        setNotice('Your account has a temporary password. Change it before continuing.')
      } else {
        onLogin(user)
      }
    } catch (err) {
      setError(
        err.message.includes('401')
          ? 'Invalid username or password.'
          : err.message.includes('403')
            ? 'This account is inactive or access is denied.'
            : 'Unable to sign in. Check that the DIMS backend is running.'
      )
    } finally {
      setLoading(false)
    }
  }

  async function handlePasswordChange(event) {
    event.preventDefault()
    setError('')
    setNotice('')
    if (newPassword.length < 8) {
      setError('New password must contain at least 8 characters.')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('The new passwords do not match.')
      return
    }
    if (newPassword === password) {
      setError('Choose a new password different from the temporary password.')
      return
    }

    setLoading(true)
    try {
      await authApi.changePassword(password, newPassword)
      const storedUser = JSON.parse(localStorage.getItem('dims_user') || '{}')
      onLogin({ ...storedUser, access_token: localStorage.getItem('dims_token'), must_change_password: false })
    } catch (err) {
      setError(err.message.includes('400')
        ? 'The temporary password is incorrect or the new password was rejected.'
        : 'Unable to change password. Please sign in again or contact the administrator.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <div className="login-brand-mark">D</div>
        <div className="login-brand-name">DIMS</div>
        <div className="login-brand-subtitle">
          DSS INTELLIGENCE MANAGEMENT SYSTEM
        </div>

        <div className="login-divider" />

        {mustChangePassword ? (
          <>
            <h1>Change temporary password</h1>
            <p className="login-description">
              Set a new password to complete sign-in. Use at least 8 characters.
            </p>
            <form onSubmit={handlePasswordChange}>
              <label htmlFor="dims-new-password">New password</label>
              <input
                id="dims-new-password"
                type="password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                placeholder="Enter a new password"
                required
                minLength={8}
              />
              <label htmlFor="dims-confirm-password">Confirm new password</label>
              <input
                id="dims-confirm-password"
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                placeholder="Confirm your new password"
                required
                minLength={8}
              />
              {error && <div className="login-error">{error}</div>}
              {notice && <div className="login-security-note">{notice}</div>}
              <button type="submit" disabled={loading}>
                {loading ? 'Updating password…' : 'Change password and continue'}
              </button>
            </form>
            <button
              type="button"
              className="secondary-button"
              disabled={loading}
              onClick={() => {
                authApi.logout()
                setMustChangePassword(false)
                setPassword('')
                setUsername('')
                setNewPassword('')
                setConfirmPassword('')
                setNotice('')
              }}
            >
              Sign out
            </button>
          </>
        ) : (
          <>
            <h1>Welcome back</h1>
            <p className="login-description">
              Sign in with your authorized DIMS account.
            </p>
            <form onSubmit={handleSubmit}>
              <label htmlFor="dims-username">Username</label>
              <input
                id="dims-username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="Enter your username"
                required
              />
              <label htmlFor="dims-password">Password</label>
              <input
                id="dims-password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter your password"
                required
              />
              {error && <div className="login-error">{error}</div>}
              <button type="submit" disabled={loading}>
                {loading ? 'Signing in…' : 'Sign in securely'}
              </button>
            </form>
          </>
        )}

        <div className="login-security-note">
          Authorized access only · Internal workspace
        </div>
      </section>
    </main>
  )
}

export default Login
