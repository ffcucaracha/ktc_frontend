export interface AiModelTopFeature {
  name: string;
  importance: number;
}

export interface AiModelValidationMetrics {
  accuracy?: number;
  precision?: number;
  recall?: number;
  f1?: number;
  tp?: number;
  fp?: number;
  tn?: number;
  fn?: number;
  positive_rows?: number;
  negative_rows?: number;
}

export interface AiModelInfo {
  model_version: string;
  target?: string;
  horizon_seconds?: number;
  threshold?: number;
  feature_names?: string[];
  feature_importances?: Record<string, number>;
  top_features?: AiModelTopFeature[];
  training_rows?: number;
  validation_rows?: number;
  dataset_rows?: number;
  dataset_sessions?: number;
  training_sessions?: number;
  validation_sessions?: number;
  dataset_path?: string;
  data_provenance?: string;
  validation_metrics?: AiModelValidationMetrics;
  metadata_file: string;
  artifact_file: string;
  artifact_exists: boolean;
  active: boolean;
}
