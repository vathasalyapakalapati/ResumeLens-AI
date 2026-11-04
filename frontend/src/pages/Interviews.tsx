import { History as HistoryIcon, Video } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { AnalysisPicker } from '@/components/AnalysisPicker'
import { EmptyState } from '@/components/EmptyState'
import { InterviewRow } from '@/components/InterviewRow'
import { ListSkeleton } from '@/components/ListSkeleton'
import { StartInterviewForm } from '@/components/StartInterviewForm'
import { buttonVariants } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useAnalyses } from '@/lib/analyses'
import { errorMessage } from '@/lib/api'
import { useAllInterviews } from '@/lib/interviews'
import { cn } from '@/lib/utils'

/** The AI Interview tab: pick one of your scored analyses, start an interview, see all past interviews. */
export function Interviews() {
  const analyses = useAnalyses()
  const interviews = useAllInterviews()
  const [params, setParams] = useSearchParams()

  const scored = (analyses.data ?? []).filter((a) => a.status === 'done')
  const selected = params.get('analysis') ?? scored[0]?.id ?? null
  const chosen = scored.find((a) => a.id === selected)
  const countFor = (id: string) => interviews.data?.filter((iv) => iv.analysis_id === id).length ?? 0

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">AI Interview</h1>
        <p className="text-muted-foreground">
          Practise with a video-call mock interview based on one of your scored analyses: its resume, job description and
          report.
        </p>
      </div>

      {analyses.isPending && <ListSkeleton />}
      {analyses.isError && <p className="text-sm text-weak">{errorMessage(analyses.error)}</p>}
      {analyses.data && scored.length === 0 && (
        <EmptyState icon={Video} title="Score a resume first">
          An interview is based on an analysis.{' '}
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
                extra={(id) => (countFor(id) ? `${countFor(id)} interview${countFor(id) === 1 ? '' : 's'}` : null)}
              />
            </CardContent>
          </Card>

          <Card className="h-fit">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <span className="grid size-6 place-items-center rounded-full bg-primary text-xs text-primary-foreground">2</span>
                Set up the interview
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
              {/* key: reset the form when switching analyses */}
              <StartInterviewForm key={selected ?? 'none'} analysisId={selected} />
              <p className="text-xs text-muted-foreground">
                You'll be asked for camera and microphone access. The recording stays on this device; you can watch it,
                download it, and download the transcript afterwards.
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      <section className="space-y-3">
        <h2 className="font-semibold">Your interviews</h2>
        {interviews.isPending && <ListSkeleton />}
        {interviews.data?.length === 0 && (
          <EmptyState icon={HistoryIcon} title="No interviews yet">
            Pick an analysis above and start your first mock interview.
          </EmptyState>
        )}
        {!!interviews.data?.length && (
          <ul className="divide-y rounded-xl border bg-card">
            {interviews.data.map((iv) => (
              <InterviewRow
                key={iv.id}
                iv={iv}
                context={`${iv.role ?? 'Untitled job'}${iv.company ? ` at ${iv.company}` : ''} · Resume: ${iv.resume_title ?? 'unknown'}`}
              />
            ))}
          </ul>
        )}
        {analyses.data && scored.length > 0 && (
          <Link to="/history" className={cn(buttonVariants({ variant: 'ghost', size: 'sm' }), 'px-0 text-muted-foreground')}>
            <HistoryIcon /> See all analyses in History
          </Link>
        )}
      </section>
    </div>
  )
}
