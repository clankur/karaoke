import { useState } from "react";

export interface GenerationOptions {
  whisper_model: string;
  language: string | null;
  demucs_model: string;
  words_per_line: number;
  keep_vocals: boolean;
  vocals_volume: number;
  use_synced_lyrics: boolean;
}

interface GenerationConfigProps {
  onGenerate: (options: GenerationOptions) => void;
  disabled: boolean;
}

export function GenerationConfig({ onGenerate, disabled }: GenerationConfigProps) {
  const [whisperModel, setWhisperModel] = useState("base");
  const [language, setLanguage] = useState("");
  const [wordsPerLine, setWordsPerLine] = useState(7);
  const [keepVocals, setKeepVocals] = useState(true);
  const [vocalsVolume, setVocalsVolume] = useState(0.3);
  const [useSyncedLyrics, setUseSyncedLyrics] = useState(true);

  const handleGenerate = () => {
    onGenerate({
      whisper_model: whisperModel,
      language: language.trim() || null,
      demucs_model: "htdemucs",
      words_per_line: wordsPerLine,
      keep_vocals: keepVocals,
      vocals_volume: vocalsVolume,
      use_synced_lyrics: useSyncedLyrics,
    });
  };

  return (
    <div className="generation-config">
      <h2>Options</h2>

      <div className="config-grid">
        <div className="config-field">
          <label htmlFor="whisper-model">Whisper Model</label>
          <select
            id="whisper-model"
            value={whisperModel}
            onChange={(e) => setWhisperModel(e.target.value)}
            disabled={disabled}
          >
            <option value="tiny">Tiny (fastest)</option>
            <option value="base">Base (default)</option>
            <option value="small">Small</option>
            <option value="medium">Medium</option>
            <option value="large">Large (most accurate)</option>
          </select>
        </div>

        <div className="config-field">
          <label htmlFor="language">Language</label>
          <input
            id="language"
            type="text"
            placeholder="auto-detect"
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            disabled={disabled}
          />
        </div>

        <div className="config-field">
          <label htmlFor="words-per-line">Words per Line</label>
          <input
            id="words-per-line"
            type="number"
            min={1}
            max={20}
            value={wordsPerLine}
            onChange={(e) => setWordsPerLine(Number(e.target.value))}
            disabled={disabled}
          />
        </div>

        <div className="config-field config-checkbox">
          <label>
            <input
              type="checkbox"
              checked={useSyncedLyrics}
              onChange={(e) => setUseSyncedLyrics(e.target.checked)}
              disabled={disabled}
            />
            Use synced lyrics
          </label>
        </div>

        <div className="config-field config-checkbox">
          <label>
            <input
              type="checkbox"
              checked={keepVocals}
              onChange={(e) => setKeepVocals(e.target.checked)}
              disabled={disabled}
            />
            Keep vocals in output
          </label>
        </div>

        {keepVocals && (
          <div className="config-field">
            <label htmlFor="vocals-volume">
              Vocals Volume: {vocalsVolume.toFixed(1)}
            </label>
            <input
              id="vocals-volume"
              type="range"
              min={0}
              max={1}
              step={0.1}
              value={vocalsVolume}
              onChange={(e) => setVocalsVolume(Number(e.target.value))}
              disabled={disabled}
            />
          </div>
        )}
      </div>

      <button
        className="btn-generate"
        onClick={handleGenerate}
        disabled={disabled}
      >
        Generate Karaoke
      </button>
    </div>
  );
}
