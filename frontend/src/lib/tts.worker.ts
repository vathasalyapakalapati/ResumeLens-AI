/// <reference lib="webworker" />
/**
 * Runs Piper text-to-speech off the main thread, so the interview video keeps rendering smoothly
 * while a sentence is synthesised. The voice model (~60 MB) is downloaded once and cached by the
 * browser (origin private file system).
 */
import { TtsSession } from '@mintplex-labs/piper-tts-web'

type In = { type: 'load'; voiceId: string } | { type: 'speak'; id: number; text: string }

let session: TtsSession | null = null

self.onmessage = async (e: MessageEvent<In>) => {
  const msg = e.data
  try {
    if (msg.type === 'load') {
      session = await TtsSession.create({
        voiceId: msg.voiceId,
        progress: (p) => self.postMessage({ type: 'progress', loaded: p.loaded, total: p.total, url: p.url }),
      })
      self.postMessage({ type: 'ready' })
    } else if (msg.type === 'speak') {
      if (!session) throw new Error('voice not loaded')
      const wav = await session.predict(msg.text)
      const buf = await wav.arrayBuffer()
      self.postMessage({ type: 'audio', id: msg.id, wav: buf }, [buf])
    }
  } catch (err) {
    self.postMessage({ type: 'error', id: msg.type === 'speak' ? msg.id : undefined, message: String(err) })
  }
}
