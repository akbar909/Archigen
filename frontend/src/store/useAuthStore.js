import { create } from 'zustand'
import { toast } from 'react-hot-toast'
import { login as apiLogin, register as apiRegister, getApiErrorMessage, setUnauthorizedHandler } from '../services'
import { useProjectStore } from './useProjectStore'

export function isTokenValid(token) {
  if (!token || typeof token !== 'string') return false
  const parts = token.split('.')
  if (parts.length !== 3) return false
  try {
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
    const payload = JSON.parse(jsonPayload)
    if (!payload.exp) return true
    const now = Math.floor(Date.now() / 1000)
    return payload.exp > now + 5
  } catch {
    return false
  }
}

const getInitialToken = () => {
  const token = localStorage.getItem('archigen_token')
  if (!token) return null
  if (!isTokenValid(token)) {
    localStorage.removeItem('archigen_token')
    localStorage.removeItem('archigen_user')
    return null
  }
  return token
}

const getInitialUser = () => {
  const token = getInitialToken()
  if (!token) return null
  const stored = localStorage.getItem('archigen_user')
  if (!stored || stored === 'undefined') return null
  try {
    return JSON.parse(stored)
  } catch {
    return null
  }
}

export const useAuthStore = create((set) => ({
  user: getInitialUser(),
  token: getInitialToken(),
  isAuthed: !!(getInitialToken() && getInitialUser()),

  storeSession: (data) => {
    localStorage.setItem('archigen_token', data.token)
    const userData = data.user || { token: data.token }
    localStorage.setItem('archigen_user', JSON.stringify(userData))
    set({ user: userData, token: data.token, isAuthed: true })
  },

  clearSession: () => {
    localStorage.removeItem('archigen_token')
    localStorage.removeItem('archigen_user')
    set({ user: null, token: null, isAuthed: false })
    useProjectStore.getState().reset()
  },

  login: async (payload) => {
    try {
      useProjectStore.getState().reset()
      const data = await apiLogin(payload)
      useAuthStore.getState().storeSession(data)
      toast.success('Welcome back! 👋')
      return { success: true, data }
    } catch (err) {
      const errorMsg = getApiErrorMessage(err, 'Authentication failed')
      toast.error(errorMsg)
      return { success: false, error: errorMsg }
    }
  },

  register: async (payload) => {
    try {
      useProjectStore.getState().reset()
      const data = await apiRegister(payload)
      useAuthStore.getState().storeSession(data)
      toast.success('Account created! Welcome to ArchiGen 🎉')
      return { success: true, data }
    } catch (err) {
      const errorMsg = getApiErrorMessage(err, 'Registration failed')
      toast.error(errorMsg)
      return { success: false, error: errorMsg }
    }
  },

  logout: (options = {}) => {
    const isExpired = options?.expired === true
    useAuthStore.getState().clearSession()

    if (isExpired) {
      toast.error('Session expired. Please sign in again.')
    } else {
      toast.success('Signed out successfully')
    }

    const currentPath = window.location.pathname + window.location.search
    if (isExpired && currentPath && !currentPath.startsWith('/auth') && currentPath !== '/') {
      const redirectUrl = `/auth?redirect=${encodeURIComponent(currentPath)}`
      if (window.location.pathname !== '/auth') {
        window.location.href = redirectUrl
      }
    } else if (!window.location.pathname.startsWith('/auth')) {
      window.location.href = '/auth'
    }
  },
}))

setUnauthorizedHandler(() => {
  useAuthStore.getState().logout({ expired: true })
})
