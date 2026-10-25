/** Formats numeric seconds into clean "MM:SS" or "HH:MM:SS" time string */
export function formatTime(seconds: number): string {
  if (isNaN(seconds) || seconds < 0) return '00:00'
  const totalSecs = Math.floor(seconds)
  const hours = Math.floor(totalSecs / 3600)
  const minutes = Math.floor((totalSecs % 3600) / 60)
  const secs = totalSecs % 60

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}
