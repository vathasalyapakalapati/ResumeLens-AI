import { useQuery } from '@tanstack/react-query'
import { Database, Plus, SearchCheck } from 'lucide-react'
import { Link } from 'react-router-dom'
import { EmptyState } from '@/components/EmptyState'
import { buttonVariants } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { getHealth } from '@/lib/api'

export function Dashboard() {
  const health = useQuery({ queryKey: ['health'], queryFn: getHealth, retry: false })

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Hello 👋</h1>
          <p className="text-muted-foreground">Here's how your resume is doing.</p>
        </div>
        <Link to="/analyze" className={buttonVariants()}>
          <Plus /> New analysis
        </Link>
      </div>

      <EmptyState icon={SearchCheck} title="No analyses yet — run your first one">
        Upload a resume and a job description to get a scored, evidence-backed match report.
      </EmptyState>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Database className="size-4" /> System status
          </CardTitle>
          <CardDescription>Shows the React app reaching FastAPI and PostgreSQL.</CardDescription>
        </CardHeader>
        <CardContent className="text-sm">
          {health.isPending && <div className="h-5 w-48 animate-pulse rounded bg-muted" />}
          {health.isError && <p className="text-weak">API unreachable — is the backend running on port 8010?</p>}
          {health.data && (
            <p>
              <span className="mr-2 inline-block size-2 rounded-full bg-strong" />
              API {health.data.status} · database {health.data.database} · pgvector {health.data.pgvector}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
