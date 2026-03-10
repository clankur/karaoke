import { useCallback, useEffect, useRef, useState } from "react";
import { getJobStatus, startGeneration } from "../api/generate";
import type { GenerateRequest, JobResponse } from "../types";

export function useGenerationJob() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<JobResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isGenerating =
    jobId !== null &&
    (job === null || (job.status !== "completed" && job.status !== "failed"));

  const stopPolling = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  const startJob = useCallback(
    async (request: GenerateRequest) => {
      setError(null);
      setJob(null);
      try {
        const id = await startGeneration(request);
        setJobId(id);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to start job");
      }
    },
    []
  );

  // Poll using setTimeout chain (avoids overlapping requests)
  useEffect(() => {
    if (!jobId) return;

    let stopped = false;

    const poll = async () => {
      try {
        const status = await getJobStatus(jobId);
        if (stopped) return;
        setJob(status);
        if (status.status !== "completed" && status.status !== "failed") {
          timeoutRef.current = setTimeout(poll, 2000);
        }
      } catch {
        if (!stopped) {
          timeoutRef.current = setTimeout(poll, 2000);
        }
      }
    };

    poll();

    return () => {
      stopped = true;
      stopPolling();
    };
  }, [jobId, stopPolling]);

  const reset = useCallback(() => {
    stopPolling();
    setJobId(null);
    setJob(null);
    setError(null);
  }, [stopPolling]);

  return { jobId, job, isGenerating, error, startJob, reset };
}
