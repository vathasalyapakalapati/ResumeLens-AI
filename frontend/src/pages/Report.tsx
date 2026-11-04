import {
  AlertTriangle,
  ArrowLeft,
  Briefcase,
  CheckCircle2,
  CircleDashed,
  FileText,
  Loader2,
  RotateCcw,
  XCircle,
} from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { InterviewsPanel } from '@/components/InterviewsPanel'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { scoreBg, scoreStroke, scoreTone, useAnalysis, useStartAnalysis } from '@/lib/analyses'
import { type AnalysisDetail, errorMessage, type ReportRequirement, type ReqStatus, type SubScores } from '@/lib/api'
import { formatDate } from '@/lib/library'
import { cn } from '@/lib/utils'

const STEPS = [
  { key: 'parse', label: 'Reading resume and JD' },
  { key: 'match', label: 'Matching requirements' },
  { key: 'score', label: 'Scoring' },
] as const

const SUB_LABELS: Record<keyof SubScores, string> = {
  must_have: 'Must-have requirements',
  nice_to_have: 'Nice-to-have requirements',
  skills: 'Skills',
  experience: 'Experience',
  education: 'Education',
  keywords: 'ATS keyword coverage',
}

const STATUS: Record<ReqStatus, { icon: typeof CheckCircle2; label: string; tone: string }> = {
  met: { icon: CheckCircle2, label: 'Met', tone: 'text-strong' },
  partial: { icon: CircleDashed, label: 'Partial', tone: 'text-partial' },
  missing: { icon: XCircle, label: 'Missing', tone: 'text-weak' },
}

function ScoreRing({ score }: { score: number }) {
  const r = 52
  const c = 2 * Math.PI * r
  return (
    <div className="relative size-36 shrink-0">
      <svg viewBox="0 0 120 120" className="size-full -rotate-90">
        <circle cx="60" cy="60" r={r} fill="none" strokeWidth="10" className="stroke-muted" />
        <circle
          cx="60"
          cy="60"
          r={r}
          fill="none"
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - score / 100)}
          className={cn('transition-[stroke-dashoffset] duration-700', scoreStroke(score))}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn('text-4xl font-semibold', scoreTone(score))}>{score}</span>
        <span className="text-xs text-muted-foreground">out of 100</span>
      </div>
    </div>
  )
}

function Progress({ a }: { a: AnalysisDetail }) {
  const current = STEPS.findIndex((s) => s.key === a.current_step)
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-6 py-12">
        <Loader2 className="size-8 animate-spin text-primary" />
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
              <span className={cn(i > current && 'text-muted-foreground')}>{s.label}</span>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  )
}

function SourceCard({ kind, id, title, sub }: { kind: 'resume' | 'jd'; id: string | null; title: string; sub?: string | null }) {
  const Icon = kind === 'resume' ? FileText : Briefcase
  const inner = (
    <>
      <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-accent text-primary">
        <Icon className="size-4" />
      </span>
      <span className="min-w-0">
        <span className="block text-xs text-muted-foreground">{kind === 'resume' ? 'Resume used' : 'Job description used'}</span>
        <span className="block truncate font-medium">{title}</span>
        <span className="block truncate text-xs text-muted-foreground">
          {id ? sub : 'Deleted since. The details below were saved with this report.'}
        </span>
      </span>
    </>
  )
  const cls = 'flex items-center gap-3 rounded-xl border bg-card px-4 py-3'
  return id ? (
    <Link to={kind === 'resume' ? `/resumes/${id}` : `/jobs/${id}`} className={cn(cls, 'hover:bg-accent/40')}>
      {inner}
    </Link>
  ) : (
    <div className={cls}>{inner}</div>
  )
}

