import type { Context } from '@deepseek-ai/cordis'
import {
  CallId,
  LlmAdapter,
  type GenerateOptions,
  type LlmResolvedModelInfo,
  type StreamChunk,
} from '@deepseek-ai/dsh-llm'

export const name = 'bizbuddy-mock-model'
export const inject = ['llm']

function textOf(options: GenerateOptions): string {
  return options.messages.flatMap(message => message.content)
    .filter(block => block.type === 'text')
    .map(block => block.text)
    .join('\n')
}

function toolResults(options: GenerateOptions): string[] {
  return options.messages.flatMap(message => message.content)
    .filter(block => block.type === 'tool-result')
    .flatMap(block => block.content)
    .filter(block => block.type === 'text')
    .map(block => block.text)
}

function toolCall(id: string, toolName: string, args: Record<string, unknown>): StreamChunk[] {
  const callId = CallId(id)
  const raw = JSON.stringify(args)
  return [
    { type: 'block-start', index: 0, blockType: 'tool-call' },
    { type: 'tool-call-delta', index: 0, id: callId, name: toolName, argumentsDelta: raw },
    { type: 'block-end', index: 0, block: { type: 'tool-call', id: callId, name: toolName, arguments: raw } },
    { type: 'finish', reason: { kind: 'tool-calls' } },
  ]
}

class BizBuddyMockAdapter extends LlmAdapter {
  override resolveModel(provider: string, model: string): Promise<LlmResolvedModelInfo> {
    return Promise.resolve({ provider, id: model, name: model })
  }

  async * stream(options: GenerateOptions): AsyncIterable<StreamChunk> {
    const prompt = textOf(options)
    const results = toolResults(options)
    const isDocumentQuestion = /制度|规范|作业|要求|流程/i.test(prompt)
    const isMeasurementQuestion = /温度|压力|液位|流量/i.test(prompt)
    if (isMeasurementQuestion || (!isDocumentQuestion && /点位|DCS|设备/i.test(prompt))) {
      if (results.length === 0) {
        yield * toolCall('mock-ts-list', 'ts_list', { keyword: '反应釜温度' })
        return
      }
      if (results.length === 1) {
        yield * toolCall('mock-ts-query', 'ts_query', {
          pointId: 'reactor_temperature',
          startTime: '2026-08-25T00:00:00+08:00',
          endTime: '2026-08-26T00:00:00+08:00',
        })
        return
      }
      yield * this.text('反应釜温度数据已经查询完成，结论仅依据工具返回的采样值。')
      return
    }

    if (results.length === 0) {
      yield * toolCall('mock-doc-search', 'doc_search', { query: prompt, topK: 5 })
      return
    }
    const match = results.join('\n').match(/"citationId":"([^"]+)"/)
    const citation = match?.[1] ?? 'missing-citation'
    yield * this.text(`根据企业制度，危险化学品应存放在专用区域。[${citation}]`)
  }

  private async * text(text: string): AsyncIterable<StreamChunk> {
    yield { type: 'block-start', index: 0, blockType: 'text' }
    yield { type: 'text-delta', index: 0, text }
    yield { type: 'block-end', index: 0, block: { type: 'text', text } }
    yield { type: 'finish', reason: { kind: 'stop' } }
  }
}

export function apply(ctx: Context): void {
  ctx.llm.registerAdapter(['bizbuddy-mock'], new BizBuddyMockAdapter())
}
