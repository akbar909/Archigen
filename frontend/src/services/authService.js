import { apiClient } from './apiClient'

export async function register(payload) {
  const { data } = await apiClient.post('/auth/register', payload)
  return data
}

export async function login(payload) {
  const { data } = await apiClient.post('/auth/login', payload)
  return data
}
