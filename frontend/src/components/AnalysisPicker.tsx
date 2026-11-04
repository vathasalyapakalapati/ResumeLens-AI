import { Check, Search } from 'lucide-react'
import { useState } from 'react'
import { Input } from '@/components/ui/input'
import { scoreTone } from '@/lib/analyses'
import type { AnalysisSummary } from '@/lib/api'
import { formatDate } from '@/lib/library'
import { cn } from '@/lib/utils'

/** Pick one finished analysis from history. `extra` adds a note per row (e.g. "2 interviews"). */
export function AnalysisPicker({
  analyses,
  selected,
  onSelect,
  extra,
}: {
  analyses: AnalysisSummary[]
  selected: string | null
  onSelect: (id: string) => void
  extra?: (id: string) => string | null
}) {
  const [query, setQuery] = useState('')
  const q = query.trim().toLowerCase()
  const shown = analyses.filter((a) => !q || [a.resume_title, a.jd_title, a.jd_company].some((t) => t?.toLowerCase().includes(q)))

  return (
    <div className="space-y-3">
      {analyses.length > 4 && (
        <div className="relative">
          <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
          <Input className="pl-9" placeholder="Search by resume, job or company" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
      )}
      <ul role="listbox" className="max-h-96 space-y-2 overflow-y-auto">
        {shown.map((a) => {
          const note = extra?.(a.id)
          return (
            <li key={a.id}>
              <button
                role="option"
                aria-selected={selected === a.id}
                onClick={() => onSelect(a.id)}
                className={cn(
                  'flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left hover:bg-accent/50',
                  selected === a.id && 'border-primary bg-accent',
                )}
              >
                <span className={cn('grid size-10 shrink-0 place-items-center rounded-full border-2 text-sm font-semibold', scoreTone(a.overall_score))}>
                  {a.overall_score}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">
                    {a.jd_title ?? 'Untitled job'}
                    {a.jd_company && <span className="font-normal text-muted-foreground"> · {a.jd_company}</span>}
                  </span>
                  <span className="block truncate text-xs text-muted-foreground">
                    Resume: {a.resume_title ?? 'unknown'} · {formatDate(a.created_at)}
                    {note && ` · ${note}`}
                  </span>
                </span>
                {selected === a.id && <Check className="size-4 shrink-0 text-primary" />}
              </button>
            </li>
          )
        })}
        {shown.length === 0 && <li className="py-4 text-center text-sm text-muted-foreground">No matches for "{query}".</li>}
      </ul>
    </div>
  )
}
