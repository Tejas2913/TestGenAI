/**
 * LoginPage — full-page authentication screen.
 *
 * Features:
 *   • Toggle between Login and Register modes
 *   • JWT-based auth via useAuthStore
 *   • Inline error messages (RFC7807-aware via normalized errors)
 *   • Loading state on the submit button
 *   • Accessible form (labels, aria-describedby)
 *   • Premium dark-capable design matching the app theme
 *
 * Phase 5. Does not modify any backend state.
 */
import { useState, useCallback } from 'react'
import { useAuthStore } from "../stores/useAuthStore";

function InputField({ id, label, type, value, onChange, disabled, autoComplete, hint }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label
        htmlFor={id}
        className="text-sm font-medium text-gray-700 dark:text-gray-300"
      >
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={onChange}
        disabled={disabled}
        autoComplete={autoComplete}
        aria-describedby={hint ? `${id}-hint` : undefined}
        className="
          w-full rounded-xl border border-gray-200 bg-white px-4 py-2.5
          text-sm text-gray-900 placeholder-gray-400
          transition-all outline-none
          focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20
          disabled:cursor-not-allowed disabled:opacity-50
          dark:border-gray-700 dark:bg-gray-800 dark:text-white
          dark:placeholder-gray-500 dark:focus:border-blue-400
        "
      />
      {hint && (
        <p id={`${id}-hint`} className="text-xs text-gray-400 dark:text-gray-500">
          {hint}
        </p>
      )}
    </div>
  )
}

function SubmitButton({ isLoading, label }) {
  return (
    <button
      type="submit"
      disabled={isLoading}
      className="
        w-full rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold
        text-white shadow-sm transition-all
        hover:bg-blue-500 active:scale-[0.98]
        disabled:cursor-not-allowed disabled:opacity-60
        focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2
        focus-visible:outline-blue-600 cursor-pointer
      "
    >
      {isLoading ? (
        <span className="flex items-center justify-center gap-2">
          <svg
            className="h-4 w-4 animate-spin"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          {label}...
        </span>
      ) : label}
    </button>
  )
}

export default function LoginPage() {
  const [mode, setMode] = useState('login')   // 'login' | 'register'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const login        = useAuthStore((s) => s.login)
  const register     = useAuthStore((s) => s.register)
  const isLoading    = useAuthStore((s) => s.isLoading)
  const authError    = useAuthStore((s) => s.authError)
  const clearAuthError = useAuthStore((s) => s.clearAuthError)

  const switchMode = useCallback((next) => {
    setMode(next)
    clearAuthError()
    setPassword('')
    setConfirmPassword('')
  }, [clearAuthError])

  const handleSubmit = useCallback(async (e) => {
    e.preventDefault()

    if (mode === 'register' && password !== confirmPassword) {
      return // Prevent submission with mismatched passwords
    }

    if (mode === 'login') {
      await login({ email, password })
    } else {
      await register({ email, password })
    }
  }, [mode, email, password, confirmPassword, login, register])

  const passwordMismatch =
    mode === 'register' && confirmPassword && password !== confirmPassword

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-br from-gray-50 via-blue-50/30 to-indigo-50/40 px-4 dark:from-gray-950 dark:via-gray-900 dark:to-gray-950">
      {/* Card */}
      <div className="w-full max-w-sm">
        {/* Logo / Header */}
        <div className="mb-8 text-center">
          <div className="mb-4 inline-flex rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 p-3 shadow-lg shadow-blue-500/30">
            <svg
              className="h-8 w-8 text-white"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M5 14.5l-1.402 1.402c-1.232 1.232-.65 3.318 1.067 3.611A48.309 48.309 0 0012 21c2.773 0 5.491-.235 8.135-.687 1.718-.293 2.3-2.379 1.067-3.61L19.8 15.3M5 14.5l7.5-7.5 7.5 7.5"
              />
            </svg>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white">
            TestGen AI
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            AI-powered test generation
          </p>
        </div>

        {/* Form card */}
        <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          {/* Mode toggle */}
          <div className="mb-6 flex rounded-lg border border-gray-200 p-0.5 dark:border-gray-700">
            {['login', 'register'].map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => switchMode(m)}
                className={`
                  flex-1 rounded-md py-1.5 text-sm font-medium transition-all cursor-pointer
                  ${mode === m
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
                  }
                `}
              >
                {m === 'login' ? 'Sign In' : 'Register'}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
            <InputField
              id="email"
              label="Email address"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isLoading}
              autoComplete="email"
            />

            <InputField
              id="password"
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isLoading}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            />

            {mode === 'register' && (
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="confirm-password"
                  className="text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Confirm password
                </label>
                <input
                  id="confirm-password"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  disabled={isLoading}
                  autoComplete="new-password"
                  className={`
                    w-full rounded-xl border px-4 py-2.5 text-sm
                    text-gray-900 placeholder-gray-400 outline-none
                    transition-all focus:ring-2 focus:ring-blue-500/20
                    disabled:cursor-not-allowed disabled:opacity-50
                    dark:bg-gray-800 dark:text-white dark:placeholder-gray-500
                    ${passwordMismatch
                      ? 'border-red-400 focus:border-red-400 dark:border-red-500'
                      : 'border-gray-200 focus:border-blue-500 dark:border-gray-700 dark:focus:border-blue-400'
                    }
                  `}
                />
                {passwordMismatch && (
                  <p className="text-xs text-red-500 dark:text-red-400">Passwords do not match.</p>
                )}
              </div>
            )}

            {/* Auth error */}
            {authError && (
              <div
                role="alert"
                className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 dark:border-red-800/50 dark:bg-red-900/20"
              >
                <svg className="mt-0.5 h-4 w-4 shrink-0 text-red-500" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                </svg>
                <p className="text-xs text-red-700 dark:text-red-300">{authError.message}</p>
              </div>
            )}

            <SubmitButton
              isLoading={isLoading}
              label={mode === 'login' ? 'Sign In' : 'Create Account'}
            />
          </form>

          {mode === 'login' && (
            <p className="mt-4 text-center text-xs text-gray-400 dark:text-gray-500">
              Don't have an account?{' '}
              <button
                type="button"
                onClick={() => switchMode('register')}
                className="font-medium text-blue-600 hover:underline dark:text-blue-400 cursor-pointer"
              >
                Register
              </button>
            </p>
          )}
        </div>

        <p className="mt-6 text-center text-xs text-gray-400 dark:text-gray-600">
          TestGen AI V2.1 — Async Generation Engine
        </p>
      </div>
    </div>
  )
}
