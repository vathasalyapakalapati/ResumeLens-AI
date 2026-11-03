import { Briefcase, Check, FileText, Loader2, Sparkles, X } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AddJdForm } from '@/components/AddJdForm'
import { ListSkeleton } from '@/components/ListSkeleton'
import { UploadResume } from '@/components/UploadResume'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useStartAnalysis } from '@/lib/analyses'
import { errorMessage } from '@/lib/api'
import { formatDate, useJds, useResumes } from '@/lib/library'
import { cn } from '@/lib/utils'

type Source = 'new' | 'saved'

interface Option {
  id: string
  title: string
  meta: string
}

function Toggle({ value, onChange, labels }: { value: Source; onChange: (v: Source) => void; labels: [string, string] }) {
  return (
    <div role="tablist" className="inline-flex gap-1 rounded-lg bg-muted p-1">
      {(['new', 'saved'] as const).map((v, i) => (
        <button
          key={v}
          type="button"
          role="tab"
          aria-selected={value === v}
          onClick={() => onChange(v)}
          className={cn(
            'rounded-md px-3 py-1.5 text-sm text-muted-foreground',
            value === v && 'bg-card text-foreground shadow-sm',
          )}
        >
          {labels[i]}
        </button>
      ))}
    </div>
  )
}

function SavedList({
  options,
  loading,
  selected,
  onSelect,
  icon,
  empty,
}: {
  options: Option[] | undefined
  loading: boolean
  selected: string | null
  onSelect: (id: string) => void
  icon: ReactNode
  empty: string
}) {
  if (loading) return <ListSkeleton />
  if (!options?.length) return <p className="rounded-lg border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">{empty}</p>
  return (
    <ul role="listbox" className="max-h-72 space-y-2 overflow-y-auto">
      {options.map((o) => (
        <li key={o.id}>
          <button
            role="option"
            aria-selected={selected === o.id}
            onClick={() => onSelect(o.id)}
            className={cn(
              'flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left hover:bg-accent/50',
              selected === o.id && 'border-primary bg-accent',
            )}
          >
            <span className="text-primary">{icon}</span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">{o.title}</span>
              <span className="block truncate text-xs text-muted-foreground">{o.meta}</span>
            </span>
            {selected === o.id && <Check className="size-4 text-primary" />}
          </button>
        </li>
      ))}
    </ul>
  )
}

/** Shown after a new resume/JD is added: what's selected, with a way to change it. */
function Chosen({ icon, title, onClear }: { icon: ReactNode; title: string; onClear: () => void }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-primary bg-accent px-3 py-2">
      <span className="text-primary">{icon}</span>
      <span className="min-w-0 flex-1 truncate text-sm font-medium">{title}</span>
      <Check className="size-4 text-primary" />
      <Button variant="ghost" size="sm" onClick={onClear}>
        <X /> Change
      </Button>
    </div>
  )
}

function Step({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <span className="grid size-6 place-items-center rounded-full bg-primary text-xs text-primary-foreground">{n}</span>
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
    </Card>
  )
}

export function NewAnalysis() {
  const resumes = useResumes()
  const jds = useJds()
  const start = useStartAnalysis()
  const navigate = useNavigate()

  const [resumeSource, setResumeSource] = useState<Source>('new')
  const [jdSource, setJdSource] = useState<Source>('new')
  const [newResume, setNewResume] = useState<Option | null>(null)
  const [newJd, setNewJd] = useState<Option | null>(null)
  const [savedResume, setSavedResume] = useState<string | null>(null)
  const [savedJd, setSavedJd] = useState<string | null>(null)

  const resumeId = resumeSource === 'new' ? newResume?.id : savedResume
  const jdId = jdSource === 'new' ? newJd?.id : savedJd
  const ready = Boolean(resumeId && jdId)

  const run = () => {
    if (resumeId && jdId)
      start.mutate({ resume_id: resumeId, jd_id: jdId }, { onSuccess: (a) => navigate(`/reports/${a.id}`) })
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">New analysis</h1>
        <p className="text-muted-foreground">
          Score a resume against a job description. Every finding points to a line in your resume.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Step n={1} title="Resume">
          <Toggle value={resumeSource} onChange={setResumeSource} labels={['Upload new resume', 'Use a saved resume']} />
          {resumeSource === 'new' &&
            (newResume ? (
              <Chosen icon={<FileText className="size-4" />} title={newResume.title} onClear={() => setNewResume(null)} />
            ) : (
              <UploadResume onUploaded={(r) => setNewResume({ id: r.id, title: r.title, meta: '' })} />
            ))}
          {resumeSource === 'saved' && (
            <SavedList
              loading={resumes.isPending}
              options={resumes.data?.map((r) => ({
                id: r.id,
                title: r.title,
                meta: [r.file_name, formatDate(r.created_at)].filter(Boolean).join(' · '),
              }))}
              selected={savedResume}
              onSelect={setSavedResume}
              icon={<FileText className="size-4" />}
              empty="No saved resumes yet. Upload one with the first option."
            />
          )}
        </Step>

        <Step n={2} title="Job description">
          <Toggle value={jdSource} onChange={setJdSource} labels={['Add new JD', 'Use a saved JD']} />
          {jdSource === 'new' &&
            (newJd ? (
              <Chosen icon={<Briefcase className="size-4" />} title={newJd.title} onClear={() => setNewJd(null)} />
            ) : (
              <AddJdForm onAdded={(jd) => setNewJd({ id: jd.id, title: jd.title ?? 'Untitled job', meta: '' })} />
            ))}
          {jdSource === 'saved' && (
            <SavedList
              loading={jds.isPending}
              options={jds.data?.map((j) => ({
                id: j.id,
                title: j.title ?? 'Untitled job',
                meta: [j.company, formatDate(j.created_at)].filter(Boolean).join(' · '),
              }))}
              selected={savedJd}
              onSelect={setSavedJd}
              icon={<Briefcase className="size-4" />}
              empty="No saved job descriptions yet. Add one with the first option."
            />
          )}
        </Step>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button size="default" onClick={run} disabled={!ready || start.isPending}>
          {start.isPending ? <Loader2 className="animate-spin" /> : <Sparkles />} Run analysis
        </Button>
        <p className="text-sm text-muted-foreground">
          {ready ? 'Ready to score.' : `Still needed: ${[!resumeId && 'a resume', !jdId && 'a job description'].filter(Boolean).join(' and ')}.`}
        </p>
      </div>
      {start.isError && <p className="text-sm text-weak">{errorMessage(start.error)}</p>}
    </div>
  )
}
