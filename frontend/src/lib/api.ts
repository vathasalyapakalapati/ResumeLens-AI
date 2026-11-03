import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'

// Same-origin in dev (Vite proxy) and in production (FastAPI serves the app),
// so cookies ride along automatically.
export const api = axios.create({ baseURL: '/api', withCredentials: true })

// ---------- silent refresh ----------
// The access cookie lives 15 minutes. When a call comes back 401, try /auth/refresh once
// (shared by every request that failed at the same moment), then replay the call.

let refreshing: Promise<void> | null = null
const NO_RETRY = ['/auth/login', '/auth/signup', '/auth/refresh', '/auth/logout']

api.interceptors.response.use(undefined, async (error: AxiosError) => {
  const config = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined
  if (error.response?.status !== 401 || !config || config._retried || NO_RETRY.includes(config.url ?? '')) {
    throw error
  }
  config._retried = true
  refreshing ??= api
    .post('/auth/refresh')
    .then(() => undefined)
    .finally(() => {
      refreshing = null
    })
  try {
    await refreshing
  } catch {
    throw error // refresh failed: surface the original 401
  }
  return api(config)
})

/** A readable message from any API error (FastAPI sends `detail` as a string or a list). */
export function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail.length) {
      const first = detail[0] as { loc?: unknown[]; msg?: string }
      const field = first.loc?.[first.loc.length - 1]
      if (field === 'email') return 'Please enter a valid email address.'
      if (field === 'password') return 'Password must be 8 to 128 characters.'
      if (field === 'full_name') return 'Name must be 120 characters or fewer.'
      return first.msg ?? 'Please check the form.'
    }
    if (!err.response) return 'Cannot reach the server. Is the backend running?'
  }
  return 'Something went wrong. Please try again.'
}

// ---------- endpoints ----------

export interface Health {
  status: string
  database: string
  pgvector: string | null
}

export interface User {
  id: string
  email: string
  full_name: string | null
  is_verified: boolean
  created_at: string
}

export const getHealth = () => api.get<Health>('/health').then((r) => r.data)

export const getMe = () => api.get<User>('/auth/me').then((r) => r.data)
export const login = (body: { email: string; password: string }) =>
  api.post<User>('/auth/login', body).then((r) => r.data)
export const signup = (body: { email: string; password: string; full_name?: string }) =>
  api.post<User>('/auth/signup', body).then((r) => r.data)
export const logout = () => api.post('/auth/logout').then(() => undefined)

// ---------- library: resumes and job descriptions ----------

export interface Line {
  id: string // "L1", "L2", ...
  text: string
}

export interface ResumeSummary {
  id: string
  title: string
  file_name: string | null
  version: number
  line_count: number
  created_at: string
}

export interface ResumeDetail extends ResumeSummary {
  format: string
  pages: number | null
  warnings: string[]
  lines: Line[]
}

export interface JdSummary {
  id: string
  title: string | null
  company: string | null
  source: 'upload' | 'paste'
  line_count: number
  created_at: string
}

export interface JdDetail extends JdSummary {
  lines: Line[]
}

const form = (fields: Record<string, string | Blob | undefined>) => {
  const fd = new FormData()
  for (const [k, v] of Object.entries(fields)) if (v) fd.append(k, v)
  return fd
}

export const listResumes = () => api.get<ResumeSummary[]>('/resumes').then((r) => r.data)
export const getResume = (id: string) => api.get<ResumeDetail>(`/resumes/${id}`).then((r) => r.data)
export const uploadResume = (file: File, title?: string) =>
  api.post<ResumeDetail>('/resumes', form({ file, title })).then((r) => r.data)
export const deleteResume = (id: string) => api.delete(`/resumes/${id}`).then(() => undefined)

/** Fetch through axios (so an expired session refreshes) and save it with its original name. */
export async function downloadResume(id: string, fileName: string) {
  const res = await api.get<Blob>(`/resumes/${id}/file`, { responseType: 'blob' })
  const url = URL.createObjectURL(res.data)
  const a = Object.assign(document.createElement('a'), { href: url, download: fileName })
  a.click()
  URL.revokeObjectURL(url)
}

export const listJds = () => api.get<JdSummary[]>('/jds').then((r) => r.data)
export const getJd = (id: string) => api.get<JdDetail>(`/jds/${id}`).then((r) => r.data)
export const pasteJd = (body: { text: string; title?: string; company?: string }) =>
  api.post<JdDetail>('/jds', body).then((r) => r.data)
export const uploadJd = (file: File, title?: string, company?: string) =>
  api.post<JdDetail>('/jds/upload', form({ file, title, company })).then((r) => r.data)
export const deleteJd = (id: string) => api.delete(`/jds/${id}`).then(() => undefined)

// ---------- analyses ----------

export type ReqStatus = 'met' | 'partial' | 'missing'

export interface ReportRequirement {
  id: string
  text: string
  jd_line: string | null
  importance: 'must' | 'nice'
  category: 'skill' | 'experience' | 'education' | 'other'
  status: ReqStatus
  evidence: string[]
  note: string
}

export interface Report {
  verdict: string
  summary: string
  engine: string
  warnings: string[]
  resume: { id: string; title: string; file_name: string | null }
  jd: { id: string; title: string | null; company: string | null }
  requirements: ReportRequirement[]
  keywords: { matched: string[]; missing: string[] }
  resume_lines: Record<string, string>
  jd_lines: Record<string, string>
}

export type SubScores = Record<
  'must_have' | 'nice_to_have' | 'skills' | 'experience' | 'education' | 'keywords',
  number | null
>

export interface AnalysisSummary {
  id: string
  status: 'queued' | 'running' | 'done' | 'failed'
  overall_score: number | null
  verdict: string | null
  resume_id: string | null
  resume_title: string | null
  jd_id: string | null
  jd_title: string | null
  jd_company: string | null
  created_at: string
}

export interface AnalysisDetail extends AnalysisSummary {
  current_step: 'parse' | 'match' | 'score' | null
  error: string | null
  sub_scores: SubScores | null
  report: Report | null
  model: string | null
  completed_at: string | null
}

export const listAnalyses = () => api.get<AnalysisSummary[]>('/analyses').then((r) => r.data)
export const getAnalysis = (id: string) => api.get<AnalysisDetail>(`/analyses/${id}`).then((r) => r.data)
export const startAnalysis = (body: { resume_id: string; jd_id: string }) =>
  api.post<AnalysisDetail>('/analyses', body).then((r) => r.data)
export const deleteAnalysis = (id: string) => api.delete(`/analyses/${id}`).then(() => undefined)
