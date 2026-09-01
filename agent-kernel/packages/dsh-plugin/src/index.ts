import type { Context } from '@deepseek-ai/cordis'
import z from '@deepseek-ai/schemastery'
import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'bizbuddy-tools'
export const inject = ['tools']

const DEFAULT_TOP_K = 5
const MAX_TOP_K = 20

export interface Config {
  ragBaseUrl: string
  collectorBaseUrl: string
  timeoutMs?: number
}

export const Config: z<Config> = z.object({
  ragBaseUrl: z.string().required(),
  collectorBaseUrl: z.string().required(),
  timeoutMs: z.number().default(15_000),
})

export interface Citation {
  citationId: string
  documentId: string
  documentName: string
  page?: number
  chunkId: string
  content: string
  score?: number
}

export interface TimeSeriesPoint {
  pointId: string
  name: string
  unit?: string
  description?: string
}

export interface TimeSeriesSample {
  timestamp: string
  value: number
}

function endpoint(baseUrl: string, path: string): URL {
  const normalized = baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`
  return new URL(path.replace(/^\//, ''), normalized)
}

async function fetchJson(url: URL, init: RequestInit, signal: AbortSignal): Promise<unknown> {
  const response = await fetch(url, { ...init, signal })
  const body = await response.text()
  if (!response.ok) {
    throw new Error(`upstream returned HTTP ${response.status}: ${body.slice(0, 300)}`)
  }
  if (body.length === 0) throw new Error('upstream returned an empty response body')
  try {
    return JSON.parse(body) as unknown
  } catch {
    throw new Error('upstream returned invalid JSON')
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function requiredString(value: unknown, field: string): string {
  if (typeof value !== 'string' || value.trim() === '') throw new Error(`invalid upstream field: ${field}`)
  return value
}

function optionalString(value: unknown, field: string): string | undefined {
  if (value === undefined) return undefined
  return requiredString(value, field)
}

function optionalNumber(value: unknown, field: string): number | undefined {
  if (value === undefined) return undefined
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new Error(`invalid upstream field: ${field}`)
  return value
}

function parseCitations(value: unknown): Citation[] {
  if (!isRecord(value) || !Array.isArray(value.hits)) throw new Error('invalid document search response: hits must be an array')
  return value.hits.map((raw, index) => {
    if (!isRecord(raw)) throw new Error(`invalid document search hit at index ${index}`)
    const page = optionalNumber(raw.page, `hits[${index}].page`)
    const score = optionalNumber(raw.score, `hits[${index}].score`)
    return {
      citationId: requiredString(raw.citationId, `hits[${index}].citationId`),
      documentId: requiredString(raw.documentId, `hits[${index}].documentId`),
      documentName: requiredString(raw.documentName, `hits[${index}].documentName`),
      chunkId: requiredString(raw.chunkId, `hits[${index}].chunkId`),
      content: requiredString(raw.content, `hits[${index}].content`),
      ...(page === undefined ? {} : { page }),
      ...(score === undefined ? {} : { score }),
    }
  })
}

function parsePoints(value: unknown): TimeSeriesPoint[] {
  if (!isRecord(value) || !Array.isArray(value.points)) throw new Error('invalid point list response: points must be an array')
  return value.points.map((raw, index) => {
    if (!isRecord(raw)) throw new Error(`invalid point at index ${index}`)
    const unit = optionalString(raw.unit, `points[${index}].unit`)
    const description = optionalString(raw.description, `points[${index}].description`)
    return {
      pointId: requiredString(raw.pointId, `points[${index}].pointId`),
      name: requiredString(raw.name, `points[${index}].name`),
      ...(unit === undefined ? {} : { unit }),
      ...(description === undefined ? {} : { description }),
    }
  })
}

function parseSeries(value: unknown, expectedPointId: string): { pointId: string; unit?: string; samples: TimeSeriesSample[] } {
  if (!isRecord(value) || !Array.isArray(value.samples)) throw new Error('invalid time-series response: samples must be an array')
  const pointId = requiredString(value.pointId, 'pointId')
  if (pointId !== expectedPointId) throw new Error(`time-series response pointId mismatch: expected ${expectedPointId}, got ${pointId}`)
  const unit = optionalString(value.unit, 'unit')
  const samples = value.samples.map((raw, index) => {
    if (!isRecord(raw)) throw new Error(`invalid sample at index ${index}`)
    const timestamp = requiredString(raw.timestamp, `samples[${index}].timestamp`)
    if (Number.isNaN(Date.parse(timestamp)) || !/[zZ]|[+-]\d{2}:\d{2}$/.test(timestamp)) {
      throw new Error(`invalid timestamp at samples[${index}]: an ISO 8601 timezone is required`)
    }
    const sample = optionalNumber(raw.value, `samples[${index}].value`)
    if (sample === undefined) throw new Error(`invalid upstream field: samples[${index}].value`)
    return { timestamp, value: sample }
  })
  return { pointId, ...(unit === undefined ? {} : { unit }), samples }
}

function assertTimeZone(value: string, field: string): void {
  if (Number.isNaN(Date.parse(value)) || !/[zZ]|[+-]\d{2}:\d{2}$/.test(value)) {
    throw new Error(`${field} must be an ISO 8601 timestamp with a timezone`)
  }
}

export function apply(ctx: Context, config: Config): void {
  const timeoutMs = config.timeoutMs ?? 15_000

  ctx.tools.register(defineTool({
    name: 'doc_search',
    description: 'Search approved enterprise documents. Use this before answering questions about policies, procedures, standards, or document facts.',
    parameters: {
      query: { type: 'string', required: true, description: 'A focused search query.' },
      topK: { type: 'integer', description: `Number of hits, default ${DEFAULT_TOP_K}, maximum ${MAX_TOP_K}.` },
    },
    timeoutMs,
    output: {
      schema: {
        type: 'object', additionalProperties: false, properties: {
          hits: {
            type: 'array', required: true, items: {
              type: 'object', additionalProperties: false, properties: {
                citationId: { type: 'string', required: true },
                documentId: { type: 'string', required: true },
                documentName: { type: 'string', required: true },
                page: { type: 'number' },
                chunkId: { type: 'string', required: true },
                content: { type: 'string', required: true },
                score: { type: 'number' },
              },
            },
          },
        },
      },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
      presentationMeta: (_args, value) => ({ kind: 'doc_search', citations: value.hits }),
    },
    async execute(args, exec) {
      const query = args.query.trim()
      if (query === '') throw new Error('query must not be empty')
      const topK = args.topK ?? DEFAULT_TOP_K
      if (topK < 1 || topK > MAX_TOP_K) throw new Error(`topK must be between 1 and ${MAX_TOP_K}`)
      const payload = await fetchJson(endpoint(config.ragBaseUrl, '/api/v1/documents/search'), {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ query, topK }),
      }, exec.signal)
      return { hits: parseCitations(payload) }
    },
  }))

  ctx.tools.register(defineTool({
    name: 'ts_list',
    description: 'List available DCS time-series points. Use this before querying a point unless its exact pointId is already present in tool results.',
    parameters: {
      keyword: { type: 'string', description: 'Optional point name or id keyword.' },
    },
    timeoutMs,
    output: {
      schema: {
        type: 'object', additionalProperties: false, properties: {
          points: {
            type: 'array', required: true, items: {
              type: 'object', additionalProperties: false, properties: {
                pointId: { type: 'string', required: true },
                name: { type: 'string', required: true },
                unit: { type: 'string' },
                description: { type: 'string' },
              },
            },
          },
        },
      },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
    },
    async execute(args, exec) {
      const url = endpoint(config.collectorBaseUrl, '/api/v1/timeseries/points')
      const keyword = args.keyword?.trim()
      if (keyword) url.searchParams.set('keyword', keyword)
      const payload = await fetchJson(url, { method: 'GET' }, exec.signal)
      return { points: parsePoints(payload) }
    },
  }))

  ctx.tools.register(defineTool({
    name: 'ts_query',
    description: 'Query one DCS point over an explicit timezone-aware time range. Never invent samples when the result is empty.',
    parameters: {
      pointId: { type: 'string', required: true, description: 'Exact point id returned by ts_list.' },
      startTime: { type: 'string', required: true, description: 'ISO 8601 timestamp with timezone.' },
      endTime: { type: 'string', required: true, description: 'ISO 8601 timestamp with timezone.' },
    },
    timeoutMs,
    output: {
      schema: {
        type: 'object', additionalProperties: false, properties: {
          pointId: { type: 'string', required: true },
          unit: { type: 'string' },
          samples: { type: 'array', required: true, items: { type: 'object', additionalProperties: false, properties: {
            timestamp: { type: 'string', required: true }, value: { type: 'number', required: true },
          } } },
        },
      },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
    },
    async execute(args, exec) {
      const pointId = args.pointId.trim()
      if (pointId === '') throw new Error('pointId must not be empty')
      assertTimeZone(args.startTime, 'startTime')
      assertTimeZone(args.endTime, 'endTime')
      if (Date.parse(args.startTime) >= Date.parse(args.endTime)) throw new Error('startTime must be earlier than endTime')
      const payload = await fetchJson(endpoint(config.collectorBaseUrl, '/api/v1/timeseries/query'), {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ pointId, startTime: args.startTime, endTime: args.endTime }),
      }, exec.signal)
      return parseSeries(payload, pointId)
    },
  }))
}
