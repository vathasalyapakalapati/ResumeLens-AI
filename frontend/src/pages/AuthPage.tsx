import { Aperture, CheckCircle2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { ThemeToggle } from '@/components/ThemeToggle'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const PITCH = [
  'Every score backed by a line in your resume',
  'Honest rewrites, kept apart from real skill gaps',
  'Track each resume version and watch your score climb',
]

/** Split-screen login / sign-up. The form is wired to the API in phase 2. */
export function AuthPage({ mode }: { mode: 'login' | 'signup' }) {
  const signup = mode === 'signup'
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
        <form className="w-full max-w-sm space-y-4" onSubmit={(e) => e.preventDefault()}>
          <div className="space-y-1">
            <h2 className="text-2xl font-semibold">{signup ? 'Create your account' : 'Welcome back'}</h2>
            <p className="text-sm text-muted-foreground">
              {signup ? 'Start scoring your resume in a minute.' : 'Log in to see your reports.'}
            </p>
          </div>
          {signup && <Input placeholder="Full name" autoComplete="name" />}
          <Input type="email" placeholder="Email" autoComplete="email" />
          <Input type="password" placeholder="Password" autoComplete={signup ? 'new-password' : 'current-password'} />
          <Button className="w-full" type="submit">
            {signup ? 'Sign up' : 'Log in'}
          </Button>
          <p className="text-center text-sm text-muted-foreground">
            {signup ? 'Already have an account? ' : 'New here? '}
            <Link to={signup ? '/login' : '/signup'} className="font-medium text-primary hover:underline">
              {signup ? 'Log in' : 'Create an account'}
            </Link>
          </p>
          <p className="text-center text-xs text-muted-foreground">
            Sign-in goes live in phase 2. <Link to="/dashboard" className="underline">Preview the app</Link>
          </p>
        </form>
      </section>
    </div>
  )
}
