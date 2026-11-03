import { LogOut } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { initials, useLogout, useMe } from '@/lib/auth'

/** Avatar button with a small dropdown: who you are, log out. */
export function UserMenu() {
  const { user } = useMe()
  const logout = useLogout()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === 'Escape' : !ref.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

  if (!user) return null

  const signOut = () => logout.mutate(undefined, { onSettled: () => navigate('/login', { replace: true }) })

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
        className="flex size-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {initials(user)}
      </button>
      {open && (
        <div role="menu" className="absolute right-0 mt-2 w-60 rounded-md border bg-background p-1 shadow-lg">
          <div className="px-3 py-2">
            {user.full_name && <p className="truncate text-sm font-medium">{user.full_name}</p>}
            <p className="truncate text-xs text-muted-foreground">{user.email}</p>
          </div>
          <div className="my-1 h-px bg-border" />
          <button
            role="menuitem"
            onClick={signOut}
            disabled={logout.isPending}
            className="flex w-full items-center gap-2 rounded px-3 py-1.5 text-sm hover:bg-accent disabled:opacity-50"
          >
            <LogOut className="size-4" /> {logout.isPending ? 'Logging out…' : 'Log out'}
          </button>
        </div>
      )}
    </div>
  )
}
