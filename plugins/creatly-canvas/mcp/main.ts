import process from 'node:process'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { createBridgeRpc } from './bridge'
import { createCanvasMcp } from './server'

createCanvasMcp(createBridgeRpc()).connect(new StdioServerTransport()).catch(() => {
  process.stderr.write('Canvas MCP failed to start. Check Node.js >=22 and local bridge configuration.\n')
  process.exitCode = 1
})
