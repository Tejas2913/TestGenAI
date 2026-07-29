/**
 * useToastStore — queued toast notification system.
 *
 * Supports: success, error, warning, info
 * Auto-dismiss (4s), manual dismiss, queue.
 */
import { create } from 'zustand'

let _nextId = 1

export const useToastStore = create((set, get) => ({
  toasts: [],

  /**
   * addToast({ message, type, duration })
   * type: 'success' | 'error' | 'warning' | 'info'
   */
  addToast: ({ message, type = 'info', duration = 4000 }) => {
    const id = _nextId++
    set((s) => ({ toasts: [...s.toasts, { id, message, type, duration }] }))

    if (duration > 0) {
      setTimeout(() => get().removeToast(id), duration)
    }
    return id
  },

  removeToast: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),

  clearAll: () => set({ toasts: [] }),
}))

// Convenience helpers (call outside React)
export const toast = {
  success: (message, opts) =>
    useToastStore.getState().addToast({ message, type: 'success', ...opts }),
  error: (message, opts) =>
    useToastStore.getState().addToast({ message, type: 'error', duration: 6000, ...opts }),
  warning: (message, opts) =>
    useToastStore.getState().addToast({ message, type: 'warning', ...opts }),
  info: (message, opts) =>
    useToastStore.getState().addToast({ message, type: 'info', ...opts }),
}
