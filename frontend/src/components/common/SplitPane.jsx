import { useCallback, useEffect, useRef, useState } from 'react'
import { usePreferencesStore } from '../../stores/usePreferencesStore'

/**
 * SplitPane — horizontally resizable container with draggable divider.
 *
 * Props:
 *   left       – React node for the left panel
 *   right      – React node for the right panel
 *   minLeft    – minimum left width in % (default 25)
 *   minRight   – minimum right width in % (default 30)
 */

const MIN_LEFT = 25
const MIN_RIGHT = 30

export default function SplitPane({ left, right }) {
  const savedSize = usePreferencesStore((s) => s.splitPaneSize)
  const setSavedSize = usePreferencesStore((s) => s.setSplitPaneSize)

  const [leftPercent, setLeftPercent] = useState(savedSize)
  const containerRef = useRef(null)
  const isDragging = useRef(false)
  const leftPercentRef = useRef(savedSize)

  const handleMouseDown = useCallback((e) => {
    e.preventDefault()
    isDragging.current = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }, [])

  const handleMouseMove = useCallback(
    (e) => {
      if (!isDragging.current || !containerRef.current) return
      const rect = containerRef.current.getBoundingClientRect()
      const x = e.clientX - rect.left
      let pct = (x / rect.width) * 100
      pct = Math.max(MIN_LEFT, Math.min(100 - MIN_RIGHT, pct))
      leftPercentRef.current = pct
      setLeftPercent(pct)
    },
    []
  )

  const handleMouseUp = useCallback(() => {
    if (!isDragging.current) return
    isDragging.current = false
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    // Persist the final position — read from ref to avoid render-time state read
    setSavedSize(Math.round(leftPercentRef.current))
  }, [setSavedSize])

  useEffect(() => {
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [handleMouseMove, handleMouseUp])

  return (
    <div
      ref={containerRef}
      className="flex h-full w-full overflow-hidden"
    >
      {/* Left panel */}
      <div
        className="h-full overflow-auto"
        style={{ width: `${leftPercent}%` }}
      >
        {left}
      </div>

      {/* Drag handle */}
      <div
        onMouseDown={handleMouseDown}
        className="group relative z-10 flex w-1.5 shrink-0 cursor-col-resize items-center justify-center
                   bg-gray-100 transition-colors hover:bg-blue-200
                   dark:bg-gray-800 dark:hover:bg-blue-800"
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize panels"
        tabIndex={0}
      >
        {/* Visual grip dots */}
        <div className="flex flex-col gap-1 opacity-0 transition-opacity group-hover:opacity-100">
          <span className="h-1 w-1 rounded-full bg-gray-400 dark:bg-gray-500" />
          <span className="h-1 w-1 rounded-full bg-gray-400 dark:bg-gray-500" />
          <span className="h-1 w-1 rounded-full bg-gray-400 dark:bg-gray-500" />
        </div>
      </div>

      {/* Right panel */}
      <div
        className="h-full overflow-auto"
        style={{ width: `${100 - leftPercent}%` }}
      >
        {right}
      </div>
    </div>
  )
}
