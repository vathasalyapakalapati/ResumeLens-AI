import { Loader2, Mic } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { errorMessage, type Interviewer } from '@/lib/api'
import { useInterviewConfig, useStartInterview } from '@/lib/interviews'
import { cn } from '@/lib/utils'

export const INTERVIEWERS: { key: Interviewer; name: string; title: string }[] = [
  { key: 'maya', name: 'Maya', title: 'Senior Recruiter' },
  { key: 'james', name: 'James', title: 'Engineering Manager' },
]

/** Interviewer + number of questions + Start. Opens the interview room when ready. */
export function StartInterviewForm({ analysisId }: { analysisId: string | null }) {
  const config = useInterviewConfig()
  const start = useStartInterview(analysisId ?? '')
  const navigate = useNavigate()
  const [count, setCount] = useState(12)
  const [who, setWho] = useState<Interviewer>('maya')

  const begin = () => {
    if (analysisId)
      start.mutate({ question_count: count, interviewer: who }, { onSuccess: (iv) => navigate(`/interviews/${iv.id}/room`) })
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground">Interviewer</p>
          <div className="inline-flex gap-1 rounded-lg bg-muted p-1">
            {INTERVIEWERS.map((i) => (
              <button
                key={i.key}
                type="button"
                onClick={() => setWho(i.key)}
                className={cn(
                  'rounded-md px-3 py-1.5 text-left text-sm text-muted-foreground',
                  who === i.key && 'bg-card text-foreground shadow-sm',
                )}
              >
                {i.name} <span className="text-xs text-muted-foreground">· {i.title}</span>
              </button>
            ))}
          </div>
        </div>
        <label className="space-y-1.5">
          <span className="block text-xs font-medium text-muted-foreground">Questions</span>
          <select
            value={count}
            onChange={(e) => setCount(Number(e.target.value))}
            className="h-9 rounded-md border bg-card px-3 text-sm"
          >
            {[10, 11, 12, 13, 14, 15].map((n) => (
              <option key={n} value={n}>
                {n} questions
              </option>
            ))}
          </select>
        </label>
        <Button onClick={begin} disabled={!analysisId || start.isPending}>
          {start.isPending ? <Loader2 className="animate-spin" /> : <Mic />} Start interview
        </Button>
      </div>
      {start.isPending && <p className="text-sm text-muted-foreground">Preparing your questions…</p>}
      {start.isError && <p className="text-sm text-weak">{errorMessage(start.error)}</p>}
      {config.data && !config.data.ai && (
        <p className="rounded-md border border-partial/50 bg-partial/10 px-3 py-2 text-xs">
          No AI key is set, so questions come from a script based on your report, with no follow-ups and basic
          feedback. Add a free Groq key (LLM_PROVIDER=groq and GROQ_API_KEY) for a conversational interviewer.
        </p>
      )}
    </div>
  )
}
