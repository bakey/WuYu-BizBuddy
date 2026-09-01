import { createServer, type Server } from 'node:http'
import { mkdtemp, stat } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { afterEach, describe, expect, it } from 'vitest'
import { BizBuddyAgentKernel } from '../src/agent-kernel.js'
import type { BizBuddyEvent } from '../src/types.js'

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = resolve(packageRoot, '../..')

function startMockServices(): Promise<{ baseUrl: string; close: () => Promise<void> }> {
  const server = createServer(async (request, response) => {
    const url = new URL(request.url ?? '/', 'http://127.0.0.1')
    if (request.method === 'POST' && url.pathname === '/api/v1/documents/search') {
      response.writeHead(200, { 'content-type': 'application/json' })
      response.end(JSON.stringify({
        hits: [{
          citationId: 'fire-work-001',
          documentId: 'doc-fire-work-001',
          documentName: '动火作业安全管理制度',
          page: 12,
          chunkId: 'chunk-1203',
          content: '动火作业前应办理动火作业票。',
          score: 0.92,
        }],
      }))
      return
    }
    if (request.method === 'GET' && url.pathname === '/api/v1/timeseries/points') {
      response.writeHead(200, { 'content-type': 'application/json' })
      response.end(JSON.stringify({
        points: [{
          pointId: 'reactor_temperature',
          name: '一号反应釜温度',
          unit: '℃',
          description: '一号反应釜内部温度',
        }],
      }))
      return
    }
    if (request.method === 'POST' && url.pathname === '/api/v1/timeseries/query') {
      response.writeHead(200, { 'content-type': 'application/json' })
      response.end(JSON.stringify({
        pointId: 'reactor_temperature',
        unit: '℃',
        samples: [
          { timestamp: '2026-08-25T10:00:00+08:00', value: 85.2 },
          { timestamp: '2026-08-25T11:00:00+08:00', value: 86.1 },
        ],
      }))
      return
    }
    response.writeHead(404, { 'content-type': 'application/json' })
    response.end(JSON.stringify({ message: 'not found' }))
  })
  return new Promise((resolveStart, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const address = server.address()
      if (address === null || typeof address === 'string') {
        reject(new Error('mock service did not bind to a TCP port'))
        return
      }
      resolveStart({
        baseUrl: `http://127.0.0.1:${address.port}`,
        close: () => closeServer(server),
      })
    })
  })
}

function closeServer(server: Server): Promise<void> {
  return new Promise((resolveClose, reject) => {
    server.close(error => error === undefined ? resolveClose() : reject(error))
  })
}

async function collect(stream: AsyncIterable<BizBuddyEvent>): Promise<BizBuddyEvent[]> {
  const events: BizBuddyEvent[] = []
  for await (const event of stream) events.push(event)
  return events
}

describe('BizBuddyAgentKernel integration', () => {
  const kernels: BizBuddyAgentKernel[] = []
  const services: Array<{ close: () => Promise<void> }> = []

  afterEach(async () => {
    await Promise.all(kernels.splice(0).map(kernel => kernel.shutdown()))
    await Promise.all(services.splice(0).map(service => service.close()))
  })

  it('streams a cited document answer through the DSH child process', async () => {
    const service = await startMockServices()
    services.push(service)
    const dataDir = await mkdtemp(resolve(tmpdir(), 'bizbuddy-kernel-'))
    const kernel = new BizBuddyAgentKernel()
    kernels.push(kernel)

    await kernel.start({
      configPath: resolve(workspaceRoot, 'cordis.yml'),
      workspaceDir: workspaceRoot,
      dataDir,
      skillsDir: resolve(workspaceRoot, 'skills'),
      ragBaseUrl: service.baseUrl,
      collectorBaseUrl: service.baseUrl,
      model: { baseUrl: 'http://unused.example', model: 'unused', apiKey: '' },
      mockModel: true,
      requestTimeoutMs: 20_000,
    })

    const events = await collect(kernel.prompt('session-doc-001', '动火作业有什么要求？', 'req-doc-001'))

    expect(events).toContainEqual(expect.objectContaining({
      type: 'searching', requestId: 'req-doc-001', sessionId: 'session-doc-001', callId: 'mock-doc-search', tool: 'doc_search',
    }))
    expect(events).toContainEqual(expect.objectContaining({
      type: 'citation', requestId: 'req-doc-001', sessionId: 'session-doc-001', citations: [expect.objectContaining({
        citationId: 'fire-work-001', documentId: 'doc-fire-work-001', page: 12,
      })],
    }))
    expect(events.some(event => event.type === 'text_delta' && event.text.includes('[fire-work-001]'))).toBe(true)
    expect(events).toContainEqual(expect.objectContaining({
      type: 'done', requestId: 'req-doc-001', sessionId: 'session-doc-001', reason: 'completed',
    }))
    expect(events.map(event => event.seq)).toEqual([...events.keys()].map(index => index + 1))
    await expect(stat(resolve(dataDir, 'sessions.sqlite'))).resolves.toBeDefined()
  }, 30_000)

  it('discovers a point and queries its time-series samples', async () => {
    const service = await startMockServices()
    services.push(service)
    const dataDir = await mkdtemp(resolve(tmpdir(), 'bizbuddy-kernel-'))
    const kernel = new BizBuddyAgentKernel()
    kernels.push(kernel)

    await kernel.start({
      configPath: resolve(workspaceRoot, 'cordis.yml'),
      workspaceDir: workspaceRoot,
      dataDir,
      skillsDir: resolve(workspaceRoot, 'skills'),
      ragBaseUrl: service.baseUrl,
      collectorBaseUrl: service.baseUrl,
      model: { baseUrl: 'http://unused.example', model: 'unused', apiKey: '' },
      mockModel: true,
      requestTimeoutMs: 20_000,
    })

    const events = await collect(kernel.prompt('session-dcs-001', '一号反应釜温度历史怎么样？', 'req-dcs-001'))

    expect(events).toContainEqual(expect.objectContaining({
      type: 'searching', requestId: 'req-dcs-001', tool: 'ts_list', callId: 'mock-ts-list',
    }))
    expect(events).toContainEqual(expect.objectContaining({
      type: 'searching', requestId: 'req-dcs-001', tool: 'ts_query', callId: 'mock-ts-query',
    }))
    expect(events.some(event => event.type === 'text_delta' && event.text.includes('工具返回的采样值'))).toBe(true)
    expect(events).toContainEqual(expect.objectContaining({ type: 'done', requestId: 'req-dcs-001', reason: 'completed' }))
  }, 30_000)
})
