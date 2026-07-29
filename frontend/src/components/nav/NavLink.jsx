import { NavLink as RouterNavLink } from 'react-router-dom'

/**
 * NavLink — styled navigation link with active state.
 */
export default function NavLink({ to, children }) {
  return (
    <RouterNavLink
      to={to}
      className={({ isActive }) =>
        `px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
          isActive
            ? 'bg-gray-100 text-gray-900 dark:bg-gray-800 dark:text-white'
            : 'text-gray-500 hover:text-gray-900 hover:bg-gray-50 dark:text-gray-400 dark:hover:text-white dark:hover:bg-gray-800/50'
        }`
      }
    >
      {children}
    </RouterNavLink>
  )
}
