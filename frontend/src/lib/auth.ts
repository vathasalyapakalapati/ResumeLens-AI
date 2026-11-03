import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { getMe, login, logout, signup, type User } from '@/lib/api'

const ME = ['me'] as const

/** The signed-in user, `null` when logged out, `undefined` while checking. */
export function useMe() {
  const query = useQuery({
    queryKey: ME,
    queryFn: async (): Promise<User | null> => {
      try {
        return await getMe()
      } catch (err) {
        if (axios.isAxiosError(err) && err.response?.status === 401) return null
        throw err
      }
    },
    staleTime: 5 * 60_000,
    retry: false,
  })
  return { ...query, user: query.data }
}

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: login, onSuccess: (user) => qc.setQueryData(ME, user) })
}

export function useSignup() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: signup, onSuccess: (user) => qc.setQueryData(ME, user) })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: logout,
    onSettled: () => {
      qc.clear() // drop every cached query from this user
      qc.setQueryData(ME, null)
    },
  })
}

/** "Ada" from "Ada Lovelace", else the part of the email before @. */
export const firstName = (u: User) => u.full_name?.split(/\s+/)[0] || u.email.split('@')[0]

export const initials = (u: User) => {
  const parts = (u.full_name ?? '').split(/\s+/).filter(Boolean)
  return (parts.length ? parts.slice(0, 2).map((p) => p[0]) : [u.email[0]]).join('').toUpperCase()
}
