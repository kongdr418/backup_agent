declare module '@panzoom/panzoom' {
  interface PanzoomOptions {
    maxScale?: number
    minScale?: number
    step?: number
    contain?: 'inside' | 'outside' | 'static'
    animate?: boolean
  }
  interface PanzoomInstance {
    destroy(): void
    reset(): void
    zoomTo(scale: number, opts?: { animate?: boolean }): void
    getScale(): number
    getPan(): { x: number; y: number }
    pan(x: number, y: number, opts?: { animate?: boolean }): void
    zoomWithWheel(event: WheelEvent): void
  }
  export default function panzoom(el: HTMLElement, opts?: PanzoomOptions): PanzoomInstance
}
