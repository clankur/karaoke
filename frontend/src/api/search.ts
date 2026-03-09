import type { VideoSearchResult } from "../types";

export async function searchVideos(
  query: string,
  maxResults = 5
): Promise<VideoSearchResult[]> {
  const params = new URLSearchParams({
    q: query,
    max_results: String(maxResults),
  });
  const response = await fetch(`/api/search?${params}`);
  if (!response.ok) {
    throw new Error(`Search failed: ${response.statusText}`);
  }
  const data = await response.json();
  return data.results;
}
