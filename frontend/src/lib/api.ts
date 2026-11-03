import axios from 'axios'

// Same-origin in dev (Vite proxy) and in production (FastAPI serves the app),
// so cookies ride along automatically.
export const api = axios.create({ baseURL: '/api', withCredentials: true })

export interface Health {
  status: string
  database: string
  pgvector: string | null
}

export const getHealth = () => api.get<Health>('/health').then((r) => r.data)
