import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/components/AppLayout'
import { RequireAuth } from '@/components/RequireAuth'
import { AuthPage } from '@/pages/AuthPage'
import { History } from '@/pages/History'
import { JobView, ResumeView } from '@/pages/Library'
import { NewAnalysis } from '@/pages/NewAnalysis'
import { Report } from '@/pages/Report'
import './index.css'

const queryClient = new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false } } })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<AuthPage mode="login" />} />
          <Route path="/signup" element={<AuthPage mode="signup" />} />
          {/* Logged-out visitors are sent to /login. */}
          <Route element={<RequireAuth />}>
            <Route element={<AppLayout />}>
              <Route path="/analyze" element={<NewAnalysis />} />
              <Route path="/reports/:id" element={<Report />} />
              <Route path="/history" element={<History />} />
              <Route path="/resumes/:id" element={<ResumeView />} />
              <Route path="/jobs/:id" element={<JobView />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/analyze" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