function RequirementRow({ req, resumeLines }: { req: ReportRequirement; resumeLines: Record<string, string> }) {
  const s = STATUS[req.status]
  return (
    <li className="space-y-2 px-4 py-3">
      <div className="flex items-start gap-3">
        <s.icon className={cn('mt-0.5 size-5 shrink-0', s.tone)} aria-label={s.label} />
        <div className="min-w-0 flex-1">
          <p className="font-medium">{req.text}</p>
          <p className="text-xs text-muted-foreground">
            <span className={cn('font-medium', s.tone)}>{s.label}</span>
            {' · '}
            {req.category}
            {req.jd_line && ` · JD ${req.jd_line}`}
            {req.note && ` · ${req.note}`}
          </p>
        </div>
      </div>
      {req.evidence.length > 0 && (
        <ul className="ml-8 space-y-1">
          {req.evidence.map((lid) => (
            <li key={lid} className="flex gap-2 rounded-md bg-muted/60 px-2 py-1 text-sm">
              <span className="shrink-0 font-mono text-xs leading-5 text-muted-foreground">{lid}</span>
              <span className="min-w-0">{resumeLines[lid] ?? '(line text not available)'}</span>
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}

function Done({ a }: { a: AnalysisDetail }) {
  const report = a.report!
  const score = a.overall_score ?? 0
  const groups = [
    { title: 'Must-have', items: report.requirements.filter((r) => r.importance === 'must') },
    { title: 'Nice-to-have', items: report.requirements.filter((r) => r.importance === 'nice') },
  ].filter((g) => g.items.length)
  const counts = (items: ReportRequirement[]) =>
    (['met', 'partial', 'missing'] as const).map((s) => `${items.filter((r) => r.status === s).length} ${s}`).join(' · ')

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="flex flex-col items-center gap-6 pt-6 sm:flex-row sm:items-center">
          <ScoreRing score={score} />
          <div className="space-y-2">
            <p className={cn('text-xl font-semibold', scoreTone(score))}>{report.verdict}</p>
            <p className="text-sm leading-relaxed">{report.summary}</p>
            <p className="text-xs text-muted-foreground">
              Scored {a.completed_at && formatDate(a.completed_at)} · matcher: {report.engine}
            </p>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-3 sm:grid-cols-2">
        <SourceCard kind="resume" id={a.resume_id} title={a.resume_title ?? report.resume.title} sub={report.resume.file_name} />
        <SourceCard kind="jd" id={a.jd_id} title={a.jd_title ?? report.jd.title ?? 'Untitled job'} sub={a.jd_company ?? report.jd.company} />
      </div>

      {report.warnings.map((w) => (
        <p key={w} className="flex items-start gap-2 rounded-md border border-partial/50 bg-partial/10 px-3 py-2 text-sm">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-partial" /> {w}
        </p>
      ))}

      {a.sub_scores && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Score breakdown</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
            {(Object.keys(SUB_LABELS) as (keyof SubScores)[]).map((k) => {
              const v = a.sub_scores![k]
              return (
                <div key={k} className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span>{SUB_LABELS[k]}</span>
                    <span className={cn('font-medium', scoreTone(v))}>{v == null ? 'n/a' : v}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-muted">
                    <div className={cn('h-full rounded-full', scoreBg(v))} style={{ width: `${v ?? 0}%` }} />
                  </div>
                </div>
              )
            })}
          </CardContent>
        </Card>
      )}

      {groups.map((g) => (
        <section key={g.title} className="space-y-2">
          <div className="flex items-baseline justify-between">
            <h2 className="font-semibold">{g.title} requirements</h2>
            <span className="text-xs text-muted-foreground">{counts(g.items)}</span>
          </div>
          <ul className="divide-y rounded-xl border bg-card">
            {g.items.map((r) => (
              <RequirementRow key={r.id} req={r} resumeLines={report.resume_lines} />
            ))}
          </ul>
        </section>
      ))}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">ATS keywords</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex flex-wrap gap-1.5">
            <span className="mr-1 text-muted-foreground">In your resume:</span>
            {report.keywords.matched.length ? (
              report.keywords.matched.map((k) => (
                <span key={k} className="rounded-full bg-strong/15 px-2 py-0.5 text-xs font-medium text-strong">
                  {k}
                </span>
              ))
            ) : (
              <span className="text-muted-foreground">none</span>
            )}
          </div>
          <div className="flex flex-wrap gap-1.5">
            <span className="mr-1 text-muted-foreground">Missing:</span>
            {report.keywords.missing.length ? (
              report.keywords.missing.map((k) => (
                <span key={k} className="rounded-full bg-weak/15 px-2 py-0.5 text-xs font-medium text-weak">
                  {k}
                </span>
              ))
            ) : (
              <span className="text-muted-foreground">none</span>
            )}
          </div>
          <p className="text-xs text-muted-foreground">Only add a missing keyword if you genuinely have that experience.</p>
        </CardContent>
      </Card>
    </div>
  )
}

export function Report() {
  const { id = '' } = useParams()
  const analysis = useAnalysis(id)
  const rerun = useStartAnalysis()
  const navigate = useNavigate()
  const a = analysis.data

  const again = () => {
    if (a?.resume_id && a.jd_id)
      rerun.mutate({ resume_id: a.resume_id, jd_id: a.jd_id }, { onSuccess: (n) => navigate(`/reports/${n.id}`) })
  }
  const canRerun = Boolean(a?.resume_id && a.jd_id && ['done', 'failed'].includes(a.status))

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link to="/history" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" /> History
        </Link>
        {canRerun && (
          <Button variant="outline" size="sm" onClick={again} disabled={rerun.isPending}>
            {rerun.isPending ? <Loader2 className="animate-spin" /> : <RotateCcw />} Run again
          </Button>
        )}
      </div>
      <h1 className="text-2xl font-semibold">Match report</h1>

      {analysis.isPending && <Progress a={{ current_step: null } as AnalysisDetail} />}
      {analysis.isError && <p className="rounded-xl border px-4 py-6 text-center text-sm text-weak">{errorMessage(analysis.error)}</p>}
      {a && ['queued', 'running'].includes(a.status) && <Progress a={a} />}
      {a?.status === 'failed' && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <XCircle className="size-8 text-weak" />
            <p className="font-medium">This analysis couldn't be completed</p>
            <p className="max-w-md text-sm text-muted-foreground">{a.error}</p>
          </CardContent>
        </Card>
      )}
      {a?.status === 'done' && a.report && (
        <>
          <Done a={a} />
          <InterviewsPanel analysisId={a.id} />
        </>
      )}
      {rerun.isError && <p className="text-sm text-weak">{errorMessage(rerun.error)}</p>}
    </div>
  )
}
