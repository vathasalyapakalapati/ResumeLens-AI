import { FileUp, Loader2 } from 'lucide-react'
import { type DragEvent, useId, useState } from 'react'
import { cn } from '@/lib/utils'

const MAX_MB = 5

interface Props {
  accept: string[] // extensions, e.g. ['.pdf', '.docx']
  onFile: (file: File) => void
  busy?: boolean
  hint?: string
}

/** Click-or-drop file picker. Checks extension and size before anything is uploaded. */
export function FileDrop({ accept, onFile, busy, hint }: Props) {
  const inputId = useId()
  const [over, setOver] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const pick = (file: File | undefined) => {
    if (!file || busy) return
    const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
    if (!accept.includes(ext)) return setError(`Please choose a ${accept.join(' or ')} file.`)
    if (file.size > MAX_MB * 1024 * 1024) return setError(`That file is over ${MAX_MB} MB.`)
    setError(null)
    onFile(file)
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setOver(false)
    pick(e.dataTransfer.files[0])
  }

  return (
    <div className="space-y-2">
      <label
        htmlFor={inputId}
        onDragOver={(e) => {
          e.preventDefault()
          setOver(true)
        }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
        className={cn(
          'flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors hover:border-primary/60 hover:bg-accent/40',
          over && 'border-primary bg-accent/60',
          busy && 'pointer-events-none opacity-60',
        )}
      >
        {busy ? (
          <Loader2 className="size-8 animate-spin text-primary" />
        ) : (
          <FileUp className="size-8 text-primary" />
        )}
        <span className="font-medium">{busy ? 'Uploading and reading…' : 'Drop a file here or click to browse'}</span>
        <span className="text-xs text-muted-foreground">
          {hint ?? accept.join(', ').toUpperCase().replaceAll('.', '')} · up to {MAX_MB} MB
        </span>
        <input
          id={inputId}
          type="file"
          className="sr-only"
          accept={accept.join(',')}
          disabled={busy}
          onChange={(e) => {
            pick(e.target.files?.[0])
            e.target.value = '' // let the same file be picked again after an error
          }}
        />
      </label>
      {error && <p className="text-sm text-weak">{error}</p>}
    </div>
  )
}
