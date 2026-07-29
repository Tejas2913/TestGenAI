import { Outlet } from 'react-router-dom'
import Navbar from '../components/nav/Navbar'
import ToastContainer from '../components/common/ToastContainer'

/**
 * AppLayout — root layout wrapping all pages.
 * Navbar + content area + footer + global ToastContainer.
 */
export default function AppLayout() {
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-white dark:bg-gray-950">
      <Navbar />

      {/* Page content — takes remaining height */}
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-gray-50 px-4 py-2 dark:border-gray-800 dark:bg-gray-900">
        <p className="text-center text-xs text-gray-400 dark:text-gray-500">
          TestGen AI v0.1.0
        </p>
      </footer>

      {/* Global toast notifications */}
      <ToastContainer />
    </div>
  )
}
