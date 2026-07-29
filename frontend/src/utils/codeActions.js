/**
 * copyToClipboard — copies text to clipboard with fallback.
 * @returns {Promise<boolean>} true if copy succeeded
 */
export async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    // Fallback for older browsers / non-HTTPS
    try {
      const textarea = document.createElement('textarea')
      textarea.value = text
      textarea.style.cssText = 'position:fixed;left:-9999px;top:-9999px'
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      return true
    } catch {
      return false
    }
  }
}

/**
 * downloadFile — triggers a file download in the browser.
 * @param {string} content  File contents
 * @param {string} filename Suggested filename
 * @param {string} [mimeType='text/x-python'] MIME type
 */
export function downloadFile(content, filename, mimeType = 'text/x-python') {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

/**
 * buildTestFilename — generates a pytest filename from function name.
 * @param {string|null} functionName
 * @returns {string}
 */
export function buildTestFilename(functionName) {
  if (!functionName) return 'test_generated.py'
  // Sanitize: lowercase, replace spaces/special chars with underscores
  const safe = functionName
    .toLowerCase()
    .replace(/[^a-z0-9_]/g, '_')
    .replace(/_{2,}/g, '_')
    .replace(/^_|_$/g, '')
  return `test_${safe}.py`
}

/**
 * formatDuration — human-readable duration from milliseconds.
 */
export function formatDuration(ms) {
  if (ms == null) return null
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

/**
 * formatTokens — formatted token count.
 */
export function formatTokens(count) {
  if (count == null) return null
  return count.toLocaleString()
}

/**
 * formatTimestamp — short datetime string.
 */
export function formatTimestamp(iso) {
  if (!iso) return null
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    })
  } catch {
    return null
  }
}
