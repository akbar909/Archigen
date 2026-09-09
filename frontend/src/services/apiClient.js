import axios from 'axios'

const API_BASE = 'http://localhost:7860/api'
// const API_BASE = 'https://akbar909-archigen.hf.space/api'

export const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 180000,
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('archigen_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

let isHandling401 = false
let unauthorizedHandler = null

export function setUnauthorizedHandler(fn) {
  unauthorizedHandler = fn
}

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = error?.config?.url || ''
    const isAuthRoute = url.includes('/auth/login') || url.includes('/auth/register')

    if (error?.response?.status === 401 && !isAuthRoute) {
      if (!isHandling401) {
        isHandling401 = true
        if (typeof unauthorizedHandler === 'function') {
          unauthorizedHandler()
        } else {
          localStorage.removeItem('archigen_token')
          localStorage.removeItem('archigen_user')
          window.location.href = '/auth'
        }
        setTimeout(() => {
          isHandling401 = false
        }, 1500)
      }
    }
    return Promise.reject(error)
  }
)

export function getGenerationErrorMessage(err) {
  const status = err?.response?.status
  const detail = err?.response?.data?.error || err?.message || 'Generation failed'

  if (status === 403 || /permission denied|consumer.*suspended|gemini api error 403/i.test(detail)) {
    return 'AI service is unavailable right now. Please try again later.'
  }

  return detail
}

export function getApiErrorMessage(err, fallback = 'Operation failed') {
  return err?.response?.data?.error || err?.message || fallback
}
