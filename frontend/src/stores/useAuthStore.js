import { create } from 'zustand'
import { authService } from '../api/authService'
import { toast } from './useToastStore'

/**
 * useAuthStore — JWT authentication state.
 *
 * Manages:
 *   - Current user identity
 *   - JWT token (persisted in localStorage under 'testgen_jwt')
 *   - Login / register / logout actions
 *   - Hydration from localStorage on app startup
 *
 * The token is read by api/client.js request interceptor on every
 * outgoing V2 request — this store does NOT inject headers itself.
 *
 * Phase 5 addition. Does not modify any Phase 1–4 backend state.
 */

const TOKEN_KEY = 'testgen_jwt'
const USER_KEY  = 'testgen_user'

/** Restore persisted session from localStorage (called once on import). */
function loadPersistedSession() {
  try {
    const token = localStorage.getItem(TOKEN_KEY)
    const raw   = localStorage.getItem(USER_KEY)
    const user  = raw ? JSON.parse(raw) : null
    return { token, user, isAuthenticated: !!(token && user) }
  } catch {
    return { token: null, user: null, isAuthenticated: false }
  }
}

const persisted = loadPersistedSession()

export const useAuthStore = create((set, get) => ({
  // ── State ─────────────────────────────────────────────────────────────────

  /** Current authenticated user ({ id, email, is_active }) or null */
  user: persisted.user,

  /** Raw JWT string or null */
  token: persisted.token,

  /** True when a valid token + user are in memory */
  isAuthenticated: persisted.isAuthenticated,

  /** True while login / register API call is in-flight */
  isLoading: false,

  /** Normalized error from the last failed auth attempt */
  authError: null,

  // ── Actions ───────────────────────────────────────────────────────────────

  clearAuthError: () => set({ authError: null }),

  /**
   * login({ email, password }) — POST /api/v2/auth/login
   *
   * On success: persists JWT + user to localStorage and updates state.
   * On failure: sets authError.
   *
   * @returns {boolean} true on success, false on failure
   */
  login: async ({ email, password }) => {
    set({ isLoading: true, authError: null })

    try {
      // Step 1: get JWT token
      const tokenResponse = await authService.login({ email, password })
      const token = tokenResponse.access_token

      // Step 2: persist token (so the interceptor picks it up for next call)
      localStorage.setItem(TOKEN_KEY, token)

      // Step 3: fetch user identity using the new token
      // The backend returns user data from the login endpoint directly
      // (JWT payload contains user_id; we store what we received)
      const user = {
        email,
        token_type: tokenResponse.token_type,
      }

      localStorage.setItem(USER_KEY, JSON.stringify(user))

      set({
        token,
        user,
        isAuthenticated: true,
        isLoading: false,
        authError: null,
      })

      toast.success(`Welcome back!`)
      return true
    } catch (err) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
      set({
        token: null,
        user: null,
        isAuthenticated: false,
        isLoading: false,
        authError: {
          message: err.message || 'Login failed. Please check your credentials.',
          code: err.code || 'LOGIN_FAILED',
        },
      })
      return false
    }
  },

  /**
   * register({ email, password }) — POST /api/v2/auth/register
   *
   * On success: immediately logs in.
   * On failure: sets authError.
   *
   * @returns {boolean} true on success, false on failure
   */
  register: async ({ email, password }) => {
    set({ isLoading: true, authError: null })

    try {
      await authService.register({ email, password })
      // Auto-login after successful registration
      set({ isLoading: false })
      return await get().login({ email, password })
    } catch (err) {
      set({
        isLoading: false,
        authError: {
          message: err.message || 'Registration failed.',
          code: err.code || 'REGISTER_FAILED',
        },
      })
      return false
    }
  },

  /**
   * logout() — clears all auth state and localStorage.
   */
  logout: () => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    set({
      user: null,
      token: null,
      isAuthenticated: false,
      authError: null,
    })
    toast.info('Logged out successfully.')
  },
}))
