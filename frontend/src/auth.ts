import type { User } from './types'

const TOKEN_KEY = 'taller_access_token'
const USER_KEY = 'taller_user'
export const auth = {
  token: () => sessionStorage.getItem(TOKEN_KEY),
  user: (): User | null => { const value = sessionStorage.getItem(USER_KEY); return value ? JSON.parse(value) : null },
  set(token: string, user: User) { sessionStorage.setItem(TOKEN_KEY, token); sessionStorage.setItem(USER_KEY, JSON.stringify(user)) },
  clear() { sessionStorage.removeItem(TOKEN_KEY); sessionStorage.removeItem(USER_KEY) }
}
