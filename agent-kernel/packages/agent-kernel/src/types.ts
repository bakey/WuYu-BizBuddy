export interface Citation {
  citationId: string
  documentId: string
  documentName: string
  page?: number
  chunkId: string
  content: string
  score?: number
}

export type BusinessToolName = 'doc_search' | 'ts_list' | 'ts_query'

export interface BizBuddyEventBase {
  requestId: string
  sessionId: string
  seq: number
}

export type BizBuddyEvent =
  | (BizBuddyEventBase & { type: 'searching'; callId: string; tool: BusinessToolName; message: string })
  | (BizBuddyEventBase & { type: 'text_delta'; text: string })
  | (BizBuddyEventBase & { type: 'citation'; citations: Citation[] })
  | (BizBuddyEventBase & { type: 'done'; reason: 'completed' | 'max_tokens' })
  | (BizBuddyEventBase & { type: 'error'; code: string; message: string; retryable: boolean })

export interface ModelLaunchConfig {
  baseUrl: string
  model: string
  apiKey: string
  maxTokens?: number
}

export interface KernelLaunchConfig {
  configPath: string
  workspaceDir: string
  dataDir: string
  skillsDir: string
  ragBaseUrl: string
  collectorBaseUrl: string
  model: ModelLaunchConfig
  mockModel?: boolean
  requestTimeoutMs?: number
}

export interface TraceSummary {
  sessionId: string
  createdAt: number
  eventCount: number
}

export interface TraceEvent {
  type: string
  seq: number
  time: number
  data: unknown
}

export interface AgentKernel {
  start(config: KernelLaunchConfig): Promise<void>
  prompt(sessionId: string, text: string, requestId?: string): AsyncIterable<BizBuddyEvent>
  listTraces(): Promise<TraceSummary[]>
  readTrace(sessionId: string, fromSeq?: number): Promise<TraceEvent[]>
  shutdown(): Promise<void>
}
