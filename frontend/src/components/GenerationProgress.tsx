import type { JobResponse } from "../types";
import { getDownloadUrl } from "../api/generate";

const STAGES = [
  { key: "downloading", label: "Downloading video" },
  { key: "lyrics", label: "Looking up lyrics" },
  { key: "separating", label: "Separating vocals" },
  { key: "aligning", label: "Aligning lyrics" },
  { key: "rendering", label: "Rendering video" },
];

interface GenerationProgressProps {
  job: JobResponse;
  jobId: string;
  onReset: () => void;
}

function getStageIndex(stage: string | null): number {
  if (!stage) return -1;
  return STAGES.findIndex((s) => s.key === stage);
}

export function GenerationProgress({
  job,
  jobId,
  onReset,
}: GenerationProgressProps) {
  const currentStageIndex = getStageIndex(job.stage);

  if (job.status === "failed") {
    return (
      <div className="generation-progress progress-failed">
        <h2>Generation Failed</h2>
        <p className="error-message">{job.error}</p>
        <button className="btn-clear" onClick={onReset}>
          Try Again
        </button>
      </div>
    );
  }

  if (job.status === "completed") {
    return (
      <div className="generation-progress progress-completed">
        <h2>Karaoke Video Ready</h2>
        <a
          href={getDownloadUrl(jobId)}
          className="btn-download"
          download
        >
          Download Video
        </a>
        <button className="btn-clear" onClick={onReset}>
          New Song
        </button>
      </div>
    );
  }

  return (
    <div className="generation-progress progress-running">
      <h2>Generating...</h2>
      <div className="stage-list">
        {STAGES.map((stage, i) => {
          let stageClass = "stage-pending";
          if (i < currentStageIndex) stageClass = "stage-done";
          else if (i === currentStageIndex) stageClass = "stage-active";

          return (
            <div key={stage.key} className={`stage-item ${stageClass}`}>
              <span className="stage-indicator">
                {i < currentStageIndex ? "\u2713" : i === currentStageIndex ? "\u25CF" : "\u25CB"}
              </span>
              <span className="stage-label">{stage.label}</span>
            </div>
          );
        })}
      </div>
      {job.progress_message && (
        <p className="progress-message">{job.progress_message}</p>
      )}
    </div>
  );
}
