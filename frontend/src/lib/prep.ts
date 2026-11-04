import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createPrep, deletePrep, getPrep, listPrep } from '@/lib/api'

export const usePrepBooks = () => useQuery({ queryKey: ['prep', 'all'], queryFn: listPrep })

/** One prep book; polls every second while it is being generated. */
export function usePrepBook(id: string) {
  return useQuery({
    queryKey: ['prep', id],
    queryFn: () => getPrep(id),
    refetchInterval: (q) => (q.state.data && ['queued', 'running'].includes(q.state.data.status) ? 1000 : false),
  })
}

export function useCreatePrep(analysisId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (perCategory: number) => createPrep(analysisId, perCategory),
    onSuccess: (p) => {
      qc.setQueryData(['prep', p.id], p)
      qc.invalidateQueries({ queryKey: ['prep', 'all'] })
    },
  })
}

export function useDeletePrep() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deletePrep,
    onSuccess: (_, id) => {
      qc.removeQueries({ queryKey: ['prep', id] })
      qc.invalidateQueries({ queryKey: ['prep', 'all'] })
    },
  })
}
