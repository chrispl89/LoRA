export interface Person {
  id: number
  name: string
  consent_confirmed: boolean
  subject_is_adult: boolean
  created_at: string
}

export interface Photo {
  id: number
  s3_key: string
  content_type: string
  size_bytes: number
  status: string
  created_at: string
}

export interface PreprocessRun {
  id: number
  person_id: number
  status: string
  images_accepted: number
  images_rejected: number
  images_duplicates: number
  output_s3_prefix?: string
  error_message?: string
  started_at?: string
  finished_at?: string
  created_at: string
}

export interface Model {
  id: number
  person_id: number
  name: string
  created_at: string
  versions?: ModelVersion[]
}

export interface ModelVersion {
  id: number
  model_id: number
  version_number: number
  base_model_name: string
  trigger_token: string
  train_config_json?: any
  artifact_s3_prefix?: string
  status: string
  error_message?: string
  created_at: string
}

export interface Generation {
  id: number
  model_version_id: number
  prompt: string
  negative_prompt?: string
  steps: number
  width: number
  height: number
  seed?: number
  status: string
  output_url?: string
  thumbnail_url?: string
  error_message?: string
  created_at: string
}

export interface PresignUploadResponse {
  url: string
  method: string
  key: string
  content_type: string
}
