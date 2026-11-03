import type { Line } from '@/lib/api'

/** The parsed text with its line ids. Reports will cite these ids (e.g. "L14") as evidence. */
export function LineList({ lines }: { lines: Line[] }) {
  return (
    <ol className="divide-y rounded-xl border bg-card font-mono text-sm">
      {lines.map((line) => (
        <li key={line.id} id={line.id} className="flex gap-4 px-4 py-1.5 target:bg-accent">
          <span className="w-10 shrink-0 select-none text-right text-xs leading-5 text-muted-foreground">{line.id}</span>
          <span className="min-w-0 whitespace-pre-wrap break-words font-sans leading-5">{line.text}</span>
        </li>
      ))}
    </ol>
  )
}
