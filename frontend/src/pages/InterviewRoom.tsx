import {
  ArrowLeft,
  CameraOff,
  Check,
  Loader2,
  MessageSquareText,
  Mic,
  MicOff,
  PhoneOff,
  RotateCcw,
  Send,
  Video,
  VideoOff,
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import {
  answerInterview,
  errorMessage,
  finishInterview,
  type InterviewDetail,
  type InterviewTurn,
  transcribeAnswer,
} from '@/lib/api'
import { drawInterviewer } from '@/lib/avatar'
import { clock, useInterview, useInterviewConfig } from '@/lib/interviews'
import { AnswerListener, browserRecognitionSupported, pickMime } from '@/lib/listen'
import { persistStorage, saveRecording } from '@/lib/recordings'
import { cn } from '@/lib/utils'
import { InterviewerVoice, type LoadProgress } from '@/lib/voice'

const W = 1280
const H = 720

type Phase = 'speaking' | 'listening' | 'processing' | 'ended'

interface Media {
  stream: MediaStream
  hasVideo: boolean
}

async function getMedia(): Promise<Media> {
  const audio = { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 }, audio })
    return { stream, hasVideo: true }
  } catch (err) {
    // No camera (or it's busy): an audio-only interview still works.
    if (err instanceof DOMException && ['NotFoundError', 'NotReadableError', 'OverconstrainedError'].includes(err.name)) {
      return { stream: await navigator.mediaDevices.getUserMedia({ audio }), hasVideo: false }
    }
    throw err
  }
}

function mediaError(err: unknown): string {
  if (err instanceof DOMException) {
    if (err.name === 'NotAllowedError')
      return 'Camera and microphone access was blocked. Click the camera icon in the address bar, allow both, then reload this page.'
    if (err.name === 'NotFoundError') return 'No microphone was found. Plug one in and reload this page.'
    if (err.name === 'NotReadableError') return 'Your camera or microphone is being used by another app. Close it and reload.'
  }
  if (!window.isSecureContext) return 'Camera access needs a secure page (https or localhost).'
  return 'Could not start your camera and microphone.'
}

