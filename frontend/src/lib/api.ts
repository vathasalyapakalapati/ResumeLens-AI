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

// ---------- AI interviews ----------

export type Interviewer = 'maya' | 'james'

export interface InterviewTurn {
  role: 'interviewer' | 'candidate'
  kind: 'question' | 'follow_up' | 'closing' | 'answer'
  q: number
  text: string
  t: number // seconds since the recording started
}

export interface InterviewFeedback {
  overall_score: number | null
  summary: string
  strengths: string[]
  improvements: string[]
  questions: { number: number; rating: number | null; comment: string }[]
  engine: string
}

export interface InterviewSummary {
  id: string
  analysis_id: string
  status: 'active' | 'completed'
  interviewer: Interviewer
  question_count: number
  answered: number
  overall_score: number | null
  duration_seconds: number | null
  created_at: string
}

export interface InterviewDetail extends InterviewSummary {
  interviewer_name: string
  interviewer_title: string
  candidate_name: string
  current_question: number
  done: boolean
  turns: InterviewTurn[]
  questions: string[]
  feedback: InterviewFeedback | null
  engine: string
  role: string | null
  company: string | null
  resume_title: string | null
}

export interface InterviewConfig {
  ai: boolean
  transcription: 'groq' | 'browser'
}

export interface InterviewListItem extends InterviewSummary {
  role: string | null
  company: string | null
  resume_title: string | null
  match_score: number | null
}

export const listAllInterviews = () => api.get<InterviewListItem[]>('/interviews').then((r) => r.data)
export const getInterviewConfig = () => api.get<InterviewConfig>('/interviews/config').then((r) => r.data)
export const listInterviews = (analysisId: string) =>
  api.get<InterviewSummary[]>(`/analyses/${analysisId}/interviews`).then((r) => r.data)
export const startInterview = (analysisId: string, body: { question_count: number; interviewer: Interviewer }) =>
  api.post<InterviewDetail>(`/analyses/${analysisId}/interviews`, body).then((r) => r.data)
export const getInterview = (id: string) => api.get<InterviewDetail>(`/interviews/${id}`).then((r) => r.data)
export const answerInterview = (id: string, body: { text: string; elapsed: number }) =>
  api
    .post<{ turn: InterviewTurn; done: boolean; current_question: number }>(`/interviews/${id}/answer`, body)
    .then((r) => r.data)
export const transcribeAnswer = (id: string, audio: Blob) => {
  const fd = new FormData()
  fd.append('audio', audio, audio.type.includes('mp4') ? 'answer.mp4' : 'answer.webm')
  return api.post<{ text: string }>(`/interviews/${id}/transcribe`, fd).then((r) => r.data.text)
}
export const finishInterview = (id: string, elapsed: number) =>
  api.post<InterviewDetail>(`/interviews/${id}/finish`, { elapsed }).then((r) => r.data)
export const deleteInterview = (id: string) => api.delete(`/interviews/${id}`).then(() => undefined)

/** Download the transcript (.txt or .md) through axios so an expired session refreshes. */
export async function downloadTranscript(id: string, format: 'txt' | 'md') {
  const res = await api.get<Blob>(`/interviews/${id}/transcript`, { params: { format }, responseType: 'blob' })
  const name = /filename="([^"]+)"/.exec(res.headers['content-disposition'] ?? '')?.[1] ?? `interview.${format}`
  saveBlob(res.data, name)
}

export function saveBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob)
  const a = Object.assign(document.createElement('a'), { href: url, download: name })
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

// ---------- interview prep books ----------

export type PrepCategoryKey = 'technical' | 'system_design' | 'culture' | 'behavioral'

export interface PrepQuestion {
  id: string
  category: PrepCategoryKey
  question: string
  why: string
  approach: string[]
  difficulty: 'easy' | 'medium' | 'hard'
  evidence: string[]
  focus: string | null
  requirement: string | null
}

export interface PrepContent {
  role: string
  company: string | null
  resume: string | null
  verdict: string | null
  overview: string
  tips: string[]
  warnings: string[]
  categories: { key: PrepCategoryKey; title: string; description: string; questions: PrepQuestion[] }[]
  resume_lines: Record<string, string>
  generated_at: string
}

export interface PrepSummary {
  id: string
  analysis_id: string
  status: 'queued' | 'running' | 'done' | 'failed'
  per_category: number
  question_count: number
  role: string | null
  company: string | null
  resume_title: string | null
  match_score: number | null
  created_at: string
}

export interface PrepDetail extends PrepSummary {
  current_step: PrepCategoryKey | null
  error: string | null
  engine: string | null
  content: PrepContent | null
  completed_at: string | null
}

export const listPrep = () => api.get<PrepSummary[]>('/prep').then((r) => r.data)
export const getPrep = (id: string) => api.get<PrepDetail>(`/prep/${id}`).then((r) => r.data)
export const createPrep = (analysisId: string, per_category: number) =>
  api.post<PrepDetail>(`/analyses/${analysisId}/prep`, { per_category }).then((r) => r.data)
export const deletePrep = (id: string) => api.delete(`/prep/${id}`).then(() => undefined)

export async function downloadPrep(id: string, format: 'pdf' | 'md') {
  const res = await api.get<Blob>(`/prep/${id}/download`, { params: { format }, responseType: 'blob' })
  const name = /filename="([^"]+)"/.exec(res.headers['content-disposition'] ?? '')?.[1] ?? `interview-prep.${format}`
  saveBlob(res.data, name)
}
