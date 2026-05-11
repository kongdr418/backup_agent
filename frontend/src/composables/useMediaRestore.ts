import { ref, onMounted, type Ref } from 'vue'

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
        fetchMediaAsDataUrl(d.audio_path as string).then((url) => {
          audioBase64.value = url
        }).catch(() => { /* ignore */ }),
      )
    } else if (d.audioBase64) {
      audioBase64.value = d.audioBase64 as string
    }

    if (d.image_dropped && d.image_path && !d.imageBase64) {
      tasks.push(
        fetchMediaAsDataUrl(d.image_path as string).then((url) => {
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

async function fetchMediaAsDataUrl(filePath: string): Promise<string> {
  const resp = await fetch(`/api/files/download?path=${encodeURIComponent(filePath)}`)
  if (!resp.ok) throw new Error(`Failed to fetch ${filePath}`)
  const blob = await resp.blob()
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onloadend = () => resolve(reader.result as string)
    reader.onerror = reject
    reader.readAsDataURL(blob)
  })
}
