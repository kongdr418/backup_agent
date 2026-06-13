/**
 * URL builders for static media served by the backend.
 * The actual byte streams are fetched via <img>, <audio>, <iframe>, etc.
 */

export function graphicImageUrl(filename: string): string {
  return `/api/graphic/image/${encodeURIComponent(filename)}`
}

export function videoAudioUrl(filename: string): string {
  return `/api/video/audio/${encodeURIComponent(filename)}`
}
