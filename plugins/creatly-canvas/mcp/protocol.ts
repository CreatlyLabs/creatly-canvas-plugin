export function assertExactNumbers(value: unknown): void {
  if (typeof value === 'number' && Number.isInteger(value) && !Number.isSafeInteger(value))
    throw new Error('Unsafe integer input: send long IDs and versions as strings')
  if (value && typeof value === 'object') {
    for (const item of Object.values(value))
      assertExactNumbers(item)
  }
}

export function parseExactJson(text: string): unknown {
  return JSON.parse(text, (_key: string, value: unknown, context?: { source?: string }) => {
    if (typeof value === 'number' && Number.isInteger(value) && !Number.isSafeInteger(value)) {
      if (!context?.source)
        throw new Error('Node.js 22+ with JSON parse source support is required')
      return context.source
    }
    return value
  })
}

export function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    throw new Error('Expected an object response')
  return value as Record<string, unknown>
}

export function unwrap(text: string): unknown {
  const result = object(parseExactJson(text))
  if (result.success === false)
    throw new Error(String(result.errorMsg || result.message || result.errorCode || 'Canvas API failed'))
  return result.data ?? result
}
