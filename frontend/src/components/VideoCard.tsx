import type { VideoSearchResult } from "../types";

interface VideoCardProps {
  video: VideoSearchResult;
  onSelect: (video: VideoSearchResult) => void;
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function VideoCard({ video, onSelect }: VideoCardProps) {
  return (
    <button className="video-card" onClick={() => onSelect(video)}>
      <div className="video-thumbnail">
        {video.thumbnail_url ? (
          <img src={video.thumbnail_url} alt={video.title} />
        ) : (
          <div className="thumbnail-placeholder" />
        )}
        {video.duration_seconds > 0 && (
          <span className="video-duration">
            {formatDuration(video.duration_seconds)}
          </span>
        )}
      </div>
      <div className="video-info">
        <div className="video-title">{video.title}</div>
        <div className="video-channel">{video.channel}</div>
      </div>
    </button>
  );
}
