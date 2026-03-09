interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  isUrl: boolean;
  isLoading: boolean;
}

export function SearchInput({
  value,
  onChange,
  isUrl,
  isLoading,
}: SearchInputProps) {
  return (
    <div className="search-input-container">
      <input
        type="text"
        className="search-input"
        placeholder="Paste a YouTube URL or search for a song..."
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoFocus
      />
      <div className="search-status">
        {isLoading && <span className="status-searching">Searching...</span>}
        {isUrl && !isLoading && (
          <span className="status-url">URL detected</span>
        )}
      </div>
    </div>
  );
}
