import { BookOpen, Loader2, Sparkles, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { AnalysisPicker } from '@/components/AnalysisPicker'
import { EmptyState } from '@/components/EmptyState'
import { ListSkeleton } from '@/components/ListSkeleton'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useAnalyses } from '@/lib/analyses'
import { errorMessage } from '@/lib/api'
import { useInterviewConfig } from '@/lib/interviews'
import { formatDate } from '@/lib/library'
import { useCreatePrep, useDeletePrep, usePrepBooks } from '@/lib/prep'

const CATEGORIES = ['Technical', 'System design', 'Cultural fit', 'Behavioural']

function Generate({ analysisId }: { analysisId: string }) {
  const create = useCreatePrep(analysisId)
  const config = useInterviewConfig()
  const navigate = useNavigate()
  const [perCategory, setPerCategory] = useState(6)

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-4">
        <label className="space-y-1.5">
          <span className="block text-xs font-medium text-muted-foreground">Questions per category</span>
          <select value={perCategory} onChange={(e) => setPerCategory(Number(e.target.value))} className="h-9 rounded-md border bg-card px-3 text-sm">
            {[3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
              <option key={n} value={n}>
                {n} each ({n * 4} total)
              </option>
            ))}
          </select>
        </label>
        <Button disabled={create.isPending} onClick={() => create.mutate(perCategory, { onSuccess: (p) => navigate(`/prep/${p.id}`) })}>
          {create.isPending ? <Loader2 className="animate-spin" /> : <Sparkles />} Generate prep book
        </Button>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {CATEGORIES.map((c) => (
          <span key={c} className="rounded-full bg-accent px-2.5 py-0.5 text-xs font-medium text-primary">
            {c}
          </span>
        ))}
      </div>
      {create.isError && <p className="text-sm text-weak">{errorMessage(create.error)}</p>}
      {config.data && !config.data.ai && (
        <p className="rounded-md border border-partial/50 bg-partial/10 px-3 py-2 text-xs">
          No AI key is set, so questions come from templates filled with your report (still tailored to the job's skills,
          your gaps and your resume lines). Add a free Groq key for richer, fully custom scenarios.
        </p>
      )}
    </div>
  )
}

/** The Interview Prep tab: pick an analysis, generate a prep book, see all prep books. */
export function Prep() {
  const analyses = useAnalyses()
  const books = usePrepBooks()
  const remove = useDeletePrep()
  const [params, setParams] = useSearchParams()

  const scored = (analyses.data ?? []).filter((a) => a.status === 'done')
  const selected = params.get('analysis') ?? scored[0]?.id ?? null
  const chosen = scored.find((a) => a.id === selected)
  const countFor = (id: string) => books.data?.filter((b) => b.analysis_id === id).length ?? 0

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Interview Prep</h1>
        <p className="text-muted-foreground">
          A prep book of scenario questions (technical, system design, cultural fit and behavioural) built from a job
          description and your resume, with how to answer each one. Download it as PDF or Markdown.
        </p>
      </div>

      {analyses.isPending && <ListSkeleton />}
      {analyses.isError && <p className="text-sm text-weak">{errorMessage(analyses.error)}</p>}
      {analyses.data && scored.length === 0 && (
        <EmptyState icon={BookOpen} title="Score a resume first">
          A prep book is based on an analysis.{' '}
          <Link to="/analyze" className="font-medium text-primary hover:underline">
            Run a new analysis
          </Link>{' '}
          and come back here.
        </EmptyState>
      )}

      {scored.length > 0 && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <span className="grid size-6 place-items-center rounded-full bg-primary text-xs text-primary-foreground">1</span>
                Pick an analysis from your history
              </CardTitle>
            </CardHeader>
            <CardContent>
              <AnalysisPicker
                analyses={scored}
                selected={selected}
                onSelect={(id) => setParams({ analysis: id }, { replace: true })}
                extra={(id) => (countFor(id) ? `${countFor(id)} prep book${countFor(id) === 1 ? '' : 's'}` : null)}
              />
            </CardContent>
          </Card>
          <Card className="h-fit">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <span className="grid size-6 place-items-center rounded-full bg-primary text-xs text-primary-foreground">2</span>
                Generate the prep book
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {chosen && (
                <div className="rounded-lg bg-muted/60 px-3 py-2 text-sm">
                  <p className="font-medium">
                    {chosen.jd_title ?? 'Untitled job'}
                    {chosen.jd_company && ` at ${chosen.jd_company}`}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Resume: {chosen.resume_title ?? 'unknown'} · match score {chosen.overall_score} ·{' '}
                    <Link to={`/reports/${chosen.id}`} className="text-primary hover:underline">
                      view report
                    </Link>
                  </p>
                </div>
              )}
              {selected && <Generate key={selected} analysisId={selected} />}
            </CardContent>
          </Card>
        </div>
      )}

      <section className="space-y-3">
        <h2 className="font-semibold">Your prep books</h2>
        {books.isPending && <ListSkeleton />}
        {books.data?.length === 0 && (
          <EmptyState icon={BookOpen} title="No prep books yet">
            Pick an analysis above and generate your first one.
          </EmptyState>
        )}
        {!!books.data?.length && (
          <ul className="divide-y rounded-xl border bg-card">
            {books.data.map((b) => (
              <li key={b.id} className="flex items-center gap-3 px-4 py-2.5 hover:bg-accent/40">
                <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-accent text-primary">
                  {b.status === 'queued' || b.status === 'running' ? <Loader2 className="size-4 animate-spin" /> : <BookOpen className="size-4" />}
                </span>
                <Link to={`/prep/${b.id}`} className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">
                    {b.role ?? 'Untitled job'}
                    {b.company && ` at ${b.company}`} · Resume: {b.resume_title ?? 'unknown'}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {b.status === 'done'
                      ? `${b.question_count} questions`
                      : b.status === 'failed'
                        ? 'Failed'
                        : 'Generating…'}{' '}
                    · {formatDate(b.created_at)}
                  </p>
                </Link>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Delete prep book"
                  disabled={remove.isPending && remove.variables === b.id}
                  onClick={() => window.confirm('Delete this prep book?') && remove.mutate(b.id)}
                >
                  {remove.isPending && remove.variables === b.id ? <Loader2 className="animate-spin" /> : <Trash2 />}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
