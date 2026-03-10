export interface VideoSearchResult {
  video_id: string;
  title: string;
  thumbnail_url: string;
  channel: string;
  duration_seconds: number;
  url: string;
}

export interface GenerateRequest {
  url: string;
  whisper_model: string;
  language: string | null;
  demucs_model: string;
  words_per_line: number;
  keep_vocals: boolean;
  vocals_volume: number;
  use_synced_lyrics: boolean;
}

export interface JobResponse {
  job_id: string;
  status: "pending" | "running" | "completed" | "failed";
  stage: string | null;
  progress_message: string | null;
  error: string | null;
}
