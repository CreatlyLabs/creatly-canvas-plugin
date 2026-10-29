import { dirname, resolve } from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js'

async function main() {
  const root = dirname(fileURLToPath(import.meta.url))
  const transport = new StdioClientTransport({ command: process.execPath, args: [resolve(root, 'canvas-mcp.cjs')], stderr: 'pipe', env: process.env.YUANJI_CANVAS_URL ? { YUANJI_CANVAS_URL: process.env.YUANJI_CANVAS_URL } : undefined })
  const client = new Client({ name: 'canvas-plugin-readiness', version: '1.0.0' })
  try {
    await client.connect(transport)
    const status = await client.callTool({ name: 'canvas_status' })
    if (status.isError)
      throw new Error(status.content[0]?.text || 'Bridge is unavailable')
    const pages = JSON.parse(status.content[0].text).clients?.filter(page => page.authenticated) ?? []
    process.stdout.write(`MCP initialized; authenticated canvas pages: ${pages.length}\n`)
    if (!pages.length)
      throw new Error('Open an authenticated local canvas page')
    for (const page of pages) {
      const discovered = await client.callTool({ name: 'canvas_describe_tools', arguments: { clientId: page.clientId } })
      if (discovered.isError)
        throw new Error(discovered.content[0]?.text || 'Discovery failed')
      const tools = await client.listTools()
      process.stdout.write(`Page ${page.clientId}: ${tools.tools.map(tool => tool.name).join(', ')}\n`)
    }
  }
  finally { await client.close() }
}
main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
