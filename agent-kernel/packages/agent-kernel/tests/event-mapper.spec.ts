import { describe, expect, it } from 'vitest'
import { mapSessionEvent } from '../src/event-mapper.js'

describe('mapSessionEvent', () => {
  it('maps text deltas and business tool calls', () => {
    let seq = 0
    const nextSeq = () => ++seq
    expect(mapSessionEvent('r1', 's1', {
      type: 'assistant/chunk', data: { chunk: { type: 'text-delta', text: '你好' } },
    }, nextSeq)).toEqual([{ type: 'text_delta', requestId: 'r1', sessionId: 's1', seq: 1, text: '你好' }])
    expect(mapSessionEvent('r1', 's1', {
      type: 'tool/call', data: { callId: 'c1', name: 'doc_search', arguments: '{}' },
    }, nextSeq)).toEqual([{
      type: 'searching', requestId: 'r1', sessionId: 's1', seq: 2,
      callId: 'c1', tool: 'doc_search', message: '正在检索相关制度',
    }])
  })

  it('maps durable citation metadata', () => {
    expect(mapSessionEvent('r1', 's1', {
      type: 'tool/result',
      data: { meta: { kind: 'doc_search', citations: [{
        citationId: 'doc-1:chunk-1', documentId: 'doc-1', documentName: '制度.pdf',
        page: 2, chunkId: 'chunk-1', content: '正文', score: 0.9,
      }] } },
    }, () => 1)).toEqual([{ type: 'citation', requestId: 'r1', sessionId: 's1', seq: 1, citations: [{
      citationId: 'doc-1:chunk-1', documentId: 'doc-1', documentName: '制度.pdf',
      page: 2, chunkId: 'chunk-1', content: '正文', score: 0.9,
    }] }])
  })

  it('maps terminal reasons', () => {
    expect(mapSessionEvent('r1', 's1', {
      type: 'turn/end', data: { reason: { kind: 'completed' } },
    }, () => 1)).toEqual([{ type: 'done', requestId: 'r1', sessionId: 's1', seq: 1, reason: 'completed' }])
    expect(mapSessionEvent('r1', 's1', {
      type: 'turn/end', data: { reason: { kind: 'max-tokens' } },
    }, () => 1)).toEqual([{ type: 'done', requestId: 'r1', sessionId: 's1', seq: 1, reason: 'max_tokens' }])
  })
})
