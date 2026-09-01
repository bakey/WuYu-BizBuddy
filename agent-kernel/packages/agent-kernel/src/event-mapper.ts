import type { BizBuddyEvent, BusinessToolName, Citation } from './types.js'

const BUSINESS_TOOLS = new Set<BusinessToolName>(['doc_search', 'ts_list', 'ts_query'])

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function asBusinessTool(value: unknown): BusinessToolName | undefined {
  return typeof value === 'string' && BUSINESS_TOOLS.has(value as BusinessToolName)
    ? value as BusinessToolName
    : undefined
}

function citation(value: unknown): Citation | undefined {
  if (!isRecord(value)
    || typeof value.citationId !== 'string'
    || typeof value.documentId !== 'string'
    || typeof value.documentName !== 'string'
    || typeof value.chunkId !== 'string'
    || typeof value.content !== 'string') return undefined
  if (value.page !== undefined && typeof value.page !== 'number') return undefined
  if (value.score !== undefined && typeof value.score !== 'number') return undefined
  return {
    citationId: value.citationId,
    documentId: value.documentId,
    documentName: value.documentName,
    chunkId: value.chunkId,
    content: value.content,
    ...(value.page === undefined ? {} : { page: value.page }),
    ...(value.score === undefined ? {} : { score: value.score }),
  }
}

function messageForTool(tool: BusinessToolName): string {
  if (tool === 'doc_search') return '正在检索相关制度'
  if (tool === 'ts_list') return '正在查找相关测点'
  return '正在查询历史数据'
}

function isRetryable(code: string): boolean {
  return !['MODEL_NOT_CONFIGURED', 'POINT_NOT_FOUND', 'NO_DATA', 'INVALID_TURN_END'].includes(code)
}

export function mapSessionEvent(
  requestId: string,
  sessionId: string,
  rawEvent: unknown,
  nextSeq: () => number,
): BizBuddyEvent[] {
  if (!isRecord(rawEvent) || typeof rawEvent.type !== 'string' || !isRecord(rawEvent.data)) return []
  const base = () => ({ requestId, sessionId, seq: nextSeq() })

  if (rawEvent.type === 'assistant/chunk') {
    const chunk = rawEvent.data.chunk
    if (isRecord(chunk) && chunk.type === 'text-delta' && typeof chunk.text === 'string' && chunk.text !== '') {
      return [{ ...base(), type: 'text_delta', text: chunk.text }]
    }
    return []
  }

  if (rawEvent.type === 'tool/call') {
    const tool = asBusinessTool(rawEvent.data.name)
    if (tool !== undefined && typeof rawEvent.data.callId === 'string') {
      return [{ ...base(), type: 'searching', callId: rawEvent.data.callId, tool, message: messageForTool(tool) }]
    }
    return []
  }

  if (rawEvent.type === 'tool/result') {
    if (isRecord(rawEvent.data.error)) {
      const code = typeof rawEvent.data.error.code === 'string' ? rawEvent.data.error.code : 'TOOL_ERROR'
      const message = typeof rawEvent.data.error.name === 'string' ? rawEvent.data.error.name : 'Tool execution failed'
      return [{ ...base(), type: 'error', code, message, retryable: isRetryable(code) }]
    }
    const meta = rawEvent.data.meta
    if (!isRecord(meta) || meta.kind !== 'doc_search' || !Array.isArray(meta.citations)) return []
    const citations = meta.citations.map(citation).filter((item): item is Citation => item !== undefined)
    return citations.length === 0 ? [] : [{ ...base(), type: 'citation', citations }]
  }

  if (rawEvent.type === 'turn/end') {
    const reason = rawEvent.data.reason
    if (!isRecord(reason) || typeof reason.kind !== 'string') {
      return [{ ...base(), type: 'error', code: 'INVALID_TURN_END', message: 'DSH returned an invalid turn result', retryable: false }]
    }
    if (reason.kind === 'completed') return [{ ...base(), type: 'done', reason: 'completed' }]
    if (reason.kind === 'max-tokens') return [{ ...base(), type: 'done', reason: 'max_tokens' }]
    if (reason.kind === 'error' && isRecord(reason.error)) {
      const code = typeof reason.error.code === 'string' ? reason.error.code : 'MODEL_ERROR'
      return [{
        ...base(),
        type: 'error',
        code,
        message: typeof reason.error.message === 'string' ? reason.error.message : 'Model request failed',
        retryable: isRetryable(code),
      }]
    }
    const code = `TURN_${reason.kind.toUpperCase()}`
    return [{ ...base(), type: 'error', code, message: `DSH turn ended with ${reason.kind}`, retryable: isRetryable(code) }]
  }

  return []
}
