import { create } from 'zustand'
import { toast } from 'react-hot-toast'
import { login as apiLogin, register as apiRegister, getApiErrorMessage } from '../services'
import { useProjectStore } from './useProjectStore'

const getInitialUser = () => {
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
  token: localStorage.getItem('archigen_token') || null,
  isAuthed: !!(localStorage.getItem('archigen_token') && getInitialUser()),

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

  logout: () => {
    useAuthStore.getState().clearSession()
    toast.success('Signed out successfully')
  },
}))
