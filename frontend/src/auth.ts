import type { User } from './types'

const TOKEN_KEY = 'taller_access_token'
const USER_KEY = 'taller_user'

function tokenExpiration(token: string): Date | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
    return typeof payload.exp === 'number' ? new Date(payload.exp * 1000) : null
  } catch {
    return null
  }
}

export const auth = {
  token: () => sessionStorage.getItem(TOKEN_KEY),
  user(): User | null {
    const token = auth.token(); const value = sessionStorage.getItem(USER_KEY)
    if (!token || !value) return null
    const expires = tokenExpiration(token)
    if (expires && expires.getTime() <= Date.now()) { auth.clear(); return null }
    return JSON.parse(value)
  },
  expiresAt(): Date | null { const token = auth.token(); return token ? tokenExpiration(token) : null },
  set(token: string, user: User) { sessionStorage.setItem(TOKEN_KEY, token); sessionStorage.setItem(USER_KEY, JSON.stringify(user)) },
  clear() { sessionStorage.removeItem(TOKEN_KEY); sessionStorage.removeItem(USER_KEY) }
}
