import { Check, UserPlus, UsersRound } from 'lucide-react'
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { EmptyState, ErrorState, LoadingState, StaleState } from '../components/ListStates'
import { Pagination } from '../components/Pagination'
import { formatDate } from '../lib/presentation'
import type { Page, Role, User } from '../lib/types'

const pageSizes = [25, 50, 100]

function normalizeLimit(value: string | null): number {
  const limit = Number(value)
  return pageSizes.includes(limit) ? limit : 25
}

function normalizeOffset(value: string | null, limit: number): number {
  return Math.max(0, Math.floor((Number(value) || 0) / limit) * limit)
}

export function UserManagementPage() {
  const { user, request } = useAuth()
  const [params, setParams] = useSearchParams()
  const paramKey = params.toString()
  const limit = normalizeLimit(params.get('limit'))
  const offset = normalizeOffset(params.get('offset'), limit)
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) }).toString()
  const [data, setData] = useState<Page<User> | null>(null)
  const [listError, setListError] = useState('')
  const [busy, setBusy] = useState(false)
  const [retry, setRetry] = useState(0)
  const [reload, setReload] = useState(0)
  const [pendingUserId, setPendingUserId] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState('')
  const [actionError, setActionError] = useState('')
  const [createBusy, setCreateBusy] = useState(false)
  const [createError, setCreateError] = useState('')
  const [createMessage, setCreateMessage] = useState('')
  const [draft, setDraft] = useState<{ username: string; password: string; role: Role }>({
    username: '',
    password: '',
    role: 'analyst',
  })

  useEffect(() => {
    const current = new URLSearchParams(paramKey)
    let changed = false
    if (!current.get('limit')) { current.set('limit', '25'); changed = true }
    if (!current.get('offset')) { current.set('offset', '0'); changed = true }
    if (changed) setParams(current, { replace: true })
  }, [paramKey, setParams])

  const load = useCallback(async (signal?: AbortSignal) => {
    setBusy(true)
    setListError('')
    try {
      const response = await request<Page<User>>(`/api/v1/auth/users?${query}`, { signal })
      setData(response)
      const lastOffset = response.total === 0 ? 0 : Math.floor((response.total - 1) / response.limit) * response.limit
      if (offset > lastOffset) {
        setParams((current) => {
          const next = new URLSearchParams(current)
          next.set('offset', String(lastOffset))
          return next
        }, { replace: true })
      }
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === 'AbortError') return
      setListError(reason instanceof Error ? reason.message : 'Could not load user accounts.')
    } finally {
      if (!signal?.aborted) setBusy(false)
    }
  }, [offset, query, request, setParams])

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load, retry, reload])

  const createUser = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setCreateError('')
    setCreateMessage('')
    setActionError('')
    const username = draft.username.trim().toLowerCase()
    if (!/^[a-z0-9][a-z0-9._-]{2,63}$/.test(username)) {
      setCreateError('Use 3–64 letters, numbers, dots, underscores, or hyphens. Start with a letter or number.')
      return
    }
    if (draft.password.length < 12) {
      setCreateError('Use a password with at least 12 characters.')
      return
    }
    setCreateBusy(true)
    try {
      await request<User>('/api/v1/auth/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password: draft.password, role: draft.role }),
      })
      setDraft({ username: '', password: '', role: 'analyst' })
      setCreateMessage(`Account ${username} was created and is active.`)
      setParams({ limit: String(limit), offset: '0' })
      setReload((count) => count + 1)
    } catch (reason) {
      setCreateError(reason instanceof Error ? reason.message : 'Could not create this account.')
    } finally {
      setCreateBusy(false)
    }
  }

  const changeStatus = async (target: User) => {
    setPendingUserId(target.id)
    setActionError('')
    setActionMessage('')
    try {
      const updated = await request<User>(`/api/v1/auth/users/${encodeURIComponent(target.id)}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !target.is_active }),
      })
      setData((current) => current ? { ...current, items: current.items.map((item) => item.id === updated.id ? updated : item) } : current)
      setActionMessage(`${updated.username} is now ${updated.is_active ? 'active' : 'inactive'}.`)
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : 'Could not change this account status.')
    } finally {
      setPendingUserId(null)
    }
  }

  const setPage = (page: number) => setParams((current) => {
    const next = new URLSearchParams(current)
    next.set('offset', String((page - 1) * limit))
    return next
  })
  const setPageSize = (size: number) => setParams((current) => {
    const next = new URLSearchParams(current)
    next.set('limit', String(size))
    next.set('offset', '0')
    return next
  })

  return <div className="page-content">
    <div className="page-heading-row">
      <div><p className="eyebrow"><span className="eyebrow-marker" />Access administration</p><h1>User management</h1><p className="page-description">Create accounts, review roles, and suspend access with an audit trail.</p></div>
      <div className="heading-stamp"><UsersRound size={17} /><span>Administrator only</span></div>
    </div>

    <section className="records-panel user-create-panel" aria-labelledby="create-user-heading">
      <div className="records-heading"><div><p className="eyebrow">New operator</p><h2 id="create-user-heading">Create an account</h2></div><UserPlus size={17} aria-hidden="true" /></div>
      <form className="user-create-form" onSubmit={(event) => void createUser(event)}>
        <div className="filter-field"><label htmlFor="new-username">Username</label><input id="new-username" autoComplete="off" maxLength={64} minLength={3} required value={draft.username} onChange={(event) => setDraft((current) => ({ ...current, username: event.target.value }))} /></div>
        <div className="filter-field"><label htmlFor="new-password">Temporary password</label><input id="new-password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={draft.password} onChange={(event) => setDraft((current) => ({ ...current, password: event.target.value }))} /><span className="field-hint">At least 12 characters. Never shown again.</span></div>
        <div className="filter-field"><label htmlFor="new-role">Role</label><select id="new-role" value={draft.role} onChange={(event) => setDraft((current) => ({ ...current, role: event.target.value as Role }))}><option value="analyst">Analyst</option><option value="viewer">Viewer</option><option value="admin">Administrator</option></select></div>
        <button className="button button-primary user-create-button" type="submit" disabled={createBusy}>{createBusy ? 'Creating…' : 'Create account'}</button>
      </form>
      {createError && <p className="user-form-feedback user-form-error" role="alert">{createError}</p>}
      {createMessage && <p className="user-form-feedback user-form-success" role="status"><Check size={14} />{createMessage}</p>}
    </section>

    <section className="records-panel user-list-panel" aria-labelledby="user-list-heading">
      <div className="records-heading"><div><p className="eyebrow">Provisioned accounts</p><h2 id="user-list-heading">Account register</h2></div><div className="records-meta">{data ? <><strong>{data.total.toLocaleString()}</strong> {data.total === 1 ? 'account' : 'accounts'}{busy && <span className="updating-label" role="status"><i />Updating</span>}</> : busy ? <span className="updating-label" role="status"><i />Loading</span> : 'No data'}</div></div>
      {listError && data && <StaleState onRetry={() => setRetry((count) => count + 1)} />}
      {listError && !data && <ErrorState message={listError} onRetry={() => setRetry((count) => count + 1)} />}
      {actionError && <p className="user-action-error" role="alert">{actionError}</p>}
      {actionMessage && <p className="user-action-success" role="status"><Check size={14} />{actionMessage}</p>}
      {!data && busy && <LoadingState label="Loading user accounts…" />}
      {data && data.items.length === 0 && !listError && <EmptyState filtered={false} kind="users" />}
      {data && data.items.length > 0 && <>
        <div className={`table-wrap${busy ? ' is-updating' : ''}`}>
          <table className="data-table users-table">
            <caption className="sr-only">Accounts sorted by creation date, with newest first</caption>
            <thead><tr><th scope="col">Username</th><th scope="col">Role</th><th scope="col">Created</th><th scope="col">Status</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>{data.items.map((account) => <UserRow key={account.id} account={account} currentUserId={user?.id} pending={pendingUserId === account.id} onToggle={() => void changeStatus(account)} />)}</tbody>
          </table>
        </div>
        <div className="mobile-record-list user-mobile-list">{data.items.map((account) => <UserCard key={account.id} account={account} currentUserId={user?.id} pending={pendingUserId === account.id} onToggle={() => void changeStatus(account)} />)}</div>
        <Pagination page={Math.floor(offset / limit) + 1} pageSize={limit} total={data.total} onPage={setPage} onPageSize={setPageSize} />
      </>}
    </section>
    <p className="user-management-note">Deactivation immediately blocks REST access and revokes refresh sessions. The API prevents self-deactivation and serializes administrator deactivation checks so an active administrator remains.</p>
  </div>
}

function UserStatus({ active }: { active: boolean }) {
  return <span className={`status-badge account-status account-status-${active ? 'active' : 'inactive'}`}><i aria-hidden="true" />{active ? 'Active' : 'Inactive'}</span>
}

function AccountAction({ account, currentUserId, pending, onToggle }: {
  account: User
  currentUserId?: string
  pending: boolean
  onToggle: () => void
}) {
  const ownActiveAccount = account.id === currentUserId && account.is_active
  return <button className={`account-toggle${account.is_active ? ' account-toggle-disable' : ' account-toggle-enable'}`} type="button" disabled={pending || ownActiveAccount} onClick={onToggle} aria-label={`${account.is_active ? 'Deactivate' : 'Activate'} ${account.username}`}>
    {pending ? 'Saving…' : ownActiveAccount ? 'Current account' : account.is_active ? 'Deactivate' : 'Activate'}
  </button>
}

function UserRow({ account, currentUserId, pending, onToggle }: {
  account: User
  currentUserId?: string
  pending: boolean
  onToggle: () => void
}) {
  return <tr>
    <td className="managed-username">{account.username}</td>
    <td><span className={`role-badge role-badge-${account.role}`}>{account.role}</span></td>
    <td><time dateTime={account.created_at}>{formatDate(account.created_at)}</time></td>
    <td><UserStatus active={account.is_active} /></td>
    <td className="row-actions"><AccountAction account={account} currentUserId={currentUserId} pending={pending} onToggle={onToggle} /></td>
  </tr>
}

function UserCard({ account, currentUserId, pending, onToggle }: {
  account: User
  currentUserId?: string
  pending: boolean
  onToggle: () => void
}) {
  return <article className="mobile-record-card managed-user-card">
    <div className="mobile-record-top"><span className={`role-badge role-badge-${account.role}`}>{account.role}</span><UserStatus active={account.is_active} /></div>
    <h3 className="managed-username">{account.username}</h3>
    <time dateTime={account.created_at}>{formatDate(account.created_at)}</time>
    <div className="mobile-card-actions"><span className="detail-label">Account access</span><AccountAction account={account} currentUserId={currentUserId} pending={pending} onToggle={onToggle} /></div>
  </article>
}
