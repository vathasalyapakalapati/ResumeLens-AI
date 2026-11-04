/**
 * Interview videos are kept only in this browser (IndexedDB), never uploaded.
 * Keyed by interview id. A 15-minute interview is roughly 50-150 MB.
 */

const DB = 'resumelens-recordings'
const STORE = 'videos'

export interface Recording {
  id: string
  blob: Blob
  mimeType: string
  savedAt: number
}

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1)
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: 'id' })
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function run<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await open()
  try {
    return await new Promise<T>((resolve, reject) => {
      const req = fn(db.transaction(STORE, mode).objectStore(STORE))
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => reject(req.error)
    })
  } finally {
    db.close()
  }
}

export const saveRecording = (id: string, blob: Blob) =>
  run('readwrite', (s) => s.put({ id, blob, mimeType: blob.type, savedAt: Date.now() } satisfies Recording))

export const getRecording = (id: string) => run<Recording | undefined>('readonly', (s) => s.get(id))

export const deleteRecording = (id: string) => run('readwrite', (s) => s.delete(id))

/** Ask the browser not to evict recordings when disk space runs low. */
export const persistStorage = () => navigator.storage?.persist?.().catch(() => false)

export const extensionFor = (mime: string) => (mime.includes('mp4') ? 'mp4' : 'webm')
