import { Video } from 'lucide-react'
import { InterviewRow } from '@/components/InterviewRow'
import { StartInterviewForm } from '@/components/StartInterviewForm'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useInterviews } from '@/lib/interviews'

/** On a finished report: start an AI mock interview and see past ones for this report. */
export function InterviewsPanel({ analysisId }: { analysisId: string }) {
  const interviews = useInterviews(analysisId)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Video className="size-4 text-primary" /> AI mock interview
        </CardTitle>
        <CardDescription>
          A video-call style interview based on this resume, job and report. Your camera and microphone are used; the
          recording stays on this device and can be downloaded with the transcript. Take as many as you like.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <StartInterviewForm analysisId={analysisId} />
        {!!interviews.data?.length && (
          <div className="space-y-2">
            <p className="text-sm font-medium">Past interviews for this report</p>
            <ul className="divide-y rounded-xl border">
              {interviews.data.map((iv) => (
                <InterviewRow key={iv.id} iv={iv} />
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
