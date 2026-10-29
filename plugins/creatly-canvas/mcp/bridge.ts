import { readFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'
import process from 'node:process'

export function createBridgeRpc() {
  const base = new URL(process.env.YUANJI_CANVAS_URL || 'http://127.0.0.1:3000')
  if (base.protocol !== 'http:' || !['127.0.0.1', 'localhost', '[::1]'].includes(base.hostname) || base.username || base.password)
    throw new Error('YUANJI_CANVAS_URL must be a local HTTP frontend URL')
  return async (action: string, payload: Record<string, unknown> = {}, clientId?: string) => {
    let secret: string
    try {
      secret = readFileSync(join(homedir(), '.codex', 'yuanji-canvas', 'bridge.token'), 'utf8').trim()
      if (!secret)
        throw new Error('empty')
    }
    catch {
      throw new Error('Start creatly-fe with pnpm dev:canvas and open an authenticated canvas page first.')
    }
    const response = await fetch(new URL('/__codex/bridge', base), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Canvas-Bridge-Token': secret },
      body: JSON.stringify({ action, payload, clientId }),
      signal: AbortSignal.timeout(50000),
      redirect: 'error',
    })
    if (!response.ok)
      throw new Error(`Local bridge HTTP ${response.status}. Check frontend/login and read state before retrying writes.`)
    return response.json()
  }
}
