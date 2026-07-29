import { lazy, Suspense } from 'react'
import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom'
import AppLayout from './layouts/AppLayout'
import Spinner from './components/common/Spinner'
import { useAuthStore } from './stores/useAuthStore'

/* Route-level code splitting */
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const HistoryPage = lazy(() => import('./pages/HistoryPage'))
const LoginPage = lazy(() => import('./pages/LoginPage'))
const JobDetails = lazy(() => import('./pages/JobDetails'))

/** Suspense fallback — centered spinner */
function PageLoader() {
  return (
    <div className="flex h-screen items-center justify-center bg-gray-50 dark:bg-gray-950">
      <Spinner size="lg" />
    </div>
  )
}

/**
 * ProtectedRoute — redirects to /login when the user is not authenticated.
 */
function ProtectedRoute({ children }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  return children
}

/**
 * PublicRoute — redirects to / when the user is already authenticated.
 * Prevents authenticated users from seeing the login page.
 */
function PublicRoute({ children }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }
  return children
}

const router = createBrowserRouter([
  {
    path: '/login',
    element: (
      <PublicRoute>
        <Suspense fallback={<PageLoader />}>
          <LoginPage />
        </Suspense>
      </PublicRoute>
    ),
  },
  {
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        path: '/',
        element: (
          <Suspense fallback={<PageLoader />}>
            <DashboardPage />
          </Suspense>
        ),
      },
      {
        path: '/history',
        element: (
          <Suspense fallback={<PageLoader />}>
            <HistoryPage />
          </Suspense>
        ),
      },
      {
        path: '/jobs/:jobId',
        element: (
          <Suspense fallback={<PageLoader />}>
            <JobDetails />
          </Suspense>
        ),
      },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}