export type AccessLevel = "PRIVATE" | "CAREGIVER" | "FAMILY_SUMMARY" | "FULL";
export type VerificationStatus = "PENDING" | "VERIFIED" | "REJECTED" | "NEEDS_REVIEW";
export type DocumentStatus = "UPLOADED" | "PROCESSING" | "PARSED" | "NEEDS_OCR" | "FAILED";
export type VectorIndexStatus = "NOT_INDEXED" | "INDEXING" | "INDEXED" | "INDEX_FAILED";
export type CandidateStatus = "PENDING" | "ACCEPTED" | "CORRECTED" | "REJECTED" | "NEEDS_CLARIFICATION";
export type CandidateType = "condition" | "medication" | "lab" | "symptom" | "measurement";
export type ProvenanceType =
  | "DOCUMENT_VERIFIED"
  | "USER_REPORTED"
  | "DEVICE_MEASURED"
  | "AI_EXTRACTED"
  | "AI_DERIVED"
  | "USER_CORRECTED";

export type Profile = {
  id: string;
  owner_user_id: string;
  display_name: string;
  relationship_to_owner: string;
  date_of_birth: string | null;
  sex: string | null;
  access_level: AccessLevel;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type HealthEvent = {
  id: string;
  profile_id: string;
  event_type: string;
  event_date: string;
  end_date: string | null;
  title: string;
  description: string | null;
  verification_status: VerificationStatus;
  provenance: ProvenanceType;
  confidence: number | null;
  source_document_id: string | null;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
};

export type Observation = {
  id: string;
  profile_id: string;
  health_event_id: string | null;
  source_message_id: string | null;
  code: string | null;
  display_name: string;
  value_number: number | null;
  value_text: string | null;
  unit: string | null;
  reference_low: number | null;
  reference_high: number | null;
  interpretation: string | null;
  observed_at: string;
  provenance: ProvenanceType;
  verification_status: VerificationStatus;
  created_at: string;
  updated_at: string;
};

export type Medication = {
  id: string;
  profile_id: string;
  name: string;
  dose: string | null;
  dose_unit: string | null;
  frequency: string | null;
  route: string | null;
  start_date: string | null;
  end_date: string | null;
  is_active: boolean;
  provenance: ProvenanceType;
  verification_status: VerificationStatus;
  source_event_id: string | null;
};

export type Symptom = {
  id: string;
  profile_id: string;
  name: string;
  severity: number | null;
  started_at: string | null;
  ended_at: string | null;
  notes: string | null;
  provenance: ProvenanceType;
  verification_status: VerificationStatus;
  source_message_id: string | null;
  created_at: string;
  updated_at: string;
};

export type SourceDocument = {
  id: string;
  profile_id: string;
  original_filename: string;
  mime_type: string;
  document_date: string | null;
  status: DocumentStatus;
  page_count: number;
  has_extracted_text: boolean;
  vector_index_status: VectorIndexStatus;
  vector_indexed_at: string | null;
  vector_chunk_count: number;
  created_at: string;
  updated_at: string;
};

export type DocumentPage = {
  id: string;
  document_id: string;
  page_number: number;
  text: string;
  created_at: string;
};

export type ExtractedCandidate = {
  id: string;
  document_id: string;
  candidate_type: CandidateType;
  structured_data: Record<string, unknown>;
  confidence: number;
  status: CandidateStatus;
  evidence_text: string;
  page_number: number | null;
  reviewed_by_user_id: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ExtractionSummary = {
  document_id: string;
  status: "completed";
  candidate_count: number;
  by_type: Record<string, number>;
  reused_existing: boolean;
};

export type CandidateReviewResult = {
  candidate: ExtractedCandidate;
  trusted_record: { record_type: string; record_id: string } | null;
};

export type FamilyRelationship = {
  id: string;
  source_profile_id: string;
  target_profile_id: string;
  relationship_type: string;
  created_at: string;
};

export type FamilyRecordState = "DOCUMENTED" | "NOT_DOCUMENTED" | "UNKNOWN" | "PRIVATE";

export type FamilyProfileSummary = {
  profile_id: string;
  label: string;
  relationship_to_owner: string;
  access_level: AccessLevel;
  is_private: boolean;
  permission_id: string | null;
  documented_condition_count: number | null;
  shared_conditions: string[] | null;
};

export type FamilyData = {
  requester_user_id: string;
  selected_profile_id: string;
  profiles: FamilyProfileSummary[];
  relationships: FamilyRelationship[];
};

export type FamilyEvidenceReference = {
  health_event_id: string;
  evidence_path: string;
  source_count: number;
};

export type FamilyConditionContributor = {
  profile_id: string;
  label: string;
  access_level: AccessLevel;
  state: FamilyRecordState;
  generation: number;
  branch: string;
  health_event_id: string | null;
  verification_status: VerificationStatus | null;
  evidence: FamilyEvidenceReference[];
};

export type FamilyConditionPattern = {
  condition_name: string;
  profile_count: number;
  permitted_profile_count: number;
  generation_count: number;
  branches: string[];
  contributing_profiles: FamilyConditionContributor[];
  profile_states: FamilyConditionContributor[];
  evidence_count: number;
  confidence: "HIGH" | "MODERATE" | "LOW";
  statement: string;
  notes: string[];
};

export type FamilyPatternsResponse = {
  requester_user_id: string;
  selected_profile_id: string;
  patterns: FamilyConditionPattern[];
};

export type FamilyPermission = {
  permission_id: string;
  profile_id: string;
  access_level: AccessLevel;
  scope: string | null;
};

export type AuditLog = {
  id: string;
  actor_user_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  before_state: Record<string, unknown> | null;
  after_state: Record<string, unknown> | null;
  created_at: string;
};

export type HealthResponse = {
  status: "ok" | "degraded" | "unavailable";
  service: string;
  version: string;
  checks: {
    api: "ok";
    database: "ok" | "unavailable";
    llm: "ok" | "unavailable";
    embedding: "ok" | "unavailable";
    vector_database: "ok" | "unavailable";
    upload_storage: "ok" | "unavailable";
    safety: "ok";
    agent_graph: "ok" | "unavailable";
  };
};

export type SystemStatus = {
  environment: string;
  database: "connected" | "unavailable";
  upload_directory: "configured" | "unavailable";
  vector_provider: "Pinecone";
  vector_status: "connected" | "unavailable";
  vector_index: string;
  vector_dimension: number | null;
  vector_metric: string | null;
  vector_count: number | null;
  embedding_provider: "Ollama";
  embedding_model: string;
  embedding_status: "connected" | "unavailable";
  embedding_dimension: number | null;
  compatibility: "compatible" | "dimension_mismatch" | "unavailable";
  llm_provider: "Ollama";
  llm_model: string;
  llm: "connected" | "unavailable";
  safety_policy: "enabled";
  safety_policy_version: string;
  agent_orchestration: "enabled" | "unavailable";
};

export type AgentIntent =
  | "DAILY_LOG"
  | "RECORD_LOOKUP"
  | "TIMELINE_QUERY"
  | "EVIDENCE_QUERY"
  | "ANALYTICS_QUERY"
  | "FAMILY_QUERY"
  | "DOCTOR_VISIT"
  | "GENERAL_HEALTH_INFORMATION"
  | "UNSUPPORTED_MEDICAL_ACTION"
  | "UNKNOWN";

export type AgentSource = {
  source_type: string;
  label: string;
  evidence_path: string | null;
  entity_type: string | null;
  entity_id: string | null;
  document_id: string | null;
  page_number: number | null;
};

export type AskResponse = {
  request_id: string;
  intent: AgentIntent;
  answer: string;
  conversation_id: string | null;
  pending_id: string | null;
  clarification_required: boolean;
  sources: AgentSource[];
  evidence: Record<string, unknown>[];
  safety: SafetyResult | null;
  warnings: string[];
  actions: string[];
  structured_result: Record<string, unknown> | null;
  nodes_run: string[] | null;
};

export type DocumentIndexSummary = {
  document_id: string;
  status: VectorIndexStatus;
  chunk_count: number;
};

export type EvidenceContext = {
  score: number;
  similarity_label: "retrieval similarity";
  document_id: string;
  filename: string;
  page_number: number;
  text: string;
  chunk_index: number;
};

export type RetrievalSearchResponse = {
  query: string;
  results: EvidenceContext[];
  indexed_document_count: number;
};

export type GlucoseContext = "FASTING" | "BEFORE_MEAL" | "AFTER_MEAL" | "RANDOM" | "UNKNOWN";
export type SymptomSeverity = "MILD" | "MODERATE" | "SEVERE" | "UNKNOWN";
export type PendingHealthEntryStatus =
  | "PENDING_REVIEW"
  | "NEEDS_CLARIFICATION"
  | "CONFIRMED"
  | "REJECTED";

export type GlucoseEntry = {
  entry_type: "glucose";
  value: number;
  unit: "mg/dL" | "mmol/L";
  context: GlucoseContext;
  observed_at: string | null;
  confidence: number;
};

export type BloodPressureEntry = {
  entry_type: "blood_pressure";
  systolic: number;
  diastolic: number;
  unit: "mmHg";
  observed_at: string | null;
  confidence: number;
};

export type WeightEntry = {
  entry_type: "weight";
  value: number;
  unit: "kg" | "lb" | null;
  observed_at: string | null;
  confidence: number;
};

export type DailyObservation = GlucoseEntry | BloodPressureEntry | WeightEntry;

export type SleepEntry = {
  duration_minutes: number;
  sleep_date: string | null;
  quality: string | null;
  confidence: number;
};

export type ActivityEntry = {
  activity_type: string;
  duration_minutes: number | null;
  distance: number | null;
  distance_unit: "m" | "km" | "mi" | null;
  observed_at: string | null;
  confidence: number;
};

export type DailySymptomEntry = {
  name: string;
  severity: SymptomSeverity;
  started_at: string | null;
  duration_text: string | null;
  notes: string | null;
  confidence: number;
};

export type ClarificationQuestion = {
  field: string;
  question: string;
  options: string[];
};

export type DailyHealthExtraction = {
  observations: DailyObservation[];
  symptoms: DailySymptomEntry[];
  activities: ActivityEntry[];
  sleep_entries: SleepEntry[];
  clarifications: ClarificationQuestion[];
  warnings: string[];
};

export type ChatMessage = {
  id: string;
  conversation_id: string;
  role: "USER" | "ASSISTANT" | "SYSTEM";
  content: string;
  created_at: string;
};

export type TrustedRecord = {
  record_type: "observations" | "symptoms";
  record_id: string;
};

export type PendingHealthEntry = {
  id: string;
  conversation_id: string;
  message_id: string;
  profile_id: string;
  extraction: DailyHealthExtraction;
  status: PendingHealthEntryStatus;
  was_corrected: boolean;
  trusted_records: TrustedRecord[];
  created_at: string;
  updated_at: string;
};

export type ConversationSummary = {
  id: string;
  profile_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
};

export type ConversationDetail = ConversationSummary & {
  messages: ChatMessage[];
  pending_entries: PendingHealthEntry[];
};

export type SafetyDecision = "ALLOW" | "ALLOW_WITH_NOTICE" | "WARN" | "BLOCK" | "ESCALATE";
export type SafetyCategory =
  | "URGENT_SYMPTOM"
  | "MEDICATION_CHANGE"
  | "DIAGNOSIS_REQUEST"
  | "PRESCRIBING_REQUEST"
  | "UNSUPPORTED_CURE_CLAIM"
  | "TREATMENT_REPLACEMENT"
  | "HIGH_RISK_SELF_TREATMENT"
  | "GENERAL_HEALTH_INFORMATION"
  | "LOGGING_ONLY"
  | "UNKNOWN";

export type SafetyResult = {
  decision: SafetyDecision;
  category: SafetyCategory;
  rule_id: string;
  message: string;
  safe_response_override: string | null;
  requires_professional_evaluation: boolean;
  emergency_guidance: boolean;
  audit_metadata: Record<string, unknown>;
  policy_version: string;
};

export type ChatMessageResponse = {
  message_id: string;
  pending_id: string | null;
  status: "STRUCTURED_PREVIEW" | "NEEDS_CLARIFICATION" | "INFORMATIONAL" | "SAFETY_BOUNDARY";
  extraction: DailyHealthExtraction | null;
  questions: ClarificationQuestion[];
  assistant_message: string;
  safety?: SafetyResult | null;
};

export type ConfirmationResponse = {
  pending: PendingHealthEntry;
  trusted_records: TrustedRecord[];
  already_confirmed: boolean;
};

export type ProfileSnapshot = {
  events: HealthEvent[];
  observations: Observation[];
  medications: Medication[];
  symptoms: Symptom[];
  documents: SourceDocument[];
};

export type TimelineEntityType = "health_event" | "observation" | "medication" | "symptom";
export type TimelineType =
  | "CONDITION"
  | "LAB"
  | "MEASUREMENT"
  | "MEDICATION"
  | "SYMPTOM"
  | "PROCEDURE"
  | "HOSPITALIZATION"
  | "LIFESTYLE"
  | "NOTE";
export type TimelineSourceType = "DOCUMENT" | "CHAT" | "MANUAL" | "DERIVED";

export type TimelineItem = {
  id: string;
  entity_id: string;
  entity_type: TimelineEntityType;
  timeline_type: TimelineType;
  title: string;
  description: string | null;
  occurred_at: string | null;
  end_at: string | null;
  date_precision: "EXACT" | "UNKNOWN";
  provenance: ProvenanceType;
  verification_status: VerificationStatus;
  confidence: number | null;
  source_type: TimelineSourceType;
  source_document_id: string | null;
  source_message_id: string | null;
  has_evidence: boolean;
  has_correction: boolean;
  created_at: string;
};

export type TimelineResponse = {
  profile_id: string;
  items: TimelineItem[];
  total: number;
  limit: number;
  offset: number;
};

export type DocumentEvidenceSource = {
  type: "DOCUMENT";
  document_id: string;
  filename: string;
  document_date: string | null;
  page_number: number | null;
  excerpt: string | null;
  page_text: string | null;
  view_source_path: string;
};

export type ChatEvidenceSource = {
  type: "CHAT";
  conversation_id: string;
  message_id: string;
  message: string;
  message_timestamp: string;
  label: "USER-REPORTED SOURCE";
};

export type ManualEvidenceSource = {
  type: "MANUAL" | "DERIVED";
  message: string;
};

export type CorrectionHistoryItem = {
  action: string;
  original_value: string | null;
  corrected_value: string | null;
  changed_fields: string[];
  corrected_at: string;
  actor: string | null;
};

export type EvidenceResponse = {
  profile_id: string;
  entity_id: string;
  entity_type: TimelineEntityType;
  source_type: TimelineSourceType;
  provenance: ProvenanceType;
  verification_status: VerificationStatus;
  source: DocumentEvidenceSource | ChatEvidenceSource | ManualEvidenceSource;
  saved_value: string | null;
  correction_history: CorrectionHistoryItem[];
};

export type MissingEvidenceGap = {
  type:
    | "MISSING_SOURCE"
    | "MISSING_DATE"
    | "UNVERIFIED_FACT"
    | "STALE_MEDICATION_REVIEW"
    | "MISSING_EXPECTED_DOCUMENTATION";
  entity_type: TimelineEntityType;
  entity_id: string;
  message: string;
};

export type MissingEvidenceResponse = {
  profile_id: string;
  gaps: MissingEvidenceGap[];
};

export type AnalyticsMetric =
  | "glucose"
  | "hba1c"
  | "weight"
  | "systolic_blood_pressure"
  | "diastolic_blood_pressure"
  | "sleep_duration"
  | "activity_duration";
export type TrendClassification = "INCREASED" | "DECREASED" | "STABLE" | "INSUFFICIENT_DATA";
export type DataConfidence = "HIGH" | "MODERATE" | "LOW" | "INSUFFICIENT";

export type AnalysisPeriod = {
  start: string;
  end: string;
  days: number;
  boundaries: "inclusive";
};

export type NumericSummary = {
  count: number;
  mean: number | null;
  median: number | null;
  minimum: number | null;
  maximum: number | null;
  standard_deviation: number | null;
  first_value: number | null;
  last_value: number | null;
};

export type AnalyticsEvidence = {
  observation_id: string;
  recorded_at: string;
  original_value: string;
  normalized_value: number;
  normalized_unit: string;
  provenance: ProvenanceType;
  verification_status: VerificationStatus;
  source_type: TimelineSourceType;
  source_label: string;
  source_excerpt: string | null;
  view_source_path: string | null;
  evidence_path: string;
};

export type TrendAnalysisResult = {
  profile_id: string;
  metric: AnalyticsMetric;
  metric_label: string;
  context: GlucoseContext | null;
  unit: string;
  reference_date: string;
  recent_period: AnalysisPeriod;
  baseline_period: AnalysisPeriod;
  recent_count: number;
  baseline_count: number;
  recent_summary: NumericSummary;
  baseline_summary: NumericSummary;
  absolute_change: number | null;
  percent_change: number | null;
  classification: TrendClassification;
  confidence: DataConfidence;
  confidence_reason: string;
  missing_data: string[];
  evidence_ids: string[];
  evidence: AnalyticsEvidence[];
  calculation_version: string;
  stability_threshold_percent: number;
  explanation: string;
  explanation_source: "LLM" | "TEMPLATE";
  display_priority: number | null;
};

export type SymptomEvidence = {
  symptom_id: string;
  recorded_at: string;
  severity: number | null;
  provenance: ProvenanceType;
  verification_status: VerificationStatus;
  evidence_path: string;
};

export type SymptomFrequencyResult = {
  profile_id: string;
  symptom_name: string;
  reference_date: string;
  recent_period: AnalysisPeriod;
  baseline_period: AnalysisPeriod;
  recent_count: number;
  baseline_count: number;
  recent_rate_per_day: number | null;
  baseline_rate_per_day: number | null;
  percent_change: number | null;
  classification: TrendClassification;
  confidence: DataConfidence;
  confidence_reason: string;
  missing_data: string[];
  evidence_ids: string[];
  evidence: SymptomEvidence[];
  calculation_version: string;
  explanation: string;
};

export type AvailableMetric = {
  metric: AnalyticsMetric;
  label: string;
  contexts: GlucoseContext[];
};

export type AvailableMetricsResponse = {
  profile_id: string;
  metrics: AvailableMetric[];
  symptoms: string[];
};

export type WhatChangedResponse = {
  profile_id: string;
  results: TrendAnalysisResult[];
};

export type VisitEvidenceReference = {
  entity_type: TimelineEntityType;
  entity_id: string;
  source_type: TimelineSourceType;
  source_label: string;
  provenance: ProvenanceType;
  verification_status: VerificationStatus;
  has_evidence: boolean;
  evidence_path: string;
};

export type DoctorVisitKnownHistory = {
  record_id: string;
  title: string;
  timeline_type: TimelineType;
  documented_date: string | null;
  end_date: string | null;
  evidence: VisitEvidenceReference;
};

export type DoctorVisitMedication = {
  record_id: string;
  name: string;
  dose: string | null;
  dose_unit: string | null;
  frequency: string | null;
  route: string | null;
  start_date: string | null;
  end_date: string | null;
  last_updated_at: string;
  reconciliation_needed: boolean;
  evidence: VisitEvidenceReference;
};

export type DoctorVisitObservation = {
  record_id: string;
  name: string;
  value: string;
  unit: string | null;
  observed_at: string;
  interpretation: string | null;
  evidence: VisitEvidenceReference;
};

export type DoctorVisitSymptom = {
  name: string;
  report_count: number;
  most_recent: string;
  statement: string;
  evidence: VisitEvidenceReference[];
};

export type DoctorVisitRecentChange = {
  key: string;
  statement: string;
  analysis: TrendAnalysisResult;
};

export type DoctorVisitMissingEvidence = {
  type: string;
  message: string;
  entity_type: TimelineEntityType | null;
  entity_id: string | null;
};

export type DoctorVisitQuestion = {
  question_id: string;
  trigger: string;
  question: string;
};

export type DoctorVisitEvidenceSummary = {
  key: string;
  label: string;
  count: number;
};

export type DoctorVisitBrief = {
  profile_id: string;
  profile_display_name: string;
  profile_age: number | null;
  date_of_birth: string | null;
  relationship_to_owner: string;
  generated_at: string;
  data_cutoff: string;
  summary_version: string;
  overview: string;
  overview_source: "TEMPLATE" | "LLM";
  rewrite_status:
    | "NOT_REQUESTED"
    | "LLM_ACCEPTED"
    | "UNAVAILABLE"
    | "REJECTED_FACT_CHANGE"
    | "REJECTED_SAFETY"
    | "INVALID_RESPONSE";
  known_history: DoctorVisitKnownHistory[];
  recent_changes: DoctorVisitRecentChange[];
  medications: DoctorVisitMedication[];
  recent_labs: DoctorVisitObservation[];
  recent_measurements: DoctorVisitObservation[];
  recent_symptoms: DoctorVisitSymptom[];
  missing_evidence: DoctorVisitMissingEvidence[];
  questions_to_discuss: DoctorVisitQuestion[];
  evidence_summary: DoctorVisitEvidenceSummary[];
  safety_notes: string[];
};
