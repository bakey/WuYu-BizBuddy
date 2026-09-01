import { mkdir } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { join, resolve } from 'node:path'
import { randomUUID } from 'node:crypto'
import {
  HarnessClient,
  type HarnessNotification,
  type NotificationSubscription,
} from '@deepseek-ai/dsh-sdk-client'
import { mapSessionEvent } from './event-mapper.js'
import type {
  AgentKernel as AgentKernelContract,
  BizBuddyEvent,
  KernelLaunchConfig,
  TraceEvent,
  TraceSummary,
} from './types.js'

interface RuntimeClient {
  start(): void
  initialize(params: { cwd: string; provider: string; model: string; maxTokens?: number }): Promise<unknown>
  prompt(sessionId: string, contentBlocks: { type: 'text'; text: string }[]): Promise<string>
  subscribe(filter?: (notification: HarnessNotification) => boolean): NotificationSubscription
  request(method: string, params?: object): Promise<unknown>
  close(): Promise<void>
}

export interface AgentKernelDependencies {
  createClient?: (options: ConstructorParameters<typeof HarnessClient>[0]) => RuntimeClient
  runtimeBinPath?: string
}

function runtimeBinPath(): string {
  return createRequire(import.meta.url).resolve('@deepseek-ai/dsh-sdk-jsonrpc-demo/bin')
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function childEnvironment(config: KernelLaunchConfig): NodeJS.ProcessEnv {
  const inherited = [
    'PATH', 'Path', 'PATHEXT', 'SystemRoot', 'WINDIR', 'COMSPEC', 'TEMP', 'TMP',
    'USERPROFILE', 'HOME', 'APPDATA', 'LOCALAPPDATA', 'PROGRAMDATA', 'NODE_OPTIONS',
  ]
  const env: NodeJS.ProcessEnv = {}
  for (const key of inherited) {
    if (process.env[key] !== undefined) env[key] = process.env[key]
  }
  return {
    ...env,
    BIZBUDDY_MODEL_API_KEY: config.model.apiKey,
    BIZBUDDY_MODEL_BASE_URL: config.model.baseUrl,
    BIZBUDDY_MODEL_ID: config.model.model,
    BIZBUDDY_RAG_BASE_URL: config.ragBaseUrl,
    BIZBUDDY_COLLECTOR_BASE_URL: config.collectorBaseUrl,
    BIZBUDDY_SKILLS_DIR: resolve(config.skillsDir),
    BIZBUDDY_SESSION_DB: join(resolve(config.dataDir), 'sessions.sqlite'),
    BIZBUDDY_MOCK_MODEL: config.mockModel === true ? '1' : '0',
  }
}

export class BizBuddyAgentKernel implements AgentKernelContract {
  private client: RuntimeClient | undefined
  private config: KernelLaunchConfig | undefined
  private readonly activeSessions = new Set<string>()
  private readonly createClient: (options: ConstructorParameters<typeof HarnessClient>[0]) => RuntimeClient
  private readonly binPath: string

  constructor(dependencies: AgentKernelDependencies = {}) {
    this.createClient = dependencies.createClient ?? (options => new HarnessClient(options))
    this.binPath = dependencies.runtimeBinPath ?? runtimeBinPath()
  }

  async start(config: KernelLaunchConfig): Promise<void> {
    if (this.client !== undefined) throw new Error('AgentKernel is already started')
    if (config.mockModel !== true && config.model.apiKey.trim() === '') throw new Error('model apiKey is required')
    await mkdir(resolve(config.dataDir), { recursive: true })
    const client = this.createClient({
      command: process.execPath,
      args: [this.binPath, resolve(config.configPath)],
      cwd: resolve(config.workspaceDir),
      env: childEnvironment(config),
      ...(config.requestTimeoutMs === undefined ? {} : { requestTimeoutMs: config.requestTimeoutMs }),
    })
    this.client = client
    this.config = config
    try {
      client.start()
      await client.initialize({
        cwd: resolve(config.workspaceDir),
        provider: config.mockModel === true ? 'bizbuddy-mock' : 'bizbuddy-model',
        model: config.mockModel === true ? 'bizbuddy-mock-v1' : config.model.model,
        ...(config.model.maxTokens === undefined ? {} : { maxTokens: config.model.maxTokens }),
      })
    } catch (error) {
      await client.close().catch(() => undefined)
      this.client = undefined
      this.config = undefined
      throw this.redact(error)
    }
  }

  async * prompt(sessionId: string, text: string, requestId = randomUUID()): AsyncIterable<BizBuddyEvent> {
    const client = this.client
    if (client === undefined) throw new Error('AgentKernel is not started')
    if (sessionId.trim() === '') throw new Error('sessionId must not be empty')
    if (text.trim() === '') throw new Error('prompt text must not be empty')
    if (this.activeSessions.has(sessionId)) throw new Error(`session ${sessionId} already has an active prompt`)

    this.activeSessions.add(sessionId)
    const subscription = client.subscribe(notification => notification.params.sessionId === sessionId)
    let seq = 0
    try {
      await client.prompt(sessionId, [{ type: 'text', text }])
      for (;;) {
        const notification = await subscription.next()
        if (notification.method !== 'session.event') continue
        const event = notification.params.event
        const mapped = mapSessionEvent(requestId, sessionId, event, () => ++seq)
        for (const item of mapped) yield this.redactEvent(item)
        if (isRecord(event) && event.type === 'turn/end') return
      }
    } catch (error) {
      const failure = this.redact(error)
      yield { type: 'error', requestId, sessionId, seq: ++seq, code: 'KERNEL_EXITED', message: failure.message, retryable: true }
    } finally {
      subscription.close()
      this.activeSessions.delete(sessionId)
    }
  }

  async listTraces(): Promise<TraceSummary[]> {
    const result = await this.requestTrace('trace/list')
    if (!Array.isArray(result)) throw new Error('trace/list returned an invalid response')
    return result as TraceSummary[]
  }

  async readTrace(sessionId: string, fromSeq = 0): Promise<TraceEvent[]> {
    const result = await this.requestTrace('trace/read', { sessionId, fromSeq })
    if (!Array.isArray(result)) throw new Error('trace/read returned an invalid response')
    return result as TraceEvent[]
  }

  async shutdown(): Promise<void> {
    const client = this.client
    this.client = undefined
    this.config = undefined
    if (client !== undefined) await client.close()
  }

  private async requestTrace(method: string, params?: object): Promise<unknown> {
    const client = this.client
    if (client === undefined) throw new Error('AgentKernel is not started')
    try {
      return await client.request(method, params)
    } catch (error) {
      throw this.redact(error)
    }
  }

  private redactEvent(event: BizBuddyEvent): BizBuddyEvent {
    return event.type === 'error' ? { ...event, message: this.redact(new Error(event.message)).message } : event
  }

  private redact(value: unknown): Error {
    const original = value instanceof Error ? value.message : String(value)
    const apiKey = this.config?.model.apiKey
    const message = apiKey === undefined || apiKey === '' ? original : original.split(apiKey).join('[REDACTED]')
    return new Error(message)
  }
}
