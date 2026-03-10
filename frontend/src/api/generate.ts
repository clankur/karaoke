import type { GenerateRequest, JobResponse } from "../types";

export async function startGeneration(
  request: GenerateRequest
): Promise<string> {
  const response = await fetch("/api/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new Error(`Generation failed: ${response.statusText}`);
  }
  const data = await response.json();
  return data.job_id;
}

export async function getJobStatus(jobId: string): Promise<JobResponse> {
  const response = await fetch(`/api/jobs/${jobId}`);
  if (!response.ok) {
    throw new Error(`Failed to get job status: ${response.statusText}`);
  }
  return response.json();
}

export function getDownloadUrl(jobId: string): string {
  return `/api/jobs/${jobId}/download`;
}
