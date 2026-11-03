import { ClipboardPaste, FileUp, Loader2 } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { FileDrop } from '@/components/FileDrop'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { errorMessage, type JdDetail } from '@/lib/api'
import { useAddJd } from '@/lib/library'
import { cn } from '@/lib/utils'

/** Add a job description by pasting its text or uploading a file. */
export function AddJdForm({ onAdded }: { onAdded?: (jd: JdDetail) => void }) {
  const [mode, setMode] = useState<'paste' | 'upload'>('paste')
  const [text, setText] = useState('')
  const [title, setTitle] = useState('')
  const [company, setCompany] = useState('')
  const add = useAddJd()

  const done = (jd: JdDetail) => {
    setText('')
    setTitle('')
    setCompany('')
    onAdded?.(jd)
  }
  const meta = { title: title.trim() || undefined, company: company.trim() || undefined }

  const submitPaste = (e: FormEvent) => {
    e.preventDefault()
    if (mode !== 'paste' || !text.trim()) return // Enter in a title field while on the upload tab
    add.mutate({ kind: 'paste', text, ...meta }, { onSuccess: done })
  }

  const tab = (value: typeof mode, label: string, Icon: typeof FileUp) => (
    <button
      type="button"
      role="tab"
      aria-selected={mode === value}
      onClick={() => {
        setMode(value)
        add.reset()
      }}
      className={cn(
        'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm text-muted-foreground',
        mode === value && 'bg-card text-foreground shadow-sm',
      )}
    >
      <Icon className="size-4" /> {label}
    </button>
  )

  return (
    <form onSubmit={submitPaste} className="space-y-3">
      <div role="tablist" className="inline-flex gap-1 rounded-lg bg-muted p-1">
        {tab('paste', 'Paste text', ClipboardPaste)}
        {tab('upload', 'Upload file', FileUp)}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Input placeholder="Job title (optional)" maxLength={150} value={title} onChange={(e) => setTitle(e.target.value)} />
        <Input placeholder="Company (optional)" maxLength={150} value={company} onChange={(e) => setCompany(e.target.value)} />
      </div>
      {mode === 'paste' ? (
        <>
          <Textarea
            placeholder="Paste the full job description here…"
            className="min-h-48"
            maxLength={100_000}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <Button type="submit" disabled={add.isPending || text.trim().length === 0}>
            {add.isPending && <Loader2 className="animate-spin" />} Save job description
          </Button>
        </>
      ) : (
        <FileDrop
          accept={['.pdf', '.docx', '.txt']}
          busy={add.isPending}
          onFile={(file) => add.mutate({ kind: 'upload', file, ...meta }, { onSuccess: done })}
        />
      )}
      {add.isError && <p className="text-sm text-weak">{errorMessage(add.error)}</p>}
    </form>
  )
}
