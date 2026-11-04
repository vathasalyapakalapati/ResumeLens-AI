import { BookOpen, History as HistoryIcon, Loader2, Plus, Search, Trash2, Video } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState } from '@/components/EmptyState'
import { ListSkeleton } from '@/components/ListSkeleton'
import { Button, buttonVariants } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { scoreTone, useAnalyses, useDeleteAnalysis } from '@/lib/analyses'
import { type AnalysisSummary, errorMessage } from '@/lib/api'
import { formatDate } from '@/lib/library'
import { cn } from '@/lib/utils'

function ScoreBadge({ a }: { a: AnalysisSummary }) {
  if (a.status === 'done')
    return (
      <span className={cn('grid size-12 shrink-0 place-items-center rounded-full border-2 text-lg font-semibold', scoreTone(a.overall_score))}>
        {a.overall_score}
      </span>
    )
  return (
    <span className="grid size-12 shrink-0 place-items-center rounded-full border-2 text-xs text-muted-foreground">
      {a.status === 'failed' ? 'failed' : <Loader2 className="size-4 animate-spin" />}
    </span>
  )
}

export function History() {
  const analyses = useAnalyses()
  const remove = useDeleteAnalysis()
  const [query, setQuery] = useState('')

  const q = query.trim().toLowerCase()
  const rows = (analyses.data ?? []).filter(
    (a) => !q || [a.resume_title, a.jd_title, a.jd_company].some((t) => t?.toLowerCase().includes(q)),
  )

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">History</h1>
          <p className="text-muted-foreground">Every analysis you've run, with the resume and job it used.</p>
        </div>
        <Link to="/analyze" className={buttonVariants()}>
          <Plus /> New analysis
        </Link>
      </div>

      {analyses.isPending && <ListSkeleton />}
      {analyses.isError && <p className="rounded-xl border px-4 py-6 text-center text-sm text-weak">{errorMessage(analyses.error)}</p>}
      {analyses.data?.length === 0 && (
        <EmptyState icon={HistoryIcon} title="No analyses yet. Run your first one">
          Upload a resume and a job description to get a scored, evidence-backed match report.
        </EmptyState>
      )}

      {!!analyses.data?.length && (
        <>
          <div className="relative max-w-sm">
            <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
            <Input
              className="pl-9"
              placeholder="Search by resume, job or company"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <ul className="divide-y rounded-xl border bg-card">
            {rows.map((a) => (
              <li key={a.id} className="flex items-center gap-4 px-4 py-3 hover:bg-accent/40">
                <ScoreBadge a={a} />
                <Link to={`/reports/${a.id}`} className="min-w-0 flex-1">
                  <p className="truncate font-medium">
                    {a.jd_title ?? 'Untitled job'}
                    {a.jd_company && <span className="font-normal text-muted-foreground"> · {a.jd_company}</span>}
                  </p>
                  <p className="truncate text-sm text-muted-foreground">
                    Resume: {a.resume_title ?? 'unknown'}
                    {!a.resume_id && ' (deleted)'}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {a.verdict ? `${a.verdict} · ` : ''}
                    {formatDate(a.created_at)}
                  </p>
                </Link>
                {a.status === 'done' && (
                  <Link
                    to={`/prep?analysis=${a.id}`}
                    className={buttonVariants({ variant: 'ghost', size: 'icon' })}
                    aria-label="Make an interview prep book for this job"
                    title="Interview prep"
                  >
                    <BookOpen />
                  </Link>
                )}
                {a.status === 'done' && (
                  <Link
                    to={`/interviews?analysis=${a.id}`}
                    className={buttonVariants({ variant: 'ghost', size: 'icon' })}
                    aria-label="Practise an AI interview for this job"
                    title="AI interview"
                  >
                    <Video />
                  </Link>
                )}
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Delete analysis"
                  disabled={remove.isPending && remove.variables === a.id}
                  onClick={() => {
                    if (window.confirm('Delete this analysis from your history?')) remove.mutate(a.id)
                  }}
                >
                  {remove.isPending && remove.variables === a.id ? <Loader2 className="animate-spin" /> : <Trash2 />}
                </Button>
              </li>
            ))}
            {rows.length === 0 && <li className="px-4 py-6 text-center text-sm text-muted-foreground">No matches for "{query}".</li>}
          </ul>
        </>
      )}
      {remove.isError && <p className="text-sm text-weak">{errorMessage(remove.error)}</p>}
    </div>
  )
}
