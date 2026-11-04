import { ArrowLeft, Download, FileText, Loader2, Mic, Star, Trash2, VideoOff } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { scoreTone } from '@/lib/analyses'
import { downloadTranscript, errorMessage, type InterviewDetail, saveBlob } from '@/lib/api'
import { clock, useDeleteInterview, useInterview } from '@/lib/interviews'
import { formatDate } from '@/lib/library'
import { extensionFor, getRecording } from '@/lib/recordings'
import { cn } from '@/lib/utils'

function useLocalRecording(id: string) {
  const [state, setState] = useState<{ url: string; blob: Blob } | null | undefined>(undefined)
  useEffect(() => {
    let url = ''
    getRecording(id)
      .then((r) => {
        if (!r) return setState(null)
        url = URL.createObjectURL(r.blob)
        setState({ url, blob: r.blob })
      })
      .catch(() => setState(null))
    return () => {
      if (url) URL.revokeObjectURL(url)
    }
  }, [id])
  return state
}

function Feedback({ iv }: { iv: InterviewDetail }) {
  const fb = iv.feedback
  if (!fb) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between text-base">
          <span>Feedback</span>
          {fb.overall_score != null && (
            <span className={cn('text-2xl font-semibold', scoreTone(fb.overall_score))}>
              {fb.overall_score}
              <span className="text-sm text-muted-foreground">/100</span>
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <p className="leading-relaxed">{fb.summary}</p>
        <div className="grid gap-4 sm:grid-cols-2">
          {fb.strengths.length > 0 && (
            <div>
              <p className="mb-1 font-medium text-strong">Strengths</p>
              <ul className="list-disc space-y-1 pl-5">{fb.strengths.map((s) => <li key={s}>{s}</li>)}</ul>
            </div>
          )}
          {fb.improvements.length > 0 && (
            <div>
              <p className="mb-1 font-medium text-partial">To improve</p>
              <ul className="list-disc space-y-1 pl-5">{fb.improvements.map((s) => <li key={s}>{s}</li>)}</ul>
            </div>
          )}
        </div>
        {fb.questions.length > 0 && (
          <div className="space-y-2">
            <p className="font-medium">By question</p>
            <ul className="divide-y rounded-lg border">
              {fb.questions.map((q) => (
                <li key={q.number} className="flex gap-3 px-3 py-2">
                  <span className="w-8 shrink-0 font-mono text-xs leading-5 text-muted-foreground">Q{q.number}</span>
                  <div className="min-w-0 flex-1">
                    <p className="line-clamp-2 text-xs text-muted-foreground">{iv.questions[q.number - 1]}</p>
                    <p>{q.comment}</p>
                  </div>
                  {q.rating != null && (
                    <span className="flex shrink-0 items-center gap-0.5" aria-label={`${q.rating} out of 5`}>
                      {[1, 2, 3, 4, 5].map((n) => (
                        <Star key={n} className={cn('size-3.5', n <= q.rating! ? 'fill-partial text-partial' : 'text-muted')} />
                      ))}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
        <p className="text-xs text-muted-foreground">Feedback by: {fb.engine === 'basic' ? 'basic metrics (no AI key)' : fb.engine}</p>
      </CardContent>
    </Card>
  )
}

export function InterviewReview() {
  const { id = '' } = useParams()
  const interview = useInterview(id)
  const recording = useLocalRecording(id)
  const remove = useDeleteInterview()
  const navigate = useNavigate()
  const videoRef = useRef<HTMLVideoElement>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const iv = interview.data

  if (iv?.status === 'active') return <Navigate to={`/interviews/${id}/room`} replace />

  const transcript = async (format: 'txt' | 'md') => {
    setBusy(format)
    setErr(null)
    try {
      await downloadTranscript(id, format)
    } catch (e) {
      setErr(errorMessage(e))
    } finally {
      setBusy(null)
    }
  }
  const seek = (t: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = t
      void videoRef.current.play()
    }
  }

  return (
    <div className="space-y-6">
      {iv && (
        <Link to={`/reports/${iv.analysis_id}`} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" /> Back to report
        </Link>
      )}
      {interview.isPending && <Loader2 className="size-6 animate-spin text-muted-foreground" />}
      {interview.isError && <p className="text-sm text-weak">{errorMessage(interview.error)}</p>}
      {iv && (
        <>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold">
                Mock interview{iv.role ? `: ${iv.role}` : ''}
                {iv.company ? ` at ${iv.company}` : ''}
              </h1>
              <p className="text-sm text-muted-foreground">
                {formatDate(iv.created_at)} · {iv.interviewer_name} ({iv.interviewer_title}) · {iv.answered}/{iv.question_count} answered
                {iv.duration_seconds != null && ` · ${clock(iv.duration_seconds)}`}
                {iv.resume_title && ` · Resume: ${iv.resume_title}`}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" disabled={!recording} onClick={() => recording && saveBlob(recording.blob, `interview-${iv.created_at.slice(0, 10)}.${extensionFor(recording.blob.type)}`)}>
                <Download /> Video
              </Button>
              <Button variant="outline" size="sm" disabled={busy !== null} onClick={() => transcript('txt')}>
                {busy === 'txt' ? <Loader2 className="animate-spin" /> : <FileText />} Transcript (.txt)
              </Button>
              <Button variant="outline" size="sm" disabled={busy !== null} onClick={() => transcript('md')}>
                {busy === 'md' ? <Loader2 className="animate-spin" /> : <FileText />} Transcript (.md)
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={remove.isPending}
                onClick={() => {
                  if (window.confirm('Delete this interview, its transcript and its recording on this device?'))
                    remove.mutate(id, { onSuccess: () => navigate(`/reports/${iv.analysis_id}`, { replace: true }) })
                }}
              >
                <Trash2 /> Delete
              </Button>
            </div>
          </div>
          {err && <p className="text-sm text-weak">{err}</p>}

          <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
            <div className="space-y-6">
              <div className="overflow-hidden rounded-xl border bg-black">
                {recording === undefined && <div className="grid aspect-video place-items-center"><Loader2 className="size-6 animate-spin text-zinc-400" /></div>}
                {recording === null && (
                  <div className="grid aspect-video place-items-center p-6 text-center text-sm text-zinc-300">
                    <div className="space-y-2">
                      <VideoOff className="mx-auto size-8" />
                      <p>No recording on this device.</p>
                      <p className="text-zinc-400">Recordings stay in the browser they were made in. The transcript and feedback are still here.</p>
                    </div>
                  </div>
                )}
                {recording && <video ref={videoRef} src={recording.url} controls className="aspect-video w-full" />}
              </div>
              <Feedback iv={iv} />
            </div>

            <Card className="lg:max-h-[80vh] lg:overflow-hidden">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Mic className="size-4" /> Transcript
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm lg:max-h-[calc(80vh-5rem)] lg:overflow-y-auto">
                {iv.turns.map((t, i) => (
                  <div key={i} className={cn('space-y-0.5', t.role === 'candidate' && 'pl-6')}>
                    <button
                      onClick={() => seek(t.t)}
                      disabled={!recording}
                      className="text-xs text-muted-foreground hover:text-primary disabled:hover:text-muted-foreground"
                      title={recording ? 'Jump to this moment in the video' : undefined}
                    >
                      {t.role === 'interviewer' ? iv.interviewer_name : 'You'} · {clock(t.t)}
                      {t.role === 'interviewer' && t.kind === 'question' && ` · Q${t.q}`}
                      {t.kind === 'follow_up' && ' · follow-up'}
                    </button>
                    <p className={cn('rounded-lg px-3 py-2', t.role === 'interviewer' ? 'bg-muted' : 'bg-accent')}>
                      {t.text || <i className="text-muted-foreground">(no answer)</i>}
                    </p>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
