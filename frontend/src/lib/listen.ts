/**
 * Captures one spoken answer and turns it into text.
 *  - "groq": record the microphone, then send the clip to the server (Groq Whisper). Any browser.
 *  - "browser": the browser's own speech recognition, with live text. Chrome and Edge only.
 */

interface RecognitionResult {
  isFinal: boolean
  0: { transcript: string }
}
interface RecognitionEvent {
  resultIndex: number
  results: ArrayLike<RecognitionResult>
}
interface Recognition {
  continuous: boolean
  interimResults: boolean
  lang: string
  onresult: ((e: RecognitionEvent) => void) | null
  onend: (() => void) | null
  onerror: ((e: { error: string }) => void) | null
  start(): void
  stop(): void
}
type RecognitionCtor = new () => Recognition

const Recognition: RecognitionCtor | undefined =
  (window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor })
    .SpeechRecognition ??
  (window as unknown as { webkitSpeechRecognition?: RecognitionCtor }).webkitSpeechRecognition

export const browserRecognitionSupported = () => Boolean(Recognition)

export function pickMime(candidates: string[]): string | undefined {
  return candidates.find((m) => typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(m))
}

export class AnswerListener {
  private recorder: MediaRecorder | null = null
  private chunks: Blob[] = []
  private recognition: Recognition | null = null
  private finals: string[] = []
  private interim = ''
  private active = false
  private ended: Promise<void> = Promise.resolve()

  constructor(
    private mic: MediaStream,
    readonly mode: 'groq' | 'browser',
    private transcribe: (audio: Blob) => Promise<string>,
  ) {}

  start(onText?: (live: string) => void) {
    this.active = true
    this.finals = []
    this.interim = ''
    if (this.mode === 'groq') {
      const mimeType = pickMime(['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'])
      this.chunks = []
      this.recorder = new MediaRecorder(new MediaStream(this.mic.getAudioTracks()), mimeType ? { mimeType } : undefined)
      this.recorder.ondataavailable = (e) => e.data.size && this.chunks.push(e.data)
      this.ended = new Promise((resolve) => (this.recorder!.onstop = () => resolve()))
      this.recorder.start(1000)
      return
    }
    if (!Recognition) return
    const rec = new Recognition()
    rec.continuous = true
    rec.interimResults = true
    rec.lang = 'en-US'
    rec.onresult = (e) => {
      let interim = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i]
        if (r.isFinal) this.finals.push(r[0].transcript.trim())
        else interim += r[0].transcript
      }
      this.interim = interim.trim()
      onText?.([...this.finals, this.interim].filter(Boolean).join(' '))
    }
    let resolveEnded = () => {}
    this.ended = new Promise((resolve) => (resolveEnded = resolve))
    rec.onend = () => {
      // Chrome stops after a pause; keep listening until the candidate says they're done.
      if (this.active) {
        try {
          rec.start()
          return
        } catch {
          /* fall through */
        }
      }
      resolveEnded()
    }
    rec.onerror = (e) => {
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') this.active = false
    }
    this.recognition = rec
    rec.start()
  }

  /** Stop listening and return the answer text. */
  async stop(): Promise<string> {
    this.active = false
    if (this.mode === 'groq' && this.recorder) {
      if (this.recorder.state !== 'inactive') this.recorder.stop()
      await this.ended
      const blob = new Blob(this.chunks, { type: this.recorder.mimeType || 'audio/webm' })
      this.recorder = null
      return blob.size ? this.transcribe(blob) : ''
    }
    if (this.recognition) {
      this.recognition.stop()
      await Promise.race([this.ended, new Promise((r) => setTimeout(r, 1500))])
      this.recognition = null
    }
    return [...this.finals, this.interim].filter(Boolean).join(' ').trim()
  }

  cancel() {
    this.active = false
    try {
      if (this.recorder?.state !== 'inactive') this.recorder?.stop()
      this.recognition?.stop()
    } catch {
      /* already stopped */
    }
  }
}
