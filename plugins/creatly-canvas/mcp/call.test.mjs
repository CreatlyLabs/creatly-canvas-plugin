import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

async function fixture(options, run) {
  const home = await mkdtemp(join(tmpdir(), 'canvas-plugin-test-'))
  await mkdir(join(home, '.codex/yuanji-canvas'), { recursive: true })
  await writeFile(join(home, '.codex/yuanji-canvas/bridge.token'), 'test-only-secret')
  const calls = []
  const server = createServer(async (req, res) => {
    let body = ''
    for await (const chunk of req) body += chunk
    assert.equal(req.headers['x-canvas-bridge-token'], 'test-only-secret')
    const message = JSON.parse(body); calls.push(message)
    let result
    if (message.action === 'status') result = { backend: 'http://127.0.0.1:8808', clients: options.pages || [{ clientId: 'one', authenticated: true, path: '/workbench/123' }] }
    else if (message.action === 'tools') result = { response: JSON.stringify({ success: true, data: options.invalidCatalog ? {} : [{ name: 'getCanvasContext', description: 'read', inputSchema: { type: 'object' } }, { name: 'updateNode', description: 'write', inputSchema: { type: 'object' } }] }) }
    else if (message.action === 'call') result = { response: JSON.stringify(options.writeError ? { success: false, message: 'write rejected' } : { success: true, result: message.payload }) }
    else throw new Error('Unexpected action: ' + message.action)
    res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify(result))
  })
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  const invoke = (tool, args = '{}') => new Promise(resolve => {
    const child = spawn(process.execPath, [fileURLToPath(new URL('./canvas-call.cjs', import.meta.url)), tool, args], { env: { ...process.env, HOME: home, YUANJI_CANVAS_URL: `http://127.0.0.1:${server.address().port}` } })
    let stdout = '', stderr = ''
    child.stdout.on('data', x => stdout += x); child.stderr.on('data', x => stderr += x)
    child.on('close', code => resolve({ code, stdout, stderr }))
  })
  try { await run(invoke, calls) }
  finally { await new Promise(resolve => server.close(resolve)); await rm(home, { recursive: true, force: true }) }
}

test('discovers deployed tools before calling and preserves long IDs', () => fixture({}, async (invoke, calls) => {
  const r = await invoke('getCanvasContext', '{"projectId":"123","baseVersion":"9007199254740993","payload":{"nodeId":5476940096849904473}}')
  assert.equal(r.code, 0, r.stderr)
  const call = calls.find(x => x.action === 'call')
  assert.ok(calls.findIndex(x => x.action === 'tools') < calls.findIndex(x => x.action === 'call'))
  assert.equal(call.payload.payload.nodeId, '5476940096849904473')
  assert.equal(call.payload.baseVersion, '9007199254740993')
  assert.equal(call.clientId, 'one')
}))
test('requires an explicit page with multiple authenticated tabs', () => fixture({ pages: [{ clientId: 'one', authenticated: true }, { clientId: 'two', authenticated: true }] }, async (invoke, calls) => {
  const r = await invoke('getCanvasContext')
  assert.notEqual(r.code, 0); assert.match(r.stderr, /clientId/)
  assert.equal(calls.filter(x => x.action === 'call').length, 0)
}))
test('invalid discovery cannot proceed to a write', () => fixture({ invalidCatalog: true }, async (invoke, calls) => {
  const r = await invoke('updateNode')
  assert.notEqual(r.code, 0)
  assert.equal(calls.filter(x => x.action === 'call').length, 0)
}))
test('a rejected write is reported once without retry', () => fixture({ writeError: true }, async (invoke, calls) => {
  const r = await invoke('updateNode', '{"clientId":"one","projectId":"123","payload":{"nodes":[]}}')
  assert.notEqual(r.code, 0)
  assert.equal(calls.filter(x => x.action === 'call').length, 1)
}))
