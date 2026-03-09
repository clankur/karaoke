import { SearchInput } from "./components/SearchInput";
import { SearchResults } from "./components/SearchResults";
import { useVideoSearch } from "./hooks/useVideoSearch";
import "./App.css";

function App() {
  const {
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
  } = useVideoSearch();

  return (
    <div className="app">
      <header className="app-header">
        <h1>Karaoke</h1>
        <p className="app-subtitle">
          Paste a YouTube URL or search for a song to get started
        </p>
      </header>

      <main className="app-main">
        <SearchInput
          value={query}
          onChange={setQuery}
          isUrl={inputIsUrl}
          isLoading={isLoading}
        />

        {error && <div className="search-error">{error}</div>}

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
            <button className="btn-clear" onClick={clear}>
              Clear
            </button>
          </div>
        )}

        {directUrl && !selectedVideo && (
          <div className="selected-video">
            <h2>Ready</h2>
            <code className="selected-url">{directUrl}</code>
            <button className="btn-clear" onClick={clear}>
              Clear
            </button>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
