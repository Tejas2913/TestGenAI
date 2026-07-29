/**
 * ShortcutsDialog — modal listing all keyboard shortcuts.
 * Triggered by the ⌨ button in the navbar, or by pressing ?.
 * Accepts optional isOpen/onClose for external control (? shortcut).
 */
import { useState, useEffect, useCallback } from 'react'

const SHORTCUTS = [
  { keys: ['Ctrl', 'Enter'],    description: 'Generate tests' },
  { keys: ['Ctrl', 'K'],        description: 'Focus source editor' },
  { keys: ['Ctrl', 'Shift', 'E'], description: 'Load example function' },
  { keys: ['Ctrl', 'Shift', 'C'], description: 'Copy generated code' },
  { keys: ['/'],                description: 'Focus search (History page)' },
  { keys: ['?'],                description: 'Open this help dialog' },
  { keys: ['Esc'],              description: 'Close dialogs' },
]

export default function ShortcutsDialog({ externalOpen, onExternalClose }) {
  const [internalOpen, setInternalOpen] = useState(false)
  const isOpen = externalOpen ?? internalOpen
  const close  = useCallback(() => {
    setInternalOpen(false)
    onExternalClose?.()
  }, [onExternalClose])

  // Sync external open state
  useEffect(() => {
    if (externalOpen) setInternalOpen(false) // don't double-track
  }, [externalOpen])

  // Esc to close
  useEffect(() => {
    if (!isOpen) return
    const h = (e) => { if (e.key === 'Escape') { e.stopPropagation(); close() } }
    document.addEventListener('keydown', h)
    return () => document.removeEventListener('keydown', h)
  }, [isOpen, close])

  return (
    <>
      {/* Trigger button */}
      <button
        onClick={() => setInternalOpen(true)}
        className="hidden rounded-lg p-2 text-gray-400 transition-colors
                   hover:bg-gray-100 hover:text-gray-600
                   dark:text-gray-500 dark:hover:bg-gray-800 dark:hover:text-gray-300
                   cursor-pointer sm:block"
        aria-label="Keyboard shortcuts"
        title="Keyboard shortcuts (?)"
      >
        <svg className="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M2 4.75C2 3.784 2.784 3 3.75 3h12.5c.966 0 1.75.784 1.75 1.75v8.5A1.75 1.75 0 0116.25 15H3.75A1.75 1.75 0 012 13.25v-8.5zm1.75-.25a.25.25 0 00-.25.25v8.5c0 .138.112.25.25.25h12.5a.25.25 0 00.25-.25v-8.5a.25.25 0 00-.25-.25H3.75z" clipRule="evenodd" />
          <path d="M5 6.25a.75.75 0 01.75-.75h.5a.75.75 0 010 1.5h-.5A.75.75 0 015 6.25zm3 0a.75.75 0 01.75-.75h.5a.75.75 0 010 1.5h-.5A.75.75 0 018 6.25zm3 0a.75.75 0 01.75-.75h.5a.75.75 0 010 1.5h-.5a.75.75 0 01-.75-.75zm3 0a.75.75 0 01.75-.75h.5a.75.75 0 010 1.5h-.5a.75.75 0 01-.75-.75zM5 9.25a.75.75 0 01.75-.75h.5a.75.75 0 010 1.5h-.5A.75.75 0 015 9.25zm3 0a.75.75 0 01.75-.75h.5a.75.75 0 010 1.5h-.5A.75.75 0 018 9.25zm6 0a.75.75 0 01.75-.75h.5a.75.75 0 010 1.5h-.5a.75.75 0 01-.75-.75zM7.25 11.5a.75.75 0 000 1.5h5.5a.75.75 0 000-1.5h-5.5z" />
        </svg>
      </button>

      {/* Modal */}
      {isOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
          onClick={close}
        >
          <div
            className="mx-4 w-full max-w-sm rounded-xl border border-gray-200 bg-white p-6 shadow-2xl
                       dark:border-gray-700 dark:bg-gray-900 motion-safe:animate-fade-in"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="shortcuts-title"
          >
            <div className="mb-4 flex items-center justify-between">
              <h3 id="shortcuts-title" className="text-base font-semibold text-gray-900 dark:text-white">
                Keyboard Shortcuts
              </h3>
              <button
                onClick={close}
                className="rounded-lg p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 cursor-pointer"
                aria-label="Close"
              >
                <svg className="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
                </svg>
              </button>
            </div>

            <div className="space-y-3">
              {SHORTCUTS.map(({ keys, description }) => (
                <div key={description} className="flex items-center justify-between gap-4">
                  <span className="text-sm text-gray-600 dark:text-gray-300">{description}</span>
                  <div className="flex shrink-0 items-center gap-1">
                    {keys.map((key) => (
                      <kbd
                        key={key}
                        className="rounded border border-gray-300 bg-gray-100 px-1.5 py-0.5 font-mono text-[11px]
                                   text-gray-600 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300"
                      >
                        {key}
                      </kbd>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
