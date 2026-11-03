import { AlertTriangle, ArrowLeft, Download, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { LineList } from '@/components/LineList'
import { ListSkeleton } from '@/components/ListSkeleton'
import { Button } from '@/components/ui/button'
import { downloadResume, errorMessage } from '@/lib/api'
import { formatDate, useJd, useResume } from '@/lib/library'

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

function BackButton() {
  const navigate = useNavigate()
  return (
    <button
      onClick={() => (window.history.length > 1 ? navigate(-1) : navigate('/history'))}
      className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft className="size-4" /> Back
    </button>
  )
}

function LoadError({ error }: { error: unknown }) {
  return <p className="rounded-xl border px-4 py-6 text-center text-sm text-weak">{errorMessage(error)}</p>
}

// ---------- resume ----------

export function ResumeView() {
  const { id = '' } = useParams()
  const resume = useResume(id)
  const [downloading, setDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState<string | null>(null)

  const download = async () => {
    if (!resume.data) return
    setDownloading(true)
    setDownloadError(null)
    try {
      await downloadResume(resume.data.id, resume.data.file_name ?? `resume.${resume.data.format}`)
    } catch (err) {
      setDownloadError(errorMessage(err))
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="space-y-6">
      <BackButton />
      {resume.isPending && <ListSkeleton />}
      {resume.isError && <LoadError error={resume.error} />}
      {resume.data && (
        <>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold">{resume.data.title}</h1>
              <p className="text-sm text-muted-foreground">
                {[
                  resume.data.file_name,
                  resume.data.format.toUpperCase(),
                  resume.data.pages && plural(resume.data.pages, 'page'),
                  plural(resume.data.line_count, 'line'),
                  `uploaded ${formatDate(resume.data.created_at)}`,
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </p>
            </div>
            <Button variant="outline" onClick={download} disabled={downloading}>
              {downloading ? <Loader2 className="animate-spin" /> : <Download />} Original file
            </Button>
          </div>
          {downloadError && <p className="text-sm text-weak">{downloadError}</p>}
          {resume.data.warnings.map((w) => (
            <p key={w} className="flex items-start gap-2 rounded-md border border-partial/50 bg-partial/10 px-3 py-2 text-sm">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-partial" /> {w}
            </p>
          ))}
          <div className="space-y-2">
            <h2 className="font-semibold">What an ATS reads</h2>
            <p className="text-sm text-muted-foreground">
              This is the plain text pulled from your file. If something is missing or out of order here, an applicant
              tracking system probably sees it the same way.
            </p>
          </div>
          <LineList lines={resume.data.lines} />
        </>
      )}
    </div>
  )
}

// ---------- job description ----------

export function JobView() {
  const { id = '' } = useParams()
  const jd = useJd(id)

  return (
    <div className="space-y-6">
      <BackButton />
      {jd.isPending && <ListSkeleton />}
      {jd.isError && <LoadError error={jd.error} />}
      {jd.data && (
        <>
          <div>
            <h1 className="text-2xl font-semibold">{jd.data.title ?? 'Untitled job'}</h1>
            <p className="text-sm text-muted-foreground">
              {[jd.data.company, plural(jd.data.line_count, 'line'), `added ${formatDate(jd.data.created_at)}`]
                .filter(Boolean)
                .join(' · ')}
            </p>
          </div>
          <LineList lines={jd.data.lines} />
        </>
      )}
    </div>
  )
}
