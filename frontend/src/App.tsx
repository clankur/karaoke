import { SearchInput } from "./components/SearchInput";
import { SearchResults } from "./components/SearchResults";
import { GenerationConfig, type GenerationOptions } from "./components/GenerationConfig";
import { GenerationProgress } from "./components/GenerationProgress";
import { useVideoSearch } from "./hooks/useVideoSearch";
import { useGenerationJob } from "./hooks/useGenerationJob";
import type { GenerateRequest } from "./types";
import "./App.css";

function App() {
  const {
    query,
    setQuery,
    results,
    isLoading,
    error: searchError,
    selectedVideo,
    directUrl,
    inputIsUrl,
    selectVideo,
    clear: clearSearch,
  } = useVideoSearch();

  const {
    jobId,
    job,
    isGenerating,
    error: genError,
    startJob,
    reset: resetJob,
  } = useGenerationJob();

  const videoUrl = selectedVideo?.url ?? directUrl;
  const hasVideo = !!videoUrl;
  const showConfig = hasVideo && !jobId;
  const showProgress = !!jobId && !!job;

  const handleGenerate = (options: GenerationOptions) => {
    if (!videoUrl) return;
    const request: GenerateRequest = { url: videoUrl, ...options };
    startJob(request);
  };

  const handleReset = () => {
    resetJob();
    clearSearch();
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Karaoke</h1>
        <p className="app-subtitle">
          Paste a YouTube URL or search for a song to get started
        </p>
      </header>

      <main className="app-main">
        {!jobId && (
          <>
            <SearchInput
              value={query}
              onChange={setQuery}
              isUrl={inputIsUrl}
              isLoading={isLoading}
            />

            {searchError && <div className="search-error">{searchError}</div>}

            <SearchResults
              results={results}
              isLoading={isLoading}
              onSelect={selectVideo}
            />

            {selectedVideo && (
              <div className="selected-video">
                <h2>Selected</h2>
                <div className="selected-video-details">
                  {selectedVideo.thumbnail_url && (
                    <img
                      src={selectedVideo.thumbnail_url}
                      alt={selectedVideo.title}
                      className="selected-thumbnail"
                    />
                  )}
                  <div>
                    <div className="selected-title">{selectedVideo.title}</div>
                    <div className="selected-channel">
                      {selectedVideo.channel}
                    </div>
                    <code className="selected-url">{selectedVideo.url}</code>
                  </div>
                </div>
                <button className="btn-clear" onClick={clearSearch}>
                  Clear
                </button>
              </div>
            )}

            {directUrl && !selectedVideo && (
              <div className="selected-video">
                <h2>Ready</h2>
                <code className="selected-url">{directUrl}</code>
                <button className="btn-clear" onClick={clearSearch}>
                  Clear
                </button>
              </div>
            )}
          </>
        )}

        {genError && <div className="search-error">{genError}</div>}

        {showConfig && (
          <GenerationConfig
            onGenerate={handleGenerate}
            disabled={isGenerating}
          />
        )}

        {showProgress && (
          <GenerationProgress
            job={job}
            jobId={jobId}
            onReset={handleReset}
          />
        )}
      </main>
    </div>
  );
}

export default App;
