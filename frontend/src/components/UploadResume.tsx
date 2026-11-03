import { useState } from 'react'
import { FileDrop } from '@/components/FileDrop'
import { Input } from '@/components/ui/input'
import { errorMessage, type ResumeDetail } from '@/lib/api'
import { useUploadResume } from '@/lib/library'

/** Upload a PDF or DOCX resume, with an optional title. */
export function UploadResume({ onUploaded }: { onUploaded?: (resume: ResumeDetail) => void }) {
  const [title, setTitle] = useState('')
  const upload = useUploadResume()

  return (
    <div className="space-y-3">
      <Input
        placeholder="Title (optional, defaults to the file name)"
        maxLength={150}
        value={title}
        onChange={(e) => setTitle(e.target.value)}
      />
      <FileDrop
        accept={['.pdf', '.docx']}
        busy={upload.isPending}
        onFile={(file) =>
          upload.mutate(
            { file, title: title.trim() || undefined },
            {
              onSuccess: (resume) => {
                setTitle('')
                onUploaded?.(resume)
              },
            },
          )
        }
      />
      {upload.isError && <p className="text-sm text-weak">{errorMessage(upload.error)}</p>}
    </div>
  )
}
