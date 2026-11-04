/**
 * The interviewer's voice.
 *
 * Preferred: Piper (runs in a worker, free, offline after the first download). Its audio is played
 * through Web Audio, so it reaches the speakers AND the recording, and drives the avatar's mouth.
 * Fallback: the browser's built-in speechSynthesis. It is heard live but browsers don't let it be
 * recorded, so the video then only shows the question as captions.
 */

import type { Interviewer } from '@/lib/api'

export const VOICES: Record<Interviewer, { piper: string; gender: 'female' | 'male' }> = {
  maya: { piper: 'en_US-hfc_female-medium', gender: 'female' },
  james: { piper: 'en_US-hfc_male-medium', gender: 'male' },
}

export type LoadProgress = { loaded: number; total: number }

/** Split into sentences so the first one can play while the next is synthesised. */
export function sentences(text: string): string[] {
  const parts = text.match(/[^.!?]+[.!?]+["')\]]*\s*|[^.!?]+$/g) ?? [text]
  const out: string[] = []
  for (const p of parts.map((s) => s.trim()).filter(Boolean)) {
    // Very short fragments ("Thanks.") sound better merged with what follows.
    if (out.length && out[out.length - 1].length < 25) out[out.length - 1] += ' ' + p
    else out.push(p)
  }
  return out
}

export class InterviewerVoice {
  private worker: Worker | null = null
  private nextId = 1
  private pending = new Map<number, { resolve: (b: ArrayBuffer) => void; reject: (e: Error) => void }>()
  private current: AudioBufferSourceNode | null = null
  private fallbackUtterance: SpeechSynthesisUtterance | null = null
  private cancelled = false
  mode: 'piper' | 'browser' = 'browser'
  /** 0..1 loudness of the interviewer right now (drives the mouth). */
  level = 0
  speaking = false

  constructor(
    private ctx: AudioContext,
    private outputs: AudioNode[], // speakers + the recording mix
    private interviewer: Interviewer,
  ) {}

  /** Load Piper. Resolves false (and the browser voice is used) if it can't load. */
  async load(onProgress?: (p: LoadProgress) => void, timeoutMs = 180_000): Promise<boolean> {
    try {
      this.worker = new Worker(new URL('./tts.worker.ts', import.meta.url), { type: 'module' })
      const totals = new Map<string, LoadProgress>()
      await new Promise<void>((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error('voice download timed out')), timeoutMs)
        this.worker!.onmessage = (e) => {
          const m = e.data
          if (m.type === 'progress' && m.total) {
            totals.set(m.url, { loaded: m.loaded, total: m.total })
            const all = [...totals.values()]
            onProgress?.({ loaded: all.reduce((a, b) => a + b.loaded, 0), total: all.reduce((a, b) => a + b.total, 0) })
          } else if (m.type === 'ready') {
            clearTimeout(timer)
            resolve()
          } else if (m.type === 'error') {
            clearTimeout(timer)
            reject(new Error(m.message))
          }
        }
        this.worker!.postMessage({ type: 'load', voiceId: VOICES[this.interviewer].piper })
      })
      this.worker.onmessage = (e) => {
        const m = e.data
        const p = this.pending.get(m.id)
        if (!p) return
        this.pending.delete(m.id)
        if (m.type === 'audio') p.resolve(m.wav)
        else p.reject(new Error(m.message))
      }
      // Warm up: the first inference is slow; do it before the interview starts.
      await this.synth('Hello.')
      this.mode = 'piper'
      return true
    } catch (err) {
      console.warn('Piper voice unavailable, using the browser voice:', err)
      this.worker?.terminate()
      this.worker = null
      this.mode = 'browser'
      return false
    }
  }

  private synth(text: string): Promise<ArrayBuffer> {
    const id = this.nextId++
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject })
      this.worker!.postMessage({ type: 'speak', id, text })
    })
  }

  /** Speak `text` and resolve when finished (or when stop() is called). */
  async speak(text: string, onSentence?: (s: string) => void): Promise<void> {
    this.cancelled = false
    this.speaking = true
    try {
      if (this.mode === 'piper') await this.speakPiper(text, onSentence)
      else await this.speakBrowser(text, onSentence)
    } finally {
      this.speaking = false
      this.level = 0
    }
  }

  private async speakPiper(text: string, onSentence?: (s: string) => void) {
    const parts = sentences(text)
    let next = this.synth(parts[0])
    for (let i = 0; i < parts.length && !this.cancelled; i++) {
      let wav: ArrayBuffer
      try {
        wav = await next
      } catch {
        // One failed sentence shouldn't silence the interviewer: say the rest with the browser voice.
        await this.speakBrowser(parts.slice(i).join(' '), onSentence)
        return
      }
      if (i + 1 < parts.length) next = this.synth(parts[i + 1]) // synthesise ahead while this one plays
      if (this.cancelled) return
      onSentence?.(parts[i])
      await this.play(await this.ctx.decodeAudioData(wav))
    }
  }

  private play(buffer: AudioBuffer): Promise<void> {
    return new Promise((resolve) => {
      const src = this.ctx.createBufferSource()
      src.buffer = buffer
      const analyser = this.ctx.createAnalyser()
      analyser.fftSize = 512
      src.connect(analyser)
      for (const out of this.outputs) src.connect(out)
      const data = new Uint8Array(analyser.fftSize)
      let raf = 0
      const meter = () => {
        analyser.getByteTimeDomainData(data)
        let sum = 0
        for (const v of data) sum += ((v - 128) / 128) ** 2
        this.level = Math.min(1, Math.sqrt(sum / data.length) * 4)
        raf = requestAnimationFrame(meter)
      }
      meter()
      let finished = false
      const finish = () => {
        if (finished) return
        finished = true
        cancelAnimationFrame(raf)
        clearTimeout(watchdog)
        this.level = 0
        this.current = null
        resolve()
      }
      src.onended = finish
      // Never let a stalled audio device freeze the interview.
      const watchdog = setTimeout(finish, (buffer.duration + 2) * 1000)
      this.current = src
      src.start()
    })
  }

  private speakBrowser(text: string, onSentence?: (s: string) => void): Promise<void> {
    return new Promise((resolve) => {
      if (!('speechSynthesis' in window)) return resolve()
      const u = new SpeechSynthesisUtterance(text)
      const want = VOICES[this.interviewer].gender
      const voices = speechSynthesis.getVoices().filter((v) => v.lang.startsWith('en'))
      u.voice =
        voices.find((v) => new RegExp(want === 'female' ? 'female|zira|samantha|aria|jenny' : 'male|david|daniel|guy|mark', 'i').test(v.name)) ??
        voices[0] ??
        null
      u.rate = 1
      // No audio to measure: animate the mouth with a gentle pulse while speaking.
      let raf = 0
      const pulse = () => {
        this.level = 0.35 + 0.3 * Math.abs(Math.sin(performance.now() / 90))
        raf = requestAnimationFrame(pulse)
      }
      u.onstart = () => {
        onSentence?.(text)
        pulse()
      }
      let finished = false
      const finish = () => {
        if (finished) return
        finished = true
        cancelAnimationFrame(raf)
        clearTimeout(watchdog)
        this.level = 0
        resolve()
      }
      u.onend = u.onerror = finish
      // Some browsers never fire onend (or have no voices at all); give up after a generous estimate.
      const watchdog = setTimeout(finish, 3000 + text.split(/\s+/).length * 500)
      this.fallbackUtterance = u
      speechSynthesis.speak(u)
    })
  }

  stop() {
    this.cancelled = true
    try {
      this.current?.stop()
    } catch {
      /* already stopped */
    }
    if (this.fallbackUtterance) speechSynthesis.cancel()
  }

  dispose() {
    this.stop()
    this.worker?.terminate()
    for (const p of this.pending.values()) p.reject(new Error('disposed'))
    this.pending.clear()
  }
}
