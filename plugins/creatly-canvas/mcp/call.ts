import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import process from 'node:process'
import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { getDefaultEnvironment, StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js'
import { object, parseExactJson } from './protocol'

// Bundled alongside canvas-mcp.cjs; no frontend source tree or npm install required.
const client = new Client({ name: 'creatly-canvas-cli', version: '1.0.0' })
async function invoke(name: string, args: Record<string, unknown> = {}) {
  const result = await client.callTool({ name, arguments: args }, undefined, { timeout: 60000 })
  if (result.isError)
    throw new Error(result.content.filter(x => x.type === 'text').map(x => x.text).join('\n'))
  return result
}
async function main() {
  const name = process.argv[2] || 'canvas_status'
  const input = process.argv[3] === '-' ? readFileSync(0, 'utf8') : process.argv[3] || '{}'
  const args = object(parseExactJson(input))
  await client.connect(new StdioClientTransport({
    command: process.execPath,
    args: [resolve(__dirname, 'canvas-mcp.cjs')],
    stderr: 'inherit',
    env: { ...getDefaultEnvironment(), YUANJI_CANVAS_URL: process.env.YUANJI_CANVAS_URL || 'http://127.0.0.1:3000' },
  }))
  const helpers = new Set(['canvas_status', 'canvas_describe_tools', 'canvas_list_projects'])
  if (!helpers.has(name)) {
    const status = await invoke('canvas_status')
    const text = status.content.find(x => x.type === 'text')
    if (!text || text.type !== 'text') throw new Error('Missing canvas status')
    const state = object(parseExactJson(text.text))
    const pages = (Array.isArray(state.clients) ? state.clients : []).map(object)
      .filter(page => page.authenticated && (!args.clientId || page.clientId === args.clientId))
    if (pages.length !== 1) throw new Error('Select exactly one authenticated page using canvas_status and clientId')
    args.clientId = String(pages[0]!.clientId)
    await invoke('canvas_describe_tools', { clientId: args.clientId })
  }
  const result = await invoke(name, args)
  process.stdout.write(JSON.stringify(result, null, 2) + '\n')
}
main().catch(error => {
  process.stderr.write((error instanceof Error ? error.message : 'Canvas call failed') + '\n')
  process.exitCode = 1
}).finally(() => client.close())
