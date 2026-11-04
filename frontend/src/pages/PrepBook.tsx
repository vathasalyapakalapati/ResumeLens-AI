import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  CircleDashed,
  Download,
  FileText,
  Loader2,
  Mic,
  XCircle,
} from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { downloadPrep, errorMessage, type PrepCategoryKey, type PrepContent, type PrepDetail, type PrepQuestion } from '@/lib/api'
import { formatDate } from '@/lib/library'
import { usePrepBook } from '@/lib/prep'
import { cn } from '@/lib/utils'

const STEPS: { key: PrepCategoryKey; label: string }[] = [
  { key: 'technical', label: 'Technical' },
  { key: 'system_design', label: 'System design' },
  { key: 'culture', label: 'Cultural fit' },
  { key: 'behavioral', label: 'Behavioural' },
]

const DIFFICULTY: Record<PrepQuestion['difficulty'], string> = {
  easy: 'bg-strong/15 text-strong',
  medium: 'bg-partial/15 text-partial',
  hard: 'bg-weak/15 text-weak',
}

function Progress({ p }: { p: PrepDetail }) {
  const current = STEPS.findIndex((s) => s.key === p.current_step)
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-6 py-12">
        <Loader2 className="size-8 animate-spin text-primary" />
        <p className="text-sm text-muted-foreground">Writing your prep book…</p>
        <ol className="space-y-3">
          {STEPS.map((s, i) => (
            <li key={s.key} className="flex items-center gap-3 text-sm">
              {i < current ? (
                <CheckCircle2 className="size-5 text-strong" />
              ) : i === current ? (
                <Loader2 className="size-5 animate-spin text-primary" />
              ) : (
                <CircleDashed className="size-5 text-muted-foreground" />
              )}
              <span className={cn(i > current && 'text-muted-foreground')}>{s.label} questions</span>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  )
}

function QuestionCard({ q, n, lines, open, onToggle }: { q: PrepQuestion; n: number; lines: Record<string, string>; open: boolean; onToggle: () => void }) {
  return (
    <li className="rounded-xl border bg-card">
      <button onClick={onToggle} aria-expanded={open} className="flex w-full items-start gap-3 px-4 py-3 text-left">
        <span className="mt-0.5 w-6 shrink-0 text-sm font-semibold text-muted-foreground">{n}.</span>
        <span className="min-w-0 flex-1">
          <span className="block font-medium leading-snug">{q.question}</span>
          <span className="mt-1.5 flex flex-wrap gap-1.5">
            <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium capitalize', DIFFICULTY[q.difficulty])}>{q.difficulty}</span>
            {q.focus && <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">{q.focus}</span>}
            {q.evidence.length > 0 && <span className="rounded-full bg-accent px-2 py-0.5 text-xs text-primary">uses your resume</span>}
          </span>
        </span>
        <ChevronDown className={cn('mt-1 size-4 shrink-0 text-muted-foreground transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <div className="space-y-3 border-t px-4 py-3 pl-13 text-sm">
          {q.why && (
            <p>
              <span className="font-medium">What they're looking for: </span>
              <span className="text-muted-foreground">{q.why}</span>
            </p>
          )}
          {q.approach.length > 0 && (
            <div>
              <p className="font-medium">How to answer</p>
              <ul className="mt-1 list-disc space-y-1 pl-5">{q.approach.map((a) => <li key={a}>{a}</li>)}</ul>
            </div>
          )}
          {q.evidence.length > 0 && (
            <div>
              <p className="font-medium">From your resume</p>
              <ul className="mt-1 space-y-1">
                {q.evidence.map((e) => (
                  <li key={e} className="flex gap-2 rounded-md bg-muted/60 px-2 py-1">
                    <span className="shrink-0 font-mono text-xs leading-5 text-muted-foreground">{e}</span>
                    <span>{lines[e] ?? ''}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </li>
  )
}

function Book({ p, c }: { p: PrepDetail; c: PrepContent }) {
  const [tab, setTab] = useState<PrepCategoryKey | 'all'>('all')
  const [open, setOpen] = useState<Set<string>>(new Set())
  const sections = c.categories.filter((s) => tab === 'all' || s.key === tab)
  const allIds = c.categories.flatMap((s) => s.questions.map((q) => q.id))
  const allOpen = open.size === allIds.length
  const toggle = (id: string) =>
    setOpen((o) => {
      const next = new Set(o)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="space-y-3 pt-6 text-sm">
          <p className="leading-relaxed">{c.overview}</p>
          <ul className="list-disc space-y-1 pl-5 text-muted-foreground">{c.tips.map((t) => <li key={t}>{t}</li>)}</ul>
          <p className="text-xs text-muted-foreground">
            Generated {p.completed_at && formatDate(p.completed_at)} · by {p.engine === 'built-in' ? 'built-in templates (no AI key)' : p.engine}
          </p>
        </CardContent>
      </Card>
      {c.warnings.map((w) => (
        <p key={w} className="flex items-start gap-2 rounded-md border border-partial/50 bg-partial/10 px-3 py-2 text-sm">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-partial" /> {w}
        </p>
      ))}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="tablist" className="inline-flex flex-wrap gap-1 rounded-lg bg-muted p-1">
          {[{ key: 'all' as const, title: 'All', count: allIds.length }, ...c.categories.map((s) => ({ key: s.key, title: s.title, count: s.questions.length }))].map((t) => (
            <button
              key={t.key}
              role="tab"
              aria-selected={tab === t.key}
              onClick={() => setTab(t.key)}
              className={cn('rounded-md px-3 py-1.5 text-sm text-muted-foreground', tab === t.key && 'bg-card text-foreground shadow-sm')}
            >
              {t.title} <span className="text-xs opacity-70">{t.count}</span>
            </button>
          ))}
        </div>
        <Button variant="ghost" size="sm" onClick={() => setOpen(allOpen ? new Set() : new Set(allIds))}>
          {allOpen ? 'Collapse all' : 'Show all answers'}
        </Button>
      </div>

      {sections.map((s) => (
        <section key={s.key} className="space-y-3">
          <div>
            <h2 className="text-lg font-semibold">{s.title}</h2>
            <p className="text-sm text-muted-foreground">{s.description}</p>
          </div>
          <ol className="space-y-2">
            {s.questions.map((q, i) => (
              <QuestionCard key={q.id} q={q} n={i + 1} lines={c.resume_lines} open={open.has(q.id)} onToggle={() => toggle(q.id)} />
            ))}
          </ol>
        </section>
      ))}
    </div>
  )
}

export function PrepBook() {
  const { id = '' } = useParams()
  const prep = usePrepBook(id)
  const [busy, setBusy] = useState<'pdf' | 'md' | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const p = prep.data

  const download = async (format: 'pdf' | 'md') => {
    setBusy(format)
    setErr(null)
    try {
      await downloadPrep(id, format)
    } catch (e) {
      setErr(errorMessage(e))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-6">
      <Link to="/prep" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Interview Prep
      </Link>
      {prep.isPending && <Loader2 className="size-6 animate-spin text-muted-foreground" />}
      {prep.isError && <p className="text-sm text-weak">{errorMessage(prep.error)}</p>}
      {p && (
        <>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold">
                Prep book: {p.role ?? 'Untitled job'}
                {p.company && ` at ${p.company}`}
              </h1>
              <p className="text-sm text-muted-foreground">
                Resume: {p.resume_title ?? 'unknown'} · match score {p.match_score ?? 'n/a'} ·{' '}
                <Link to={`/reports/${p.analysis_id}`} className="text-primary hover:underline">
                  view report
                </Link>
              </p>
            </div>
            {p.status === 'done' && (
              <div className="flex flex-wrap gap-2">
                <Button size="sm" onClick={() => download('pdf')} disabled={busy !== null}>
                  {busy === 'pdf' ? <Loader2 className="animate-spin" /> : <Download />} Download PDF
                </Button>
                <Button variant="outline" size="sm" onClick={() => download('md')} disabled={busy !== null}>
                  {busy === 'md' ? <Loader2 className="animate-spin" /> : <FileText />} Markdown
                </Button>
                <Link to={`/interviews?analysis=${p.analysis_id}`} className={buttonVariants({ variant: 'outline', size: 'sm' })}>
                  <Mic /> Practise in AI interview
                </Link>
              </div>
            )}
          </div>
          {err && <p className="text-sm text-weak">{err}</p>}
          {['queued', 'running'].includes(p.status) && <Progress p={p} />}
          {p.status === 'failed' && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base text-weak">
                  <XCircle className="size-5" /> This prep book couldn't be generated
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                {p.error}{' '}
                <Link to={`/prep?analysis=${p.analysis_id}`} className="text-primary hover:underline">
                  Try again
                </Link>
              </CardContent>
            </Card>
          )}
          {p.status === 'done' && p.content && <Book p={p} c={p.content} />}
        </>
      )}
    </div>
  )
}
