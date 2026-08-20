import { getJson, postJsonBody } from './client'

const basePath = '/api/v1/market-intelligence'

export type DiscoveryRun = {
  run_id: string
  status: 'queued' | 'running' | 'complete' | 'incomplete' | 'failed' | 'cancelled'
  current_stage: string
  error_code: string | null
}

export type ClaimType =
  | 'fact'
  | 'signal'
  | 'inference'
  | 'research_hypothesis'

export type CitedStatement = {
  text: string
  claim_type: ClaimType
  claim_ids: string[]
  premise_claim_ids: string[]
  evidence_ids: string[]
  source_ids: string[]
}

export type OpportunitySource = {
  source_snapshot_id: string
  title: string
  publisher: string
  url: string | null
  source_class: 'primary_evidence' | 'reporting' | 'discovery'
  document_type: string
  authority_tier: string
  published_at: string
}

export type DetectedSignal = {
  signal_id: string
  description: string
  topic: string
  claim_type: 'signal'
  claim_ids: string[]
  source_ids: string[]
  independent_source_count: number
  strength_score: number
}

export type AffectedArea = {
  name: string
  relationship: 'direct' | 'second_order' | 'third_order'
  direction: 'positive' | 'negative' | 'mixed' | 'unknown'
  rationale: CitedStatement
}

export type InvestmentLens = {
  orientation: 'long_term_accumulation'
  research_posture:
    | 'research_now'
    | 'watch_for_confirmation'
    | 'insufficient_evidence'
  long_term_relevance: CitedStatement
  posture_rationale: CitedStatement
  what_to_watch: CitedStatement[]
  capital_deployment_assessment: 'insufficient_data'
  capital_deployment_limitations: string[]
}

export type ResearchOpportunity = {
  opportunity_id: string
  run_id: string
  status: 'complete' | 'incomplete'
  document: {
    theme: { name: string; description: string; signal_ids: string[] }
    summary: CitedStatement
    why_now: CitedStatement
    detected_signals: DetectedSignal[]
    affected_industries: AffectedArea[]
    affected_companies: AffectedArea[]
    research_thesis: CitedStatement
    mechanism: CitedStatement
    bull_case: CitedStatement[]
    bear_case: CitedStatement[]
    contradictory_evidence: CitedStatement[]
    risks: CitedStatement[]
    invalidation_conditions: CitedStatement[]
    research_questions: CitedStatement[]
    source_quality: {
      source_count: number
      independent_source_count: number
      authority_counts: Record<string, number>
      discovery_only_count: number
    }
    research_priority: { label: 'low' | 'medium' | 'high'; score: number }
    confidence: {
      label: 'low' | 'medium' | 'high'
      score: number
      limitations: string[]
    }
    market_awareness: {
      awareness_state: string
      pricing_state: string
      reporting_breadth: number
    }
    investment_lens?: InvestmentLens | null
    scope: 'current_source_mvp'
  }
  sources: OpportunitySource[]
  as_of: string
  schema_version: 'research_opportunity.v1' | 'research_opportunity.v2'
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(isString)
}

function isCitedStatement(value: unknown): value is CitedStatement {
  return (
    isRecord(value) &&
    isString(value.text) &&
    (value.claim_type === 'fact' ||
      value.claim_type === 'signal' ||
      value.claim_type === 'inference' ||
      value.claim_type === 'research_hypothesis') &&
    isStringArray(value.claim_ids) &&
    isStringArray(value.premise_claim_ids) &&
    isStringArray(value.evidence_ids) &&
    isStringArray(value.source_ids)
  )
}

function isSource(value: unknown): value is OpportunitySource {
  return (
    isRecord(value) &&
    isString(value.source_snapshot_id) &&
    isString(value.title) &&
    isString(value.publisher) &&
    (value.url === null || isString(value.url)) &&
    (value.source_class === 'primary_evidence' ||
      value.source_class === 'reporting' ||
      value.source_class === 'discovery') &&
    isString(value.document_type) &&
    isString(value.authority_tier) &&
    isString(value.published_at)
  )
}

function isAffectedArea(value: unknown): value is AffectedArea {
  return (
    isRecord(value) &&
    isString(value.name) &&
    (value.relationship === 'direct' ||
      value.relationship === 'second_order' ||
      value.relationship === 'third_order') &&
    (value.direction === 'positive' ||
      value.direction === 'negative' ||
      value.direction === 'mixed' ||
      value.direction === 'unknown') &&
    isCitedStatement(value.rationale)
  )
}