/** Wrap text into lines that fit `maxWidth` on the canvas. */
function wrap(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string[] {
  const lines: string[] = []
  let line = ''
  for (const word of text.split(/\s+/)) {
    const test = line ? `${line} ${word}` : word
    if (ctx.measureText(test).width > maxWidth && line) {
      lines.push(line)
      line = word
    } else line = test
  }
  if (line) lines.push(line)
  return lines
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath()
  ctx.roundRect(x, y, w, h, r)
}

export function InterviewRoom() {
  const { id = '' } = useParams()
  const interview = useInterview(id)
  const config = useInterviewConfig()

  if (interview.isPending || config.isPending)
    return (
      <div className="grid min-h-screen place-items-center bg-zinc-950 text-zinc-300">
        <Loader2 className="size-8 animate-spin" />
      </div>
    )
  if (interview.isError || config.isError)
    return (
      <div className="grid min-h-screen place-items-center bg-zinc-950 p-6 text-center text-zinc-300">
        <div className="space-y-3">
          <p>{errorMessage(interview.error ?? config.error)}</p>
          <Link to="/history" className="underline">
            Back to history
          </Link>
        </div>
      </div>
    )
  if (interview.data.status === 'completed') return <Navigate to={`/interviews/${id}`} replace />
  return <Room initial={interview.data} transcription={config.data.transcription} />
}

function Room({ initial, transcription }: { initial: InterviewDetail; transcription: 'groq' | 'browser' }) {
  const navigate = useNavigate()
  const id = initial.id

  // ---- setup state ----
  const [media, setMedia] = useState<Media | null>(null)
  const [mediaErr, setMediaErr] = useState<string | null>(null)
  const [voiceState, setVoiceState] = useState<'loading' | 'ready' | 'fallback'>('loading')
  const [progress, setProgress] = useState<LoadProgress | null>(null)
  const [joined, setJoined] = useState(false)

  // ---- live state ----
  const [phase, setPhase] = useState<Phase>('speaking')
  const [turns, setTurns] = useState<InterviewTurn[]>(initial.turns)
  const [question, setQuestion] = useState(initial.current_question)
  const [live, setLive] = useState('')
  const [typed, setTyped] = useState('')
  const [micOn, setMicOn] = useState(true)
  const [camOn, setCamOn] = useState(true)
  const [showTranscript, setShowTranscript] = useState(true)
  const [elapsed, setElapsed] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const canvasRef = useRef<HTMLCanvasElement>(null)
  const camRef = useRef<HTMLVideoElement>(null)
  const previewRef = useRef<HTMLVideoElement>(null)
  const ctxRef = useRef<AudioContext | null>(null)
  const recordDestRef = useRef<MediaStreamAudioDestinationNode | null>(null)
  const voiceRef = useRef<InterviewerVoice | null>(null)
  const listenerRef = useRef<AnswerListener | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const startRef = useRef(0)
  const captionRef = useRef('')
  const phaseRef = useRef<Phase>('speaking')
  const camOnRef = useRef(true)
  const micLevelRef = useRef(0)
  const questionRef = useRef(initial.current_question)
  const endedRef = useRef(false)

  const canListen = transcription === 'groq' || browserRecognitionSupported()
  const now = () => (startRef.current ? (performance.now() - startRef.current) / 1000 : 0)
  const setPhaseBoth = (p: Phase) => {
    phaseRef.current = p
    setPhase(p)
  }

  // 1. Camera + microphone, audio graph, and the voice download, as soon as the page opens.
  useEffect(() => {
    let cancelled = false
    endedRef.current = false // React dev mode mounts twice; the first cleanup must not end the call
    const ctx = new AudioContext()
    const dest = ctx.createMediaStreamDestination()
    ctxRef.current = ctx
    recordDestRef.current = dest
    const voice = new InterviewerVoice(ctx, [ctx.destination, dest], initial.interviewer)
    voiceRef.current = voice
    voice.load(setProgress).then((ok) => !cancelled && setVoiceState(ok ? 'ready' : 'fallback'))

    getMedia()
      .then((m) => {
        if (cancelled) return m.stream.getTracks().forEach((t) => t.stop())
        setMedia(m)
        setCamOn(m.hasVideo)
        camOnRef.current = m.hasVideo
        // Mic into the recording (not the speakers, to avoid echo), plus a level meter.
        const src = ctx.createMediaStreamSource(m.stream)
        src.connect(dest)
        const analyser = ctx.createAnalyser()
        analyser.fftSize = 512
        src.connect(analyser)
        const data = new Uint8Array(analyser.fftSize)
        const meter = () => {
          if (cancelled) return
          analyser.getByteTimeDomainData(data)
          let sum = 0
          for (const v of data) sum += ((v - 128) / 128) ** 2
          micLevelRef.current = Math.min(1, Math.sqrt(sum / data.length) * 5)
          requestAnimationFrame(meter)
        }
        meter()
      })
      .catch((err) => !cancelled && setMediaErr(mediaError(err)))

    return () => {
      cancelled = true
      endedRef.current = true
      voice.dispose()
      listenerRef.current?.cancel()
      if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
      ctx.close().catch(() => undefined)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    return () => media?.stream.getTracks().forEach((t) => t.stop())
  }, [media])

  // Preview (setup screen) and the hidden video the canvas draws from.
  useEffect(() => {
    if (!media) return
    for (const el of [previewRef.current, camRef.current]) if (el) el.srcObject = media.stream
  }, [media, joined])

  // Warn before leaving mid-interview.
  useEffect(() => {
    if (!joined) return
    const warn = (e: BeforeUnloadEvent) => {
      if (!endedRef.current) e.preventDefault()
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [joined])

  // 2. Draw every frame: interviewer, your camera in the corner, captions, header. This canvas IS the recording.
  useEffect(() => {
    if (!joined) return
    const canvas = canvasRef.current!
    const g = canvas.getContext('2d')!
    let raf = 0
    const frame = () => {
      const t = performance.now()
      const voice = voiceRef.current
      const p = phaseRef.current
      drawInterviewer(g, W, H, initial.interviewer, {
        level: voice?.level ?? 0,
        speaking: Boolean(voice?.speaking),
        thinking: p === 'processing',
        time: t,
      })

      // Header: interviewer name, question counter, REC + timer.
      g.fillStyle = 'rgba(15,18,25,0.55)'
      roundRect(g, 24, 22, 330, 58, 14)
      g.fill()
      g.fillStyle = '#fff'
      g.font = '600 22px Inter, system-ui, sans-serif'
      g.fillText(initial.interviewer_name, 42, 50)
      g.font = '15px Inter, system-ui, sans-serif'
      g.fillStyle = 'rgba(255,255,255,0.8)'
      const q = Math.min(questionRef.current, initial.question_count)
      g.fillText(`${initial.interviewer_title} · Question ${q} of ${initial.question_count}`, 42, 70)
      const secs = (t - startRef.current) / 1000
      g.fillStyle = 'rgba(15,18,25,0.55)'
      roundRect(g, W - 160, 22, 136, 40, 12)
      g.fill()
      g.fillStyle = Math.floor(t / 600) % 2 ? '#ef4444' : '#b91c1c'
      g.beginPath()
      g.arc(W - 138, 42, 7, 0, Math.PI * 2)
      g.fill()
      g.fillStyle = '#fff'
      g.font = '600 17px Inter, system-ui, sans-serif'
      g.fillText(`REC ${clock(secs)}`, W - 124, 48)

      // Your camera, picture-in-picture (mirrored, like a video call).
      const pw = 300
      const ph = 169
      const px = W - pw - 24
      const py = H - ph - 120
      g.save()
      roundRect(g, px, py, pw, ph, 16)
      g.clip()
      const cam = camRef.current
      if (camOnRef.current && cam && cam.readyState >= 2) {
        const vw = cam.videoWidth || 16
        const vh = cam.videoHeight || 9
        const scale = Math.max(pw / vw, ph / vh)
        const dw = vw * scale
        const dh = vh * scale
        g.translate(px + pw, py)
        g.scale(-1, 1)
        g.drawImage(cam, (pw - dw) / 2, (ph - dh) / 2, dw, dh)
      } else {
        g.fillStyle = '#1f2430'
        g.fillRect(px, py, pw, ph)
        g.fillStyle = 'rgba(255,255,255,0.7)'
        g.font = '16px Inter, system-ui, sans-serif'
        g.textAlign = 'center'
        g.fillText(initial.candidate_name, px + pw / 2, py + ph / 2 + 5)
        g.textAlign = 'left'
      }
      g.restore()
      // Speaking ring around your tile while you talk.
      const lvl = p === 'listening' ? micLevelRef.current : 0
      g.strokeStyle = lvl > 0.08 ? `rgba(34,197,94,${0.5 + lvl / 2})` : 'rgba(255,255,255,0.35)'
      g.lineWidth = lvl > 0.08 ? 4 : 2
      roundRect(g, px, py, pw, ph, 16)
      g.stroke()

      // Captions.
      const caption = captionRef.current
      if (caption) {
        g.font = '500 24px Inter, system-ui, sans-serif'
        const lines = wrap(g, caption, W - 420).slice(-3)
        const boxH = lines.length * 34 + 28
        const by = H - boxH - 24
        g.fillStyle = 'rgba(10,12,18,0.72)'
        roundRect(g, 24, by, W - 380, boxH, 14)
        g.fill()
        g.fillStyle = '#fff'
        lines.forEach((l, i) => g.fillText(l, 44, by + 40 + i * 34))
      }
      raf = requestAnimationFrame(frame)
    }
    frame()
    const tick = setInterval(() => setElapsed(now()), 500)
    return () => {
      cancelAnimationFrame(raf)
      clearInterval(tick)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [joined])

  // 3. Conversation.
  const say = useCallback(async (text: string) => {
    setPhaseBoth('speaking')
    captionRef.current = ''
    try {
      await voiceRef.current?.speak(text, (sentence) => (captionRef.current = sentence))
    } catch (err) {
      console.warn('interviewer voice failed; the question stays on screen as a caption', err)
      captionRef.current = text
    }
  }, [])

  const listen = useCallback(() => {
    if (endedRef.current) return
    setLive('')
    setTyped('')
    captionRef.current = ''
    setPhaseBoth('listening')
    if (!canListen || !media) return
    const listener = new AnswerListener(media.stream, transcription, (blob) => transcribeAnswer(id, blob))
    listenerRef.current = listener
    listener.start((text) => {
      setLive(text)
      captionRef.current = `${initial.candidate_name}: ${text}`
    })
  }, [canListen, media, transcription, id, initial.candidate_name])

  const submit = useCallback(async () => {
    if (phaseRef.current !== 'listening') return
    setPhaseBoth('processing')
    setError(null)
    captionRef.current = transcription === 'groq' ? 'Transcribing your answer…' : ''
    try {
      const fromVoice = (await listenerRef.current?.stop()) ?? ''
      listenerRef.current = null
      const text = [fromVoice, typed.trim()].filter(Boolean).join(' ')
      const at = now()
      setTurns((t) => [...t, { role: 'candidate', kind: 'answer', q: questionRef.current, text, t: at }])
      captionRef.current = ''
      const res = await answerInterview(id, { text, elapsed: at })
      questionRef.current = res.current_question
      setQuestion(res.current_question)
      setTurns((t) => [...t, { ...res.turn, t: now() }])
      await say(res.turn.text)
      if (res.done) {
        setPhaseBoth('ended')
        captionRef.current = 'Interview complete. Click "End & get feedback".'
      } else listen()
    } catch (err) {
      setError(errorMessage(err))
      listen() // let them answer again
    }
  }, [id, say, listen, typed, transcription])

  const join = async () => {
    await ctxRef.current?.resume() // must happen inside the click, or the browser keeps audio muted
    void persistStorage()
    setJoined(true)
  }

  // Once the call screen (and its canvas) exists: start recording, then the interviewer speaks.
  const startedRef = useRef(false)
  useEffect(() => {
    if (!joined || startedRef.current || !canvasRef.current) return
    startedRef.current = true
    const stream = new MediaStream([
      ...canvasRef.current.captureStream(30).getVideoTracks(),
      ...recordDestRef.current!.stream.getAudioTracks(),
    ])
    const mimeType = pickMime(['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm', 'video/mp4'])
    const rec = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 1_000_000 })
    chunksRef.current = []
    rec.ondataavailable = (e) => e.data.size && chunksRef.current.push(e.data)
    rec.start(1000)
    recorderRef.current = rec
    startRef.current = performance.now()
    // First question, or when rejoining, repeat the last thing the interviewer said.
    const last = [...turns].reverse().find((t) => t.role === 'interviewer')
    void say(last?.text ?? '').then(() => (initial.done ? setPhaseBoth('ended') : listen()))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [joined])

  const repeat = async () => {
    if (phaseRef.current !== 'listening') return
    listenerRef.current?.cancel()
    listenerRef.current = null
    const last = [...turns].reverse().find((t) => t.role === 'interviewer')
    if (last) await say(last.text)
    listen()
  }

  const toggleMic = () => {
    const on = !micOn
    media?.stream.getAudioTracks().forEach((t) => (t.enabled = on))
    setMicOn(on)
  }
  const toggleCam = () => {
    const on = !camOn
    media?.stream.getVideoTracks().forEach((t) => (t.enabled = on))
    camOnRef.current = on
    setCamOn(on)
  }

  const end = async () => {
    if (phaseRef.current !== 'ended' && !window.confirm('End the interview now? Unanswered questions will be skipped.')) return
    endedRef.current = true
    setSaving(true)
    voiceRef.current?.stop()
    listenerRef.current?.cancel()
    const duration = now()
    const rec = recorderRef.current
    try {
      if (rec && rec.state !== 'inactive') {
        await new Promise<void>((resolve) => {
          rec.onstop = () => resolve()
          rec.stop()
        })
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || 'video/webm' })
        await saveRecording(id, blob).catch((e) => console.warn('could not save recording', e))
      }
      await finishInterview(id, duration)
      media?.stream.getTracks().forEach((t) => t.stop())
      navigate(`/interviews/${id}`, { replace: true })
    } catch (err) {
      setError(errorMessage(err))
      setSaving(false)
    }
  }

  // ---------- setup screen ----------
  if (!joined) {
    const pct = progress?.total ? Math.round((progress.loaded / progress.total) * 100) : 0
    return (
      <div className="min-h-screen bg-zinc-950 text-zinc-100">
        <div className="mx-auto grid max-w-5xl gap-8 px-4 py-10 lg:grid-cols-[1.4fr_1fr] lg:items-center">
          <div className="relative aspect-video overflow-hidden rounded-2xl bg-zinc-900">
            {media?.hasVideo ? (
              <video ref={previewRef} autoPlay playsInline muted className="size-full -scale-x-100 object-cover" />
            ) : (
              <div className="grid size-full place-items-center text-zinc-400">
                {mediaErr ? <CameraOff className="size-10" /> : media ? 'Microphone only (no camera found)' : <Loader2 className="size-8 animate-spin" />}
              </div>
            )}
          </div>
          <div className="space-y-5">
            <Link to={`/reports/${initial.analysis_id}`} className="inline-flex items-center gap-1 text-sm text-zinc-400 hover:text-zinc-100">
              <ArrowLeft className="size-4" /> Back to report
            </Link>
            <div>
              <h1 className="text-2xl font-semibold">Ready to join?</h1>
              <p className="text-zinc-400">
                {initial.interviewer_name} ({initial.interviewer_title}) will ask {initial.question_count} questions
                {initial.role ? ` for ${initial.role}` : ''}. Answer out loud, then press <b>Done answering</b>.
              </p>
            </div>
            <ul className="space-y-2 text-sm">
              <li className="flex items-center gap-2">
                {mediaErr ? <CameraOff className="size-4 text-red-400" /> : media ? <Check className="size-4 text-green-400" /> : <Loader2 className="size-4 animate-spin" />}
                {mediaErr ?? (media ? (media.hasVideo ? 'Camera and microphone ready' : 'Microphone ready (no camera)') : 'Asking for camera and microphone…')}
              </li>
              <li className="flex items-center gap-2">
                {voiceState === 'loading' ? <Loader2 className="size-4 animate-spin" /> : <Check className={cn('size-4', voiceState === 'ready' ? 'text-green-400' : 'text-yellow-400')} />}
                {voiceState === 'loading'
                  ? `Loading interviewer voice${pct ? ` (${pct}%, one-time ~60 MB download)` : '…'}`
                  : voiceState === 'ready'
                    ? 'Interviewer voice ready (included in the recording)'
                    : "Using the browser's voice (heard live, shown as captions in the recording)"}
              </li>
              <li className="flex items-center gap-2">
                {canListen ? <Check className="size-4 text-green-400" /> : <MessageSquareText className="size-4 text-yellow-400" />}
                {transcription === 'groq'
                  ? 'Answers transcribed with Groq Whisper'
                  : canListen
                    ? "Answers transcribed by your browser's speech recognition"
                    : 'Speech recognition needs Chrome or Edge, so you can type your answers here instead'}
              </li>
            </ul>
            {voiceState === 'loading' && (
              <div className="space-y-2">
                <div className="h-1.5 overflow-hidden rounded-full bg-zinc-800">
                  <div className="h-full bg-primary transition-all" style={{ width: `${pct}%` }} />
                </div>
                <button className="text-xs text-zinc-400 underline" onClick={() => setVoiceState('fallback')}>
                  Don't wait, use the browser voice
                </button>
              </div>
            )}
            <Button size="default" className="w-full" disabled={!media || voiceState === 'loading'} onClick={join}>
              <Video /> Join interview
            </Button>
            <p className="text-xs text-zinc-500">
              The video is recorded in your browser and saved only on this device. Keep this tab open and visible
              during the interview.
            </p>
          </div>
        </div>
      </div>
    )
  }

  // ---------- live call ----------
  return (
    <div className="flex h-screen flex-col bg-zinc-950 text-zinc-100">
      <div className="flex min-h-0 flex-1 gap-4 p-4">
        <div className="flex min-w-0 flex-1 items-center justify-center">
          <canvas ref={canvasRef} width={W} height={H} className="aspect-video max-h-full w-full max-w-full rounded-2xl bg-black object-contain shadow-2xl" />
          {/* Source for the camera tile drawn on the canvas. Not display:none, or Chrome stops decoding it. */}
          <video ref={camRef} autoPlay playsInline muted className="pointer-events-none fixed left-0 top-0 size-2 opacity-0" />
        </div>
        {showTranscript && (
          <aside className="hidden w-80 shrink-0 flex-col overflow-hidden rounded-2xl bg-zinc-900 lg:flex">
            <p className="border-b border-zinc-800 px-4 py-3 text-sm font-medium">Transcript</p>
            <ol className="flex-1 space-y-3 overflow-y-auto p-4 text-sm">
              {turns.map((t, i) => (
                <li key={i} className={cn(t.role === 'candidate' && 'text-right')}>
                  <p className="text-xs text-zinc-500">
                    {t.role === 'interviewer' ? initial.interviewer_name : 'You'} · {clock(t.t)}
                  </p>
                  <p className={cn('inline-block rounded-xl px-3 py-2 text-left', t.role === 'interviewer' ? 'bg-zinc-800' : 'bg-primary/80 text-white')}>
                    {t.text || <i className="opacity-70">(no answer)</i>}
                  </p>
                </li>
              ))}
              {phase === 'listening' && live && (
                <li className="text-right">
                  <p className="inline-block rounded-xl bg-primary/40 px-3 py-2 text-left italic">{live}</p>
                </li>
              )}
            </ol>
          </aside>
        )}
      </div>

      {(phase === 'listening' && !canListen) || error ? (
        <div className="mx-auto w-full max-w-3xl px-4">
          {error && <p className="mb-2 text-center text-sm text-red-400">{error}</p>}
          {phase === 'listening' && !canListen && (
            <textarea
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              placeholder="Type your answer here…"
              className="mb-2 h-20 w-full rounded-xl bg-zinc-900 p-3 text-sm outline-none ring-primary focus:ring-2"
            />
          )}
        </div>
      ) : null}

      <div className="flex items-center justify-center gap-3 pb-6">
        <span className="hidden w-28 text-sm tabular-nums text-zinc-400 sm:block">
          {clock(elapsed)} · Q{Math.min(question, initial.question_count)}/{initial.question_count}
        </span>
        <button onClick={toggleMic} aria-label={micOn ? 'Mute microphone' : 'Unmute microphone'} className={cn('grid size-12 place-items-center rounded-full', micOn ? 'bg-zinc-800 hover:bg-zinc-700' : 'bg-red-600')}>
          {micOn ? <Mic className="size-5" /> : <MicOff className="size-5" />}
        </button>
        <button onClick={toggleCam} disabled={!media?.hasVideo} aria-label={camOn ? 'Turn camera off' : 'Turn camera on'} className={cn('grid size-12 place-items-center rounded-full disabled:opacity-40', camOn ? 'bg-zinc-800 hover:bg-zinc-700' : 'bg-red-600')}>
          {camOn ? <Video className="size-5" /> : <VideoOff className="size-5" />}
        </button>
        <button onClick={repeat} disabled={phase !== 'listening'} aria-label="Repeat the question" className="grid size-12 place-items-center rounded-full bg-zinc-800 hover:bg-zinc-700 disabled:opacity-40">
          <RotateCcw className="size-5" />
        </button>
        {phase === 'ended' ? (
          <Button onClick={end} disabled={saving} className="h-12 rounded-full px-6">
            {saving ? <Loader2 className="animate-spin" /> : <Check />} End & get feedback
          </Button>
        ) : (
          <Button onClick={submit} disabled={phase !== 'listening'} className="h-12 min-w-44 rounded-full px-6">
            {phase === 'listening' ? <Send /> : <Loader2 className="animate-spin" />}
            {phase === 'listening' ? 'Done answering' : phase === 'speaking' ? `${initial.interviewer_name} is speaking…` : 'Thinking…'}
          </Button>
        )}
        <button onClick={() => setShowTranscript((s) => !s)} aria-label="Toggle transcript" className="hidden size-12 place-items-center rounded-full bg-zinc-800 hover:bg-zinc-700 lg:grid">
          <MessageSquareText className="size-5" />
        </button>
        <button onClick={end} disabled={saving} aria-label="End interview" className="grid size-12 place-items-center rounded-full bg-red-600 hover:bg-red-500 disabled:opacity-50">
          {saving ? <Loader2 className="size-5 animate-spin" /> : <PhoneOff className="size-5" />}
        </button>
      </div>
    </div>
  )
}
