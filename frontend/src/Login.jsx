
import { useState } from 'react'
import { authApi } from './api'
import './Login.css'

function Login({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setLoading(true)

    try {
      const user = await authApi.login(username.trim(), password)
      onLogin(user)
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

  return (
    <main className="login-page">
      <section className="login-card">
        <div className="login-brand-mark">D</div>
        <div className="login-brand-name">DIMS</div>
        <div className="login-brand-subtitle">
          DSS INTELLIGENCE MANAGEMENT SYSTEM
        </div>

        <div className="login-divider" />

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

        <div className="login-security-note">
          Authorized access only · Internal workspace
        </div>
      </section>
    </main>
  )
}

export default Login
