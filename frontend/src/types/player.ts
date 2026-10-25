/**
 * VIDYORA AI - Video Player Types & YouTube IFrame API Interfaces
 */

export type PlayerStateName =
  | 'unstarted'
  | 'ended'
  | 'playing'
  | 'paused'
  | 'buffering'
  | 'cued'
  | 'ready'

export interface VideoPlayerHandle {
  /** Seek player to a target timestamp in seconds */
  seekTo: (seconds: number, shouldPlay?: boolean) => void
  /** Start video playback */
  play: () => void
  /** Pause video playback */
  pause: () => void
  /** Toggle play/pause state */
  togglePlay: () => void
  /** Get current video playback time in seconds */
  getCurrentTime: () => number
  /** Get total video duration in seconds */
  getDuration: () => number
  /** Check if video is currently playing */
  isPlaying: () => boolean
}

export interface VideoPlayerProps {
  /** 11-character YouTube video ID */
  videoId: string
  /** Video title for accessibility and aria labels */
  title?: string | null
  /** Optional original URL for fallback link */
  originalUrl?: string
  /** Callback on periodic time updates during playback */
  onTimeUpdate?: (currentTime: number, duration: number) => void
  /** Callback when playback state changes */
  onStateChange?: (isPlaying: boolean, stateName: PlayerStateName) => void
  /** Optional styling class */
  className?: string
  /** Active concept or chunk name to display as indicator */
  activeConceptLabel?: string | null
}

// Global declaration for official YouTube IFrame Player API
declare global {
  interface Window {
    YT?: {
      Player: new (
        elementId: string | HTMLElement,
        options: YTPlayerOptions
      ) => YTPlayerInstance
      PlayerState: {
        UNSTARTED: number
        ENDED: number
        PLAYING: number
        PAUSED: number
        BUFFERING: number
        CUED: number
      }
    }
    onYouTubeIframeAPIReady?: () => void
  }
}

export interface YTPlayerOptions {
  videoId: string
  width?: string | number
  height?: string | number
  playerVars?: {
    autoplay?: 0 | 1
    controls?: 0 | 1
    modestbranding?: 0 | 1
    rel?: 0 | 1
    enablejsapi?: 0 | 1
    origin?: string
    start?: number
    playsinline?: 0 | 1
    fs?: 0 | 1
  }
  events?: {
    onReady?: (event: { target: YTPlayerInstance }) => void
    onStateChange?: (event: { data: number; target: YTPlayerInstance }) => void
    onError?: (event: { data: number; target: YTPlayerInstance }) => void
  }
}

export interface YTPlayerInstance {
  playVideo: () => void
  pauseVideo: () => void
  seekTo: (seconds: number, allowSeekAhead: boolean) => void
  getCurrentTime: () => number
  getDuration: () => number
  getPlayerState: () => number
  getPlaybackRate: () => number
  setPlaybackRate: (suggestedRate: number) => void
  getAvailablePlaybackRates: () => number[]
  setVolume: (volume: number) => void
  getVolume: () => number
  mute: () => void
  unMute: () => void
  isMuted: () => boolean
  destroy: () => void
  getIframe: () => HTMLIFrameElement
}
