import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { deleteAnalysis, getAnalysis, listAnalyses, startAnalysis } from '@/lib/api'

export const useAnalyses = () => useQuery({ queryKey: ['analyses'], queryFn: listAnalyses })

/** One analysis; polls every second while it is still being scored. */
export function useAnalysis(id: string) {
  return useQuery({
    queryKey: ['analyses', id],
    queryFn: () => getAnalysis(id),
    refetchInterval: (q) => (q.state.data && ['queued', 'running'].includes(q.state.data.status) ? 1000 : false),
  })
}

export function useStartAnalysis() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: startAnalysis,
    onSuccess: (a) => {
      qc.setQueryData(['analyses', a.id], a)
      qc.invalidateQueries({ queryKey: ['analyses'], exact: true })
    },
  })
}

export function useDeleteAnalysis() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteAnalysis,
    onSuccess: (_, id) => {
      qc.removeQueries({ queryKey: ['analyses', id] })
      qc.invalidateQueries({ queryKey: ['analyses'], exact: true })
    },
  })
}

/** Text colour class for a 0-100 score. */
export const scoreTone = (score: number | null | undefined) =>
  score == null ? 'text-muted-foreground' : score >= 70 ? 'text-strong' : score >= 45 ? 'text-partial' : 'text-weak'

export const scoreBg = (score: number | null | undefined) =>
  score == null ? 'bg-muted' : score >= 70 ? 'bg-strong' : score >= 45 ? 'bg-partial' : 'bg-weak'

export const scoreStroke = (score: number) => (score >= 70 ? 'stroke-strong' : score >= 45 ? 'stroke-partial' : 'stroke-weak')
