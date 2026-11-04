import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  deleteInterview,
  getInterview,
  getInterviewConfig,
  type Interviewer,
  listAllInterviews,
  listInterviews,
  startInterview,
} from '@/lib/api'
import { deleteRecording } from '@/lib/recordings'

export const useInterviewConfig = () =>
  useQuery({ queryKey: ['interview-config'], queryFn: getInterviewConfig, staleTime: 5 * 60_000 })

export const useInterviews = (analysisId: string) =>
  useQuery({ queryKey: ['interviews', 'for', analysisId], queryFn: () => listInterviews(analysisId) })

export const useAllInterviews = () => useQuery({ queryKey: ['interviews', 'all'], queryFn: listAllInterviews })

export const useInterview = (id: string) => useQuery({ queryKey: ['interviews', id], queryFn: () => getInterview(id) })

export function useStartInterview(analysisId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { question_count: number; interviewer: Interviewer }) => startInterview(analysisId, body),
    onSuccess: (iv) => {
      qc.setQueryData(['interviews', iv.id], iv)
      qc.invalidateQueries({ queryKey: ['interviews', 'for', analysisId] })
      qc.invalidateQueries({ queryKey: ['interviews', 'all'] })
    },
  })
}

export function useDeleteInterview() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await deleteInterview(id)
      await deleteRecording(id).catch(() => undefined)
    },
    onSuccess: (_, id) => {
      qc.removeQueries({ queryKey: ['interviews', id] })
      qc.invalidateQueries({ queryKey: ['interviews', 'for'] })
      qc.invalidateQueries({ queryKey: ['interviews', 'all'] })
    },
  })
}

export const clock = (seconds: number | null | undefined) => {
  const s = Math.max(0, Math.round(seconds ?? 0))
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}