function isInvestmentLens(value: unknown): value is InvestmentLens {
  return (
    isRecord(value) &&
    value.orientation === 'long_term_accumulation' &&
    (value.research_posture === 'research_now' ||
      value.research_posture === 'watch_for_confirmation' ||
      value.research_posture === 'insufficient_evidence') &&
    isCitedStatement(value.long_term_relevance) &&
    isCitedStatement(value.posture_rationale) &&
    Array.isArray(value.what_to_watch) &&
    value.what_to_watch.every(isCitedStatement) &&
    value.capital_deployment_assessment === 'insufficient_data' &&
    isStringArray(value.capital_deployment_limitations)
  )
}

function isOpportunity(value: unknown): value is ResearchOpportunity {
  if (
    !isRecord(value) ||
    !isString(value.opportunity_id) ||
    !isString(value.run_id) ||
    (value.status !== 'complete' && value.status !== 'incomplete') ||
    !isRecord(value.document) ||
    !Array.isArray(value.sources) ||
    !value.sources.every(isSource) ||
    (value.schema_version !== 'research_opportunity.v1' &&
      value.schema_version !== 'research_opportunity.v2')
  ) {
    return false
  }
  const document = value.document
  return (
    isRecord(document.theme) &&
    isString(document.theme.name) &&
    isString(document.theme.description) &&
    isCitedStatement(document.summary) &&
    isCitedStatement(document.why_now) &&
    Array.isArray(document.detected_signals) &&
    Array.isArray(document.affected_industries) &&
    document.affected_industries.every(isAffectedArea) &&
    Array.isArray(document.affected_companies) &&
    document.affected_companies.every(isAffectedArea) &&
    isCitedStatement(document.research_thesis) &&
    isCitedStatement(document.mechanism) &&
    Array.isArray(document.bull_case) &&
    document.bull_case.every(isCitedStatement) &&
    Array.isArray(document.bear_case) &&
    document.bear_case.every(isCitedStatement) &&
    Array.isArray(document.contradictory_evidence) &&
    document.contradictory_evidence.every(isCitedStatement) &&
    Array.isArray(document.risks) &&
    document.risks.every(isCitedStatement) &&
    Array.isArray(document.invalidation_conditions) &&
    document.invalidation_conditions.every(isCitedStatement) &&
    Array.isArray(document.research_questions) &&
    document.research_questions.every(isCitedStatement) &&
    isRecord(document.source_quality) &&
    isRecord(document.research_priority) &&
    isRecord(document.confidence) &&
    isRecord(document.market_awareness) &&
    (value.schema_version === 'research_opportunity.v1'
      ? document.investment_lens === undefined ||
        document.investment_lens === null ||
        isInvestmentLens(document.investment_lens)
      : isInvestmentLens(document.investment_lens)) &&
    document.scope === 'current_source_mvp'
  )
}

function parseRun(value: unknown): DiscoveryRun {
  if (
    !isRecord(value) ||
    !isString(value.run_id) ||
    !isString(value.current_stage) ||
    (value.status !== 'queued' &&
      value.status !== 'running' &&
      value.status !== 'complete' &&
      value.status !== 'incomplete' &&
      value.status !== 'failed' &&
      value.status !== 'cancelled') ||
    (value.error_code !== null && typeof value.error_code !== 'string')
  ) {
    throw new Error('Discovery run response was malformed')
  }
  return value as DiscoveryRun
}

function parseOpportunities(value: unknown): ResearchOpportunity[] {
  if (
    !isRecord(value) ||
    !Array.isArray(value.opportunities) ||
    !value.opportunities.every(isOpportunity)
  ) {
    throw new Error('Research opportunities response was malformed')
  }
  return value.opportunities
}

export async function startDiscoveryRun(
  signal: AbortSignal,
): Promise<DiscoveryRun> {
  return parseRun(
    await postJsonBody(
      `${basePath}/runs`,
      { window_hours: 48, maximum_themes: 3, focus_topics: [] },
      signal,
    ),
  )
}

export async function fetchDiscoveryRun(
  runId: string,
  signal: AbortSignal,
): Promise<DiscoveryRun> {
  return parseRun(await getJson(`${basePath}/runs/${runId}`, signal))
}

export async function fetchResearchOpportunities(
  signal: AbortSignal,
  runId?: string,
): Promise<ResearchOpportunity[]> {
  const query = runId ? `?run_id=${encodeURIComponent(runId)}` : ''
  return parseOpportunities(
    await getJson(`${basePath}/opportunities${query}`, signal),
  )
}
