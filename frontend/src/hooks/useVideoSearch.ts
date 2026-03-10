import { useCallback, useEffect, useMemo, useState } from "react";
import { searchVideos } from "../api/search";
import type { VideoSearchResult } from "../types";
import { useDebounce } from "./useDebounce";

const URL_PATTERN = /^(?:https?:\/\/|(?:www\.)?youtube\.com|youtu\.be)/i;

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

  const debouncedQuery = useDebounce(query);
  const inputIsUrl = isUrl(query);
  const directUrl = useMemo(
    () => (inputIsUrl ? query.trim() : null),
    [inputIsUrl, query]
  );

  useEffect(() => {
    if (inputIsUrl) {
      setResults([]);
      setError(null);
      return;
    }

    if (!debouncedQuery.trim()) {
      setResults([]);
      return;
    }

    const controller = new AbortController();
    setIsLoading(true);
    setError(null);

    searchVideos(debouncedQuery, 5, controller.signal)
      .then((res) => {
        setResults(res);
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [debouncedQuery, inputIsUrl]);

  const selectVideo = useCallback((video: VideoSearchResult) => {
    setSelectedVideo(video);
    setResults([]);
    setQuery(video.url);
  }, []);

  const clear = useCallback(() => {
    setQuery("");
    setResults([]);
    setSelectedVideo(null);
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
