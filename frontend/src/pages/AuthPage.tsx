import { Aperture, CheckCircle2, Loader2 } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ThemeToggle } from '@/components/ThemeToggle'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { errorMessage } from '@/lib/api'
import { useLogin, useMe, useSignup } from '@/lib/auth'

const PITCH = [
  'Every score backed by a line in your resume',
  'Honest rewrites, kept apart from real skill gaps',
  'Track each resume version and watch your score climb',
]

/** Split-screen login / sign-up. */
export function AuthPage({ mode }: { mode: 'login' | 'signup' }) {
  const signup = mode === 'signup'
  const { user } = useMe()
  const loginMutation = useLogin()
  const signupMutation = useSignup()
  const mutation = signup ? signupMutation : loginMutation
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/analyze'

  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  // Already signed in (e.g. opened /login in a new tab): skip the form.
  if (user) return <Navigate to={from} replace />

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const onSuccess = () => navigate(from, { replace: true })
    if (signup) signupMutation.mutate({ email, password, full_name: fullName || undefined }, { onSuccess })
    else loginMutation.mutate({ email, password }, { onSuccess })
  }

  return (
    <div className="grid min-h-screen md:grid-cols-2">
      <section className="hidden flex-col justify-between bg-primary p-10 text-primary-foreground md:flex">
        <div className="flex items-center gap-2 text-lg font-semibold">
          <Aperture className="size-6" /> ResumeLens AI
        </div>
        <div className="space-y-6">
          <h1 className="text-4xl font-semibold leading-tight">See your resume the way a recruiter and an ATS see it.</h1>
          <ul className="space-y-3">
            {PITCH.map((p) => (
              <li key={p} className="flex items-start gap-2 opacity-90">
                <CheckCircle2 className="mt-0.5 size-5 shrink-0" /> {p}
              </li>
            ))}
          </ul>
        </div>
        <p className="text-sm opacity-70">Built with React, FastAPI, PostgreSQL + pgvector and LangGraph.</p>
      </section>

      <section className="relative flex items-center justify-center p-6">
        <div className="absolute right-4 top-4">
          <ThemeToggle />
        </div>
        <form className="w-full max-w-sm space-y-4" onSubmit={submit}>
          <div className="space-y-1">
            <h2 className="text-2xl font-semibold">{signup ? 'Create your account' : 'Welcome back'}</h2>
            <p className="text-sm text-muted-foreground">
              {signup ? 'Start scoring your resume in a minute.' : 'Log in to see your reports.'}
            </p>
          </div>
          {signup && (
            <Input
              placeholder="Full name"
              autoComplete="name"
              maxLength={120}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          )}
          <Input
            type="email"
            placeholder="Email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Input
            type="password"
            placeholder={signup ? 'Password (at least 8 characters)' : 'Password'}
            autoComplete={signup ? 'new-password' : 'current-password'}
            required
            minLength={signup ? 8 : undefined}
            maxLength={128}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {mutation.isError && (
            <p role="alert" className="rounded-md border border-weak/40 bg-weak/10 px-3 py-2 text-sm text-weak">
              {errorMessage(mutation.error)}
            </p>
          )}
          <Button className="w-full" type="submit" disabled={mutation.isPending}>
            {mutation.isPending && <Loader2 className="animate-spin" />}
            {signup ? 'Sign up' : 'Log in'}
          </Button>
          <p className="text-center text-sm text-muted-foreground">
            {signup ? 'Already have an account? ' : 'New here? '}
            <Link
              to={signup ? '/login' : '/signup'}
              state={location.state}
              className="font-medium text-primary hover:underline"
            >
              {signup ? 'Log in' : 'Create an account'}
            </Link>
          </p>
        </form>
      </section>
    </div>
  )
}
