import { randomUUID } from 'node:crypto'
import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js'
import { assertExactNumbers, object, unwrap } from './protocol'

export type BridgeRpc = (action: string, payload?: Record<string, unknown>, clientId?: string) => Promise<unknown>

const readOnly = new Set(['getCanvasContext', 'getConversationContext', 'listCanvasSubjects', 'listSystemVoices', 'calculateCredits', 'getTaskStatus', 'listActors', 'listSubjectTypes', 'getSubjectReferenceLayout', 'resolveElements', 'previewElementBinding'])
const clientProperty = { type: 'string', description: 'canvas_status 返回的页面 clientId；多页面时必须指定。' }
const idProperty = { type: 'string', description: 'ID 必须使用字符串以保留 Java Long 精度。' }

const imageModelPreference = '未指定生图模型时默认 Creatly Sigma 2.5 Sunburst 2K（model=gpt-image-2.5-sunburst、function=gpt25_sunburst、modelConfigId=image_gpt25_sunburst、resolution=2k）；用户明确指定的模型、分辨率、质量和数量优先。提交前核对当前模型配置，并将节点配置、费用估算和 requests 参数保持一致。模型不可用时说明原因，不自动换模型或重生成。'

export function createCanvasMcp(rpc: BridgeRpc) {
  const definitions = new Map<string, Record<string, unknown>>()
  let catalogClientId: string | undefined
  const server = new Server({ name: 'yuanji-canvas', version: '1.0.0' }, {
    capabilities: { tools: { listChanged: true } },
    instructions: `操作前先调用 canvas_status 确认 backend 和目标页面，再调用 canvas_describe_tools 获取真实后端 payload schema。本机桥接使用浏览器已登录账号，数据保存在显示的后端环境。ID 一律传字符串；修改前读取画布及版本，优先提供 baseVersion。生成可能收费，遵循用户授权和后端确认流程。超时后先读状态，禁止自动重试写操作。个人画布修改后可能需要手动刷新页面。${imageModelPreference}`,
  })

  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: [
      { name: 'canvas_status', description: '读取本地连接页面、当前路径及后端地址；无需登录即可诊断。', inputSchema: { type: 'object' as const, properties: {}, additionalProperties: false }, annotations: { readOnlyHint: true } },
      { name: 'canvas_describe_tools', description: '获取已部署后端的真实工具定义、payload 参数 schema 和确认要求；可指定 toolName。', inputSchema: { type: 'object' as const, properties: { clientId: clientProperty, toolName: { type: 'string' } }, additionalProperties: false }, annotations: { readOnlyHint: true } },
      { name: 'canvas_list_projects', description: '列出当前登录账号的项目。', inputSchema: { type: 'object' as const, properties: { clientId: clientProperty, page: { type: 'integer', minimum: 0 }, size: { type: 'integer', minimum: 1, maximum: 100 } }, additionalProperties: false }, annotations: { readOnlyHint: true } },
      ...Array.from(definitions).map(([name, definition]) => ({
        name,
        description: `${definition.description}。先 canvas_describe_tools(toolName="${name}") 查询 payload schema。${name === 'batchGenerateImage' ? imageModelPreference : ''}`,
        inputSchema: {
          type: 'object' as const,
          properties: {
            clientId: clientProperty,
            projectId: { type: 'string', description: '十进制 ID、加密 ID 或本地 workbench URL。省略时从目标页面推断。' },
            conversationId: idProperty,
            taskId: idProperty,
            messageId: idProperty,
            executionId: idProperty,
            baseVersion: idProperty,
            toolVersion: { type: 'string' },
            payload: definition.inputSchema ?? { type: 'object', additionalProperties: true },
          },
          additionalProperties: false,
        },
        annotations: { readOnlyHint: readOnly.has(name), destructiveHint: !readOnly.has(name), openWorldHint: true },
      })),
    ],
  }))

  async function remote(action: string, payload: Record<string, unknown>, clientId?: string) {
    const response = object(await rpc(action, payload, clientId))
    if (typeof response.response !== 'string')
      throw new Error('Bridge returned an invalid response')
    return unwrap(response.response)
  }

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    try {
      const { name, arguments: args = {} } = request.params
      assertExactNumbers(args)
      const clientId = typeof args.clientId === 'string' ? args.clientId : undefined
      let result: unknown
      if (name === 'canvas_status') {
        result = await rpc('status')
      }
      else if (name === 'canvas_describe_tools') {
        const status = object(await rpc('status'))
        const clients = (Array.isArray(status.clients) ? status.clients : []).map(object).filter(client => client.authenticated && (!clientId || client.clientId === clientId))
        if (clients.length !== 1)
          throw new Error('Select exactly one authenticated page using canvas_status and clientId')
        const selectedId = String(clients[0]!.clientId)
        const latest = await remote('tools', {}, selectedId)
        if (!Array.isArray(latest))
          throw new Error('Tool catalog must be an array')
        if (Array.isArray(latest)) {
          for (const value of latest) {
            const definition = object(value)
            if (typeof definition.name !== 'string' || !definition.name || !definition.inputSchema)
              throw new Error('Invalid tool definition from backend')
          }
          catalogClientId = selectedId
          definitions.clear()
          for (const value of latest) {
            const definition = object(value)
            if (typeof definition.name === 'string')
              definitions.set(definition.name, definition)
          }
          await server.sendToolListChanged()
        }
        result = args.toolName && Array.isArray(latest)
          ? latest.filter(value => object(value).name === args.toolName)
          : latest
      }
      else if (name === 'canvas_list_projects') {
        result = await remote('projects', { page: args.page ?? 0, size: args.size ?? 20 }, clientId)
      }
      else {
        if (!definitions.has(name))
          throw new Error(`Unknown tool: ${name}. Call canvas_describe_tools to load the deployed catalog.`)
        const status = object(await rpc('status'))
        const clients = (Array.isArray(status.clients) ? status.clients : []).map(object).filter(client => client.authenticated && (!clientId || client.clientId === clientId))
        if (clients.length !== 1)
          throw new Error('Select exactly one authenticated page using canvas_status and clientId')
        const selectedId = String(clients[0]!.clientId)
        if (catalogClientId !== selectedId)
          throw new Error('Page changed. Call canvas_describe_tools for this clientId before using its tools.')
        let projectId = args.projectId
        if (!projectId && name !== 'projectCreate' && typeof clients[0]!.path === 'string')
          projectId = clients[0]!.path.match(/^\/workbench\/([^/?#]+)$/)?.[1]
        if (typeof projectId === 'string') {
          if (projectId.startsWith('http')) {
            const url = new URL(projectId)
            projectId = url.pathname.match(/^\/workbench\/([^/]+)$/)?.[1]
            if (!projectId)
              throw new Error('Expected a workbench project URL')
          }
          if (!/^\d+$/.test(String(projectId)))
            projectId = String(await remote('decrypt', { id: projectId }, selectedId))
        }
        const body: Record<string, unknown> = { requestId: randomUUID(), toolName: name, payload: args.payload ?? {} }
        if (projectId)
          body.projectId = projectId
        for (const key of ['conversationId', 'taskId', 'messageId', 'executionId', 'baseVersion', 'toolVersion']) {
          if (args[key] !== undefined)
            body[key] = args[key]
        }
        result = await remote('call', body, selectedId)
        const response = object(result)
        if (response.success === false)
          return { isError: true, content: [{ type: 'text' as const, text: JSON.stringify(result) }] }
      }
      return { content: [{ type: 'text' as const, text: JSON.stringify(result) }] }
    }
    catch (error) {
      return { isError: true, content: [{ type: 'text' as const, text: error instanceof Error ? error.message : 'Canvas MCP request failed' }] }
    }
  })
  return server
}
