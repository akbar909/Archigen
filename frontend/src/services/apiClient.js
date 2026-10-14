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
  const payload = err?.response?.data || {}
  const detail = payload.error || err?.message || 'Generation failed'

  if (status === 403 || /permission denied|consumer.*suspended|gemini api error 403/i.test(detail)) {
    return 'AI service is unavailable right now. Please try again later.'
  }

  return appendErrorReasons(detail, payload)
}

export function getApiErrorMessage(err, fallback = 'Operation failed') {
  const payload = err?.response?.data || {}
  const detail = payload.error || err?.message || fallback
  return appendErrorReasons(detail, payload)
}

function appendErrorReasons(detail, payload) {
  const reasons = [
    ...(Array.isArray(payload?.refinement?.errors) ? payload.refinement.errors : []),
    ...(Array.isArray(payload?.validation?.critical_errors) ? payload.validation.critical_errors : []),
    ...(Array.isArray(payload?.report?.critical_errors) ? payload.report.critical_errors : []),
  ].filter(Boolean)

  const uniqueReasons = [...new Set(reasons)].filter((reason) => reason !== detail)
  if (uniqueReasons.length === 0) return detail

  const visible = uniqueReasons.slice(0, 3).join(' ')
  const remaining = uniqueReasons.length - 3
  return `${detail} ${visible}${remaining > 0 ? ` (+${remaining} more)` : ''}`
}
