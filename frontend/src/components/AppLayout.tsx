import { Aperture, FileText, History, LayoutDashboard, Plus, Settings } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { ThemeToggle } from '@/components/ThemeToggle'
import { cn } from '@/lib/utils'

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/analyze', label: 'New analysis', icon: Plus },
  { to: '/history', label: 'History', icon: History },
  { to: '/resumes', label: 'Resumes', icon: FileText },
  { to: '/settings', label: 'Settings', icon: Settings },
]

/** Navbar and page frame for every signed-in page. The avatar menu arrives with auth in phase 2. */
export function AppLayout() {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4">
          <NavLink to="/dashboard" className="flex items-center gap-2 font-semibold">
            <Aperture className="size-5 text-primary" />
            ResumeLens <span className="text-primary">AI</span>
          </NavLink>
          <nav className="hidden gap-1 md:flex">
            {NAV.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm text-muted-foreground hover:bg-accent hover:text-foreground',
                    isActive && 'bg-accent text-foreground',
                  )
                }
              >
                <Icon className="size-4" />
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto">
            <ThemeToggle />
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto border-t px-2 py-1 md:hidden">
          {NAV.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn('shrink-0 rounded-md px-3 py-1.5 text-sm text-muted-foreground', isActive && 'bg-accent text-foreground')
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}
