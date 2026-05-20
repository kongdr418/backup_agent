import { ref, onMounted, type Ref } from 'vue'

/**
 * Extract filename from a full path (handles both Windows and Unix paths)
 */
function extractFilename(filePath: string): string {
  const parts = filePath.replace(/\\/g, '/').split('/')
  return parts[parts.length - 1] || ''
}

/**
 * Restore base64 media data that was stripped during localStorage persistence.
 * Fetches the file from the backend on demand and converts to a data URL.
 */
export function useMediaRestore(
  data: Ref<Record<string, unknown> | undefined>,
): { audioBase64: Ref<string>; imageBase64: Ref<string>; loading: Ref<boolean> } {
  const audioBase64 = ref('')
  const imageBase64 = ref('')
  const loading = ref(false)

  onMounted(async () => {
    const d = data.value
    if (!d) return

    const tasks: Promise<void>[] = []

    if (d.audio_dropped && d.audio_path && !d.audioBase64) {
      tasks.push(
        fetchMediaAsDataUrl(d.audio_path as string, 'audio').then((url) => {
          audioBase64.value = url
        }).catch(() => { /* ignore */ }),
      )
    } else if (d.audioBase64) {
      audioBase64.value = d.audioBase64 as string
    }

    if (d.image_dropped && d.image_path && !d.imageBase64) {
      tasks.push(
        fetchMediaAsDataUrl(d.image_path as string, 'image').then((url) => {
          imageBase64.value = url
        }).catch(() => { /* ignore */ }),
      )
    } else if (d.imageBase64) {
      imageBase64.value = d.imageBase64 as string
    }

    if (tasks.length) {
      loading.value = true
      await Promise.all(tasks)
      loading.value = false
    }
  })

  return { audioBase64, imageBase64, loading }
}

/**
 * Fetch media using the appropriate API endpoint.
 * - Images: /api/graphic/image/{filename} returns {image: base64}
 * - Audio: /api/video/audio/{filename} returns {audio: base64}
 */
async function fetchMediaAsDataUrl(filePath: string, type: 'image' | 'audio'): Promise<string> {
  const filename = extractFilename(filePath)
  if (!filename) throw new Error('Could not extract filename from path')

  const endpoint = type === 'image'
    ? `/api/graphic/image/${encodeURIComponent(filename)}`
    : `/api/video/audio/${encodeURIComponent(filename)}`

  const resp = await fetch(endpoint)
  if (!resp.ok) throw new Error(`API request failed: ${resp.status}`)

  const json = await resp.json()
  const base64Data = type === 'image' ? json.image : json.audio

  if (!base64Data) throw new Error(`No ${type} data in response`)

  const mimeType = type === 'image' ? 'image/jpeg' : 'audio/mpeg'
  return `data:${mimeType};base64,${base64Data}`
}
