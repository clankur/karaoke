import { useCallback, useEffect, useState } from "react";
import { searchVideos } from "../api/search";
import type { VideoSearchResult } from "../types";
import { useDebounce } from "./useDebounce";

const URL_PATTERN = /^https?:\/\/|youtube\.com|youtu\.be/i;

function isUrl(input: string): boolean {
  return URL_PATTERN.test(input.trim());
}

export function useVideoSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<VideoSearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedVideo, setSelectedVideo] = useState<VideoSearchResult | null>(
    null
  );
  const [directUrl, setDirectUrl] = useState<string | null>(null);

  const debouncedQuery = useDebounce(query, 300);
  const inputIsUrl = isUrl(query);

  useEffect(() => {
    if (inputIsUrl) {
      setDirectUrl(query.trim());
      setResults([]);
      setError(null);
      return;
    }

    setDirectUrl(null);

    if (!debouncedQuery.trim()) {
      setResults([]);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setError(null);

    searchVideos(debouncedQuery)
      .then((res) => {
        if (!cancelled) setResults(res);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [debouncedQuery, inputIsUrl, query]);

  const selectVideo = useCallback((video: VideoSearchResult) => {
    setSelectedVideo(video);
    setResults([]);
    setQuery(video.url);
  }, []);

  const clear = useCallback(() => {
    setQuery("");
    setResults([]);
    setSelectedVideo(null);
    setDirectUrl(null);
    setError(null);
  }, []);

  return {
    query,
    setQuery,
    results,
    isLoading,
    error,
    selectedVideo,
    directUrl,
    inputIsUrl,
    selectVideo,
    clear,
  };
}
