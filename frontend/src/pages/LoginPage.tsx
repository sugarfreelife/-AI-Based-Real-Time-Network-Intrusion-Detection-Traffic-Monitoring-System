import { Activity, Eye, EyeOff, LockKeyhole, RadioTower } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { ApiError } from '../lib/api'
import { useAuth } from '../auth/AuthProvider'

export function LoginPage() {
  const { user, login } = useAuth()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const from = (location.state as { from?: string } | null)?.from

  if (user) return <Navigate to={from?.startsWith('/') ? from : '/alerts'} replace />

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      await login(username.trim(), password)
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'Could not sign in. Check the API connection and try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="login-page">
      <div className="login-topline"><Link to="/login" className="brand-lockup" aria-label="Network observatory">
        <span className="brand-mark"><RadioTower size={19} /></span><span className="brand-copy"><strong>Network</strong><span>observatory</span></span>
      </Link><span className="login-context"><Activity size={14} /> Private workspace</span></div>
      <div className="login-layout">
        <section className="login-story" aria-labelledby="login-title">
          <div className="trace-graphic" aria-hidden="true"><span /><span /><span /><span /><i /></div>
          <p className="eyebrow">Network evidence, in context</p>
          <h1 id="login-title">A clearer view<br />of what moved.</h1>
          <p className="login-intro">Review persisted network flows and explainable alerts from your monitoring pipeline.</p>
          <div className="login-note"><LockKeyhole size={16} /><span>Sign in with an account provisioned by your administrator.</span></div>
        </section>
        <section className="login-panel" aria-labelledby="welcome-title">
          <div className="panel-kicker">Secure access</div>
          <h2 id="welcome-title">Welcome back</h2>
          <p className="panel-copy">Your session stays in this tab and expires automatically.</p>
          <form className="login-form" onSubmit={(event) => void submit(event)} noValidate>
            <label className="field-label" htmlFor="username">Username</label>
            <input id="username" name="username" type="text" autoComplete="username" autoCapitalize="none" spellCheck={false} value={username} onChange={(event) => setUsername(event.target.value)} required maxLength={64} autoFocus />
            <div className="password-label-row"><label className="field-label" htmlFor="password">Password</label><span className="field-hint">12–128 characters</span></div>
            <div className="password-input-wrap">
              <input id="password" name="password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required maxLength={128} />
              <button className="password-toggle" type="button" aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword} onClick={() => setShowPassword((visible) => !visible)}>
                {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
              </button>
            </div>
            {error && <div className="form-error" role="alert">{error}</div>}
            <button className="button button-primary login-submit" type="submit" disabled={busy || !username.trim() || !password} aria-busy={busy}>
              {busy ? <span className="spinner" aria-hidden="true" /> : null}{busy ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
          <div className="login-security"><span className="security-rule" /><span>Credentials are never saved in your browser.</span></div>
        </section>
      </div>
      <footer className="login-footer"><span>NIDS · Network intrusion detection</span><span>Evidence-first monitoring</span></footer>
    </main>
  )
}
