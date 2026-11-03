import { FileSearch, FileText, History as HistoryIcon, Settings as SettingsIcon, Upload } from 'lucide-react'
import type { ReactNode } from 'react'
import { EmptyState } from '@/components/EmptyState'

function Page({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">{title}</h1>
      {children}
    </div>
  )
}

export const NewAnalysis = () => (
  <Page title="New analysis">
    <EmptyState icon={Upload} title="Drop a resume and a job description">
      Resume upload (PDF or DOCX) and JD paste/upload arrive in phase 3.
    </EmptyState>
  </Page>
)

export const Report = () => (
  <Page title="Report">
    <EmptyState icon={FileSearch} title="No report selected">
      The score ring, requirement checklist and suggestions arrive in phase 4.
    </EmptyState>
  </Page>
)

export const History = () => (
  <Page title="History">
    <EmptyState icon={HistoryIcon} title="No analyses yet — run your first one">
      Every analysis you run will be listed here with search and filters.
    </EmptyState>
  </Page>
)

export const Resumes = () => (
  <Page title="Resumes">
    <EmptyState icon={FileText} title="Your resume library is empty">
      Uploaded resumes and their versions (v1, v2, v3) will show up here.
    </EmptyState>
  </Page>
)

export const Settings = () => (
  <Page title="Settings">
    <EmptyState icon={SettingsIcon} title="Settings come with accounts">
      Profile, change password and delete-my-data arrive in phase 2.
    </EmptyState>
  </Page>
)
