/**
 * modelCache.js
 * =============
 * High-performance IndexedDB cache for 3D GLB models.
 * 
 * - Caches fetched GLB blobs directly in the browser's IndexedDB.
 * - On repeat views or version revisits, loads instantly from local storage (0 network latency).
 * - Transparent fallback to standard network fetch when offline or on first load.
 */

const DB_NAME = 'archigen_3d_cache'
const DB_VERSION = 1
const STORE_NAME = 'glb_models'
const MAX_CACHE_ENTRIES = 25

let dbPromise = null

function getDB() {
  if (dbPromise) return dbPromise

  dbPromise = new Promise((resolve, reject) => {
    if (typeof window === 'undefined' || !window.indexedDB) {
      resolve(null)
      return
    }

    const request = window.indexedDB.open(DB_NAME, DB_VERSION)

    request.onupgradeneeded = (event) => {
      const db = event.target.result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: 'url' })
        store.createIndex('timestamp', 'timestamp', { unique: false })
      }
    }

    request.onsuccess = () => resolve(request.result)
    request.onerror = () => {
      console.warn('[ModelCache] IndexedDB open error:', request.error)
      resolve(null)
    }
  })

  return dbPromise
}

/**
 * Normalizes URL keys by removing dynamic auth query parameters (e.g. AWS presigned signatures)
 * so caching works reliably across sessions while keeping unique model keys.
 */
function normalizeCacheKey(url) {
  if (!url) return ''
  try {
    const parsed = new URL(url, window.location.href)
    // Keep pathname as the canonical key for the model
    return parsed.origin + parsed.pathname
  } catch {
    return url.split('?')[0]
  }
}

/**
 * Retrieves a cached GLB Blob URL from IndexedDB.
 * Returns null if not cached.
 */
export async function getCachedModelUrl(url) {
  const db = await getDB()
  if (!db || !url) return null

  const key = normalizeCacheKey(url)

  return new Promise((resolve) => {
    try {
      const tx = db.transaction(STORE_NAME, 'readonly')
      const store = tx.objectStore(STORE_NAME)
      const request = store.get(key)

      request.onsuccess = () => {
        const record = request.result
        if (record && record.blob) {
          const blobUrl = URL.createObjectURL(record.blob)
          resolve(blobUrl)
        } else {
          resolve(null)
        }
      }

      request.onerror = () => resolve(null)
    } catch (e) {
      console.warn('[ModelCache] Read exception:', e)
      resolve(null)
    }
  })
}

/**
 * Saves a downloaded GLB ArrayBuffer/Blob to IndexedDB for instant future loads.
 */
export async function saveModelToCache(url, blobOrBuffer) {
  const db = await getDB()
  if (!db || !url || !blobOrBuffer) return

  const key = normalizeCacheKey(url)
  const blob = blobOrBuffer instanceof Blob 
    ? blobOrBuffer 
    : new Blob([blobOrBuffer], { type: 'model/gltf-binary' })

  try {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)

    store.put({
      url: key,
      blob,
      size: blob.size,
      timestamp: Date.now(),
    })

    // Prune oldest entries if cache grows past limit
    const countRequest = store.count()
    countRequest.onsuccess = () => {
      if (countRequest.result > MAX_CACHE_ENTRIES) {
        const index = store.index('timestamp')
        const openCursor = index.openCursor()
        openCursor.onsuccess = (e) => {
          const cursor = e.target.result
          if (cursor) {
            store.delete(cursor.primaryKey)
          }
        }
      }
    }
  } catch (e) {
    console.warn('[ModelCache] Save exception:', e)
  }
}
