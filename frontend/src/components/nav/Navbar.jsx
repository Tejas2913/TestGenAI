import { useState, useCallback } from 'react'
import NavLink from './NavLink'
import ThemeToggle from './ThemeToggle'
import StatusIndicator from './StatusIndicator'
import ShortcutsDialog from './ShortcutsDialog'
import SettingsDialog from './SettingsDialog'
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts'
import { useAuthStore } from '../../stores/useAuthStore'

/**
 * Navbar — top navigation bar with logo, nav links, status, and controls.
 * Phase 5: adds user display and logout button.
 */
export default function Navbar() {
  const [helpOpen, setHelpOpen] = useState(false)

  const handleOpenHelp  = useCallback(() => setHelpOpen(true), [])
  const handleCloseHelp = useCallback(() => setHelpOpen(false), [])

  const user   = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)

  // Wire ? global shortcut to open help
  useKeyboardShortcuts({ onOpenHelp: handleOpenHelp })

  return (
    <header className="sticky top-0 z-40 border-b border-gray-200 bg-white/80 backdrop-blur-md dark:border-gray-800 dark:bg-gray-950/80">
      <div className="flex h-14 items-center justify-between px-4 lg:px-6">
        {/* Left: Logo + Nav */}
        <div className="flex items-center gap-6">
          {/* Logo */}
          <a href="/" className="flex items-center gap-2" aria-label="TestGen AI Home">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 dark:bg-blue-500">
              <svg className="h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                <path
                  fillRule="evenodd"
                  d="M4.5 2A1.5 1.5 0 003 3.5v13A1.5 1.5 0 004.5 18h11a1.5 1.5 0 001.5-1.5V7.621a1.5 1.5 0 00-.44-1.06l-4.12-4.122A1.5 1.5 0 0011.378 2H4.5zm4.75 9.5a.75.75 0 000 1.5h2.5a.75.75 0 000-1.5h-2.5zm-2.5-3a.75.75 0 000 1.5h5a.75.75 0 000-1.5h-5z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <span className="text-lg font-bold text-gray-900 dark:text-white">
              TestGen <span className="text-blue-600 dark:text-blue-400">AI</span>
            </span>
          </a>

          {/* Nav links */}
          <nav className="hidden items-center gap-1 sm:flex" aria-label="Main navigation">
            <NavLink to="/">Dashboard</NavLink>
            <NavLink to="/history">History</NavLink>
          </nav>
        </div>

        {/* Right: Status + Controls + User */}
        <div className="flex items-center gap-2">
          <StatusIndicator />
          <div className="h-5 w-px bg-gray-200 dark:bg-gray-700 hidden md:block" aria-hidden="true" />
          <ThemeToggle />
          <SettingsDialog />
          <ShortcutsDialog externalOpen={helpOpen} onExternalClose={handleCloseHelp} />

          {/* User / Logout — Phase 5 */}
          {user && (
            <>
              <div className="h-5 w-px bg-gray-200 dark:bg-gray-700" aria-hidden="true" />
              <div className="flex items-center gap-2">
                <span className="hidden max-w-[120px] truncate text-xs text-gray-500 dark:text-gray-400 sm:block">
                  {user.email}
                </span>
                <button
                  onClick={logout}
                  title="Sign out"
                  aria-label="Sign out"
                  className="
                    flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs
                    text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-800
                    dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200
                    cursor-pointer
                  "
                >
                  <svg className="h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M3 4.25A2.25 2.25 0 015.25 2h5.5A2.25 2.25 0 0113 4.25v2a.75.75 0 01-1.5 0v-2a.75.75 0 00-.75-.75h-5.5a.75.75 0 00-.75.75v11.5c0 .414.336.75.75.75h5.5a.75.75 0 00.75-.75v-2a.75.75 0 011.5 0v2A2.25 2.25 0 0110.75 18h-5.5A2.25 2.25 0 013 15.75V4.25z" clipRule="evenodd" />
                    <path fillRule="evenodd" d="M6 10a.75.75 0 01.75-.75h9.546l-1.048-.943a.75.75 0 111.004-1.114l2.5 2.25a.75.75 0 010 1.114l-2.5 2.25a.75.75 0 11-1.004-1.114l1.048-.943H6.75A.75.75 0 016 10z" clipRule="evenodd" />
                  </svg>
                  <span className="hidden sm:block">Sign out</span>
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
