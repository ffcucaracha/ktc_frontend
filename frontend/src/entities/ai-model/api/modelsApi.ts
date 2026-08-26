import { apiRequest } from "../../../shared/api/client";
import type { AiModelInfo } from "./types";

export async function listAiModels(): Promise<AiModelInfo[]> {
  return apiRequest<AiModelInfo[]>("/admin/ai-models", { auth: true });
}
