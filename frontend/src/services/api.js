import axios from 'axios'

const API_BASE ='http://localhost:5000/api'

const client = axios.create({
  baseURL: API_BASE,
  timeout: 20000,
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('archigen_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export async function register(payload) {
  const { data } = await client.post('/auth/register', payload)
  return data
}

export async function login(payload) {
  const { data } = await client.post('/auth/login', payload)
  return data
}

export async function generateDesign(payload) {
  const { data } = await client.post('/chat', payload)
  return data
}

export async function fetchHistory() {
  const { data } = await client.get('/history')
  return data
}

export async function fetchDesign(id) {
  const { data } = await client.get(`/design/${id}`)
  return data
}
