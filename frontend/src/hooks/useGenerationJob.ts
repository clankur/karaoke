import { useCallback, useEffect, useRef, useState } from "react";
import { getJobStatus, startGeneration } from "../api/generate";
import type { GenerateRequest, JobResponse } from "../types";

export function useGenerationJob() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<JobResponse | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const startJob = useCallback(
    async (request: GenerateRequest) => {
      setError(null);
      setJob(null);
      setIsGenerating(true);
      try {
        const id = await startGeneration(request);
        setJobId(id);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to start job");
        setIsGenerating(false);
      }
    },
    []
  );

  // Start polling when jobId changes
  useEffect(() => {
    if (!jobId) return;

    const poll = async () => {
      try {
        const status = await getJobStatus(jobId);
        setJob(status);
        if (status.status === "completed" || status.status === "failed") {
          stopPolling();
          setIsGenerating(false);
        }
      } catch {
        // Keep polling on transient errors
      }
    };

    // Poll immediately, then every 2s
    poll();
    intervalRef.current = setInterval(poll, 2000);

    return stopPolling;
  }, [jobId, stopPolling]);

  const reset = useCallback(() => {
    stopPolling();
    setJobId(null);
    setJob(null);
    setIsGenerating(false);
    setError(null);
  }, [stopPolling]);

  return { jobId, job, isGenerating, error, startJob, reset };
}
