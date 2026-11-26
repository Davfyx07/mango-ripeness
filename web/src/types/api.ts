export const classes = ["unripe", "partially_ripe", "ripe"] as const;
export type RipenessClass = (typeof classes)[number];
export interface HealthResponse {
  status: "ok";
  models_available: number;
}
export interface ModelInfo {
  id: string;
  nombre: string;
  familia: "CNN" | "Transformer" | "Ensamble";
  accuracy_test: number;
}
export type PredictionProbabilities = Record<RipenessClass, number>;
export interface PredictionResponse {
  model: string;
  label: RipenessClass;
  confidence: number;
  probabilities: PredictionProbabilities;
  inference_ms: number;
}
export interface ApiError {
  detail: string;
}
