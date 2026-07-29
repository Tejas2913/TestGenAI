/**
 * SettingsDialog — editor & layout preferences modal.
 *
 * Connected to usePreferencesStore (already persists to localStorage).
 * Triggered by the ⚙ button in the navbar.
 * Closes on Esc and backdrop click.
 */
import { useState, useEffect, useCallback } from 'react'
import { usePreferencesStore } from '../../stores/usePreferencesStore'
import { useThemeStore } from '../../stores/useThemeStore'

const DEFAULT_FONT_SIZE = 14
const DEFAULT_WORD_WRAP = 'on'

export default function SettingsDialog() {
  const [isOpen, setIsOpen] = useState(false)

  const editorFontSize  = usePreferencesStore((s) => s.editorFontSize)
  const wordWrap        = usePreferencesStore((s) => s.wordWrap)
  const setEditorFontSize = usePreferencesStore((s) => s.setEditorFontSize)
  const setWordWrap     = usePreferencesStore((s) => s.setWordWrap)
  const setSplitPaneSize = usePreferencesStore((s) => s.setSplitPaneSize)

  const mode    = useThemeStore((s) => s.mode)
  const setMode = useThemeStore((s) => s.setMode)

  const close = useCallback(() => setIsOpen(false), [])

  // Esc to close
  useEffect(() => {
    if (!isOpen) return
    const handler = (e) => { if (e.key === 'Escape') close() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [isOpen, close])

  const handleResetLayout = () => {
    setSplitPaneSize(40)
  }

  return (
    <>
      {/* Trigger */}
      <button
        onClick={() => setIsOpen(true)}
        className="hidden rounded-lg p-2 text-gray-400 transition-colors
                   hover:bg-gray-100 hover:text-gray-600
                   dark:text-gray-500 dark:hover:bg-gray-800 dark:hover:text-gray-300
                   cursor-pointer sm:block"
        aria-label="Settings"
        title="Settings"
      >
        <svg className="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M7.84 1.804A1 1 0 018.82 1h2.36a1 1 0 01.98.804l.331 1.652a6.993 6.993 0 011.929 1.115l1.598-.54a1 1 0 011.186.447l1.18 2.044a1 1 0 01-.205 1.251l-1.267 1.113a7.047 7.047 0 010 2.228l1.267 1.113a1 1 0 01.205 1.251l-1.18 2.044a1 1 0 01-1.186.447l-1.598-.54a6.993 6.993 0 01-1.929 1.115l-.33 1.652a1 1 0 01-.98.804H8.82a1 1 0 01-.98-.804l-.331-1.652a6.993 6.993 0 01-1.929-1.115l-1.598.54a1 1 0 01-1.186-.447l-1.18-2.044a1 1 0 01.205-1.251l1.267-1.113a7.047 7.047 0 010-2.228L1.821 7.773a1 1 0 01-.205-1.251l1.18-2.044a1 1 0 011.186-.447l1.598.54A6.993 6.993 0 017.51 3.456l.33-1.652zM10 13a3 3 0 100-6 3 3 0 000 6z" clipRule="evenodd" />
        </svg>
      </button>

      {/* Modal */}
      {isOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
          onClick={close}
          role="dialog"
          aria-modal="true"
          aria-label="Settings"
        >
          <div
            className="mx-4 w-full max-w-sm rounded-xl border border-gray-200 bg-white p-6 shadow-2xl
                       dark:border-gray-700 dark:bg-gray-900 motion-safe:animate-fade-in"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="mb-5 flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-900 dark:text-white">Settings</h2>
              <button
                onClick={close}
                className="rounded-lg p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 cursor-pointer"
                aria-label="Close settings"
              >
                <svg className="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
                </svg>
              </button>
            </div>

            <div className="space-y-5">
              {/* Theme */}
              <div>
                <label className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                  Theme
                </label>
                <div className="flex gap-2">
                  {['light', 'dark', 'system'].map((t) => (
                    <button
                      key={t}
                      onClick={() => setMode(t)}
                      className={`flex-1 rounded-lg border px-3 py-2 text-xs font-medium capitalize transition-colors cursor-pointer
                        ${mode === t
                          ? 'border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                          : 'border-gray-200 text-gray-600 hover:border-gray-300 dark:border-gray-700 dark:text-gray-400 dark:hover:border-gray-600'
                        }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>

              {/* Font Size */}
              <div>
                <label className="mb-1.5 flex items-center justify-between text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                  Editor font size
                  <span className="font-mono text-gray-900 dark:text-white normal-case">{editorFontSize}px</span>
                </label>
                <input
                  type="range"
                  min={10}
                  max={20}
                  step={1}
                  value={editorFontSize}
                  onChange={(e) => setEditorFontSize(Number(e.target.value))}
                  className="w-full accent-blue-600"
                  aria-label="Editor font size"
                />
                <div className="mt-1 flex justify-between text-[10px] text-gray-400">
                  <span>10px</span><span>20px</span>
                </div>
              </div>

              {/* Word Wrap */}
              <div>
                <label className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                  Word wrap
                </label>
                <div className="flex gap-2">
                  {['on', 'off'].map((w) => (
                    <button
                      key={w}
                      onClick={() => setWordWrap(w)}
                      className={`flex-1 rounded-lg border px-3 py-2 text-xs font-medium capitalize transition-colors cursor-pointer
                        ${wordWrap === w
                          ? 'border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                          : 'border-gray-200 text-gray-600 hover:border-gray-300 dark:border-gray-700 dark:text-gray-400 dark:hover:border-gray-600'
                        }`}
                    >
                      {w === 'on' ? 'Enabled' : 'Disabled'}
                    </button>
                  ))}
                </div>
              </div>

              {/* Reset Layout */}
              <div className="border-t border-gray-100 pt-4 dark:border-gray-800">
                <button
                  onClick={handleResetLayout}
                  className="w-full rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600
                             hover:bg-gray-50 dark:border-gray-700 dark:text-gray-400 dark:hover:bg-gray-800 transition-colors cursor-pointer"
                >
                  Reset Split Ratio to Default
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
