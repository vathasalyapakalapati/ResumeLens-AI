import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  deleteJd,
  deleteResume,
  getJd,
  getResume,
  listJds,
  listResumes,
  pasteJd,
  uploadJd,
  uploadResume,
} from '@/lib/api'

export const useResumes = () => useQuery({ queryKey: ['resumes'], queryFn: listResumes })
export const useResume = (id: string) => useQuery({ queryKey: ['resumes', id], queryFn: () => getResume(id) })
export const useJds = () => useQuery({ queryKey: ['jds'], queryFn: listJds })
export const useJd = (id: string) => useQuery({ queryKey: ['jds', id], queryFn: () => getJd(id) })

export function useUploadResume() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ file, title }: { file: File; title?: string }) => uploadResume(file, title),
    onSuccess: (resume) => {
      qc.setQueryData(['resumes', resume.id], resume)
      qc.invalidateQueries({ queryKey: ['resumes'], exact: true })
    },
  })
}

export function useDeleteResume() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteResume,
    onSuccess: (_, id) => {
      qc.removeQueries({ queryKey: ['resumes', id] })
      qc.invalidateQueries({ queryKey: ['resumes'], exact: true })
    },
  })
}

type JdInput =
  | { kind: 'paste'; text: string; title?: string; company?: string }
  | { kind: 'upload'; file: File; title?: string; company?: string }

export function useAddJd() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: JdInput) =>
      input.kind === 'paste'
        ? pasteJd({ text: input.text, title: input.title, company: input.company })
        : uploadJd(input.file, input.title, input.company),
    onSuccess: (jd) => {
      qc.setQueryData(['jds', jd.id], jd)
      qc.invalidateQueries({ queryKey: ['jds'], exact: true })
    },
  })
}

export function useDeleteJd() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteJd,
    onSuccess: (_, id) => {
      qc.removeQueries({ queryKey: ['jds', id] })
      qc.invalidateQueries({ queryKey: ['jds'], exact: true })
    },
  })
}

const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })
export const formatDate = (iso: string) => dateFormat.format(new Date(iso))
