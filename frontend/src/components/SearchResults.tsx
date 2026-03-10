import type { VideoSearchResult } from "../types";
import { VideoCard } from "./VideoCard";

interface SearchResultsProps {
  results: VideoSearchResult[];
  isLoading: boolean;
  onSelect: (video: VideoSearchResult) => void;
}

export function SearchResults({
  results,
  isLoading,
  onSelect,
}: SearchResultsProps) {
  if (isLoading) {
    return <div className="search-loading">Searching YouTube...</div>;
  }

  if (results.length === 0) {
    return null;
  }

  return (
    <div className="search-results">
      {results.map((video) => (
        <VideoCard key={video.video_id} video={video} onSelect={onSelect} />
      ))}
    </div>
  );
}
