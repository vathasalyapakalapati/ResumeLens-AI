/** Grey placeholder rows while a list loads. */
export function ListSkeleton() {
  return (
    <ul className="divide-y rounded-xl border bg-card">
      {[0, 1, 2].map((i) => (
        <li key={i} className="flex items-center gap-3 px-4 py-3">
          <span className="size-9 animate-pulse rounded-lg bg-muted" />
          <span className="h-4 w-48 animate-pulse rounded bg-muted" />
        </li>
      ))}
    </ul>
  )
}
