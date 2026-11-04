import { Loader2, PlayCircle, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { INTERVIEWERS } from '@/components/StartInterviewForm'
import { Button } from '@/components/ui/button'
import { scoreTone } from '@/lib/analyses'
import type { InterviewSummary } from '@/lib/api'
import { clock, useDeleteInterview } from '@/lib/interviews'
import { formatDate } from '@/lib/library'
import { cn } from '@/lib/utils'

/** One interview in a list. `context` adds a line such as the job and resume it was about. */
export function InterviewRow({ iv, context }: { iv: InterviewSummary; context?: string }) {
  const remove = useDeleteInterview()
  const done = iv.status === 'completed'
  const href = done ? `/interviews/${iv.id}` : `/interviews/${iv.id}/room`
  const deleting = remove.isPending && remove.variables === iv.id

  return (
    <li className="flex items-center gap-3 px-4 py-2.5 hover:bg-accent/40">
      <span
        className={cn(
          'grid size-10 shrink-0 place-items-center rounded-full border-2 text-sm font-semibold',
          scoreTone(iv.overall_score),
        )}
        title={done ? 'Interview score' : 'In progress'}
      >
        {done ? (iv.overall_score ?? '✓') : '…'}
      </span>
      <Link to={href} className="min-w-0 flex-1">
        {context && <p className="truncate text-sm font-medium">{context}</p>}
        <p className={cn('truncate', context ? 'text-xs text-muted-foreground' : 'text-sm font-medium')}>
          {INTERVIEWERS.find((i) => i.key === iv.interviewer)?.name ?? 'Interview'} · {iv.answered}/{iv.question_count}{' '}
          answered
          {done && iv.duration_seconds != null && ` · ${clock(iv.duration_seconds)}`}
        </p>
        <p className="text-xs text-muted-foreground">
          {formatDate(iv.created_at)} · {done ? 'View recording, transcript and feedback' : 'In progress: rejoin'}
        </p>
      </Link>
      {!done && (
        <Link to={href} className="text-primary" aria-label="Rejoin interview">
          <PlayCircle className="size-5" />
        </Link>
      )}
      <Button
        variant="ghost"
        size="icon"
        aria-label="Delete interview"
        disabled={deleting}
        onClick={() => {
          if (window.confirm('Delete this interview, its transcript and its recording on this device?')) remove.mutate(iv.id)
        }}
      >
        {deleting ? <Loader2 className="animate-spin" /> : <Trash2 />}
      </Button>
    </li>
  )
}
