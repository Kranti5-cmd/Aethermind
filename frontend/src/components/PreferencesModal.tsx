import React, { useState, useEffect } from 'react';
import { CloseIcon, CheckIcon, SlidersIcon, AlertCircleIcon, RefreshCwIcon } from './Icons';

export interface UserPreferences {
  user_id?: string;
  response_style: 'concise' | 'balanced' | 'detailed';
  response_language: string;
  custom_instructions?: string | null;
  updated_at?: string;
}

interface PreferencesModalProps {
  isOpen: boolean;
  onClose: () => void;
  onPreferencesSaved?: (pref: UserPreferences) => void;
}

const LANGUAGES = [
  'English',
  'Spanish',
  'French',
  'German',
  'Hindi',
  'Japanese',
  'Mandarin',
  'Portuguese',
  'Italian',
  'Dutch',
  'Russian',
  'Arabic',
];

export const PreferencesModal: React.FC<PreferencesModalProps> = ({
  isOpen,
  onClose,
  onPreferencesSaved,
}) => {
  const [style, setStyle] = useState<'concise' | 'balanced' | 'detailed'>('balanced');
  const [language, setLanguage] = useState<string>('English');
  const [instructions, setInstructions] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    const fetchPreferences = async () => {
      setIsLoading(true);
      setStatusMessage(null);
      try {
        let res: Response;
        try {
          res = await fetch('/api/preferences');
        } catch {
          res = await fetch('http://127.0.0.1:8000/api/preferences');
        }
        if (res.ok) {
          const data = await res.json();
          if (data.response_style) setStyle(data.response_style);
          if (data.response_language) setLanguage(data.response_language);
          if (data.custom_instructions) setInstructions(data.custom_instructions);
        }
      } catch (err) {
        console.warn('Could not load preferences from backend:', err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchPreferences();
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSave = async () => {
    setIsSaving(true);
    setStatusMessage(null);
    try {
      const payload = {
        response_style: style,
        response_language: language,
        custom_instructions: instructions.trim() || null,
      };

      let res: Response;
      try {
        res = await fetch('/api/preferences', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      } catch {
        res = await fetch('http://127.0.0.1:8000/api/preferences', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      }

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || 'Failed to save preferences');
      }

      const updated = await res.json();
      setStatusMessage({ text: 'Preferences saved to PostgreSQL successfully!', type: 'success' });
      if (onPreferencesSaved) {
        onPreferencesSaved(updated);
      }
      setTimeout(() => {
        onClose();
      }, 900);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error saving preferences';
      setStatusMessage({ text: msg, type: 'error' });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="preferences-modal" onClick={(e) => e.stopPropagation()}>
        <div className="preferences-header">
          <div className="preferences-header-info">
            <div className="preferences-icon-badge">
              <SlidersIcon size={20} />
            </div>
            <div>
              <h2 className="preferences-title">Personalized AI Preferences</h2>
              <p className="preferences-subtitle">
                Tailor how AetherMind formats, styles, and adapts future Gemini responses.
              </p>
            </div>
          </div>
          <button className="preferences-close-btn" onClick={onClose} aria-label="Close settings">
            <CloseIcon size={18} />
          </button>
        </div>

        {isLoading ? (
          <div className="preferences-loading">
            <RefreshCwIcon size={24} className="spin-icon" />
            <span>Loading your saved preferences...</span>
          </div>
        ) : (
          <div className="preferences-body">
            {statusMessage && (
              <div className={`preferences-alert ${statusMessage.type}`}>
                {statusMessage.type === 'success' ? (
                  <CheckIcon size={16} />
                ) : (
                  <AlertCircleIcon size={16} />
                )}
                <span>{statusMessage.text}</span>
              </div>
            )}

            {/* Response Style Section */}
            <div className="preference-group">
              <label className="preference-label">Response Style</label>
              <p className="preference-hint">Select the default depth and verbosity of AI answers:</p>
              <div className="style-cards-grid">
                <button
                  type="button"
                  className={`style-card ${style === 'concise' ? 'selected' : ''}`}
                  onClick={() => setStyle('concise')}
                >
                  <div className="style-card-header">
                    <span className="style-title">Concise</span>
                    {style === 'concise' && <CheckIcon size={14} className="check-badge" />}
                  </div>
                  <p className="style-desc">
                    Brief, highly focused summaries with bullet points and zero unnecessary words.
                  </p>
                </button>

                <button
                  type="button"
                  className={`style-card ${style === 'balanced' ? 'selected' : ''}`}
                  onClick={() => setStyle('balanced')}
                >
                  <div className="style-card-header">
                    <span className="style-title">Balanced</span>
                    {style === 'balanced' && <CheckIcon size={14} className="check-badge" />}
                  </div>
                  <p className="style-desc">
                    Natural, conversational flow with clear explanations and proportional detail.
                  </p>
                </button>

                <button
                  type="button"
                  className={`style-card ${style === 'detailed' ? 'selected' : ''}`}
                  onClick={() => setStyle('detailed')}
                >
                  <div className="style-card-header">
                    <span className="style-title">Detailed</span>
                    {style === 'detailed' && <CheckIcon size={14} className="check-badge" />}
                  </div>
                  <p className="style-desc">
                    Deep analytical explanations with background context, nuances, and edge cases.
                  </p>
                </button>
              </div>
            </div>

            {/* Preferred Response Language */}
            <div className="preference-group">
              <label className="preference-label" htmlFor="pref-language">
                Preferred Response Language
              </label>
              <p className="preference-hint">
                The AI will formulate all explanations and analyses in this language:
              </p>
              <select
                id="pref-language"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="preference-select"
              >
                {LANGUAGES.map((lang) => (
                  <option key={lang} value={lang}>
                    {lang}
                  </option>
                ))}
              </select>
            </div>

            {/* Custom Instructions */}
            <div className="preference-group">
              <label className="preference-label" htmlFor="pref-instructions">
                Custom Instructions & Persona (Optional)
              </label>
              <p className="preference-hint">
                Provide custom instructions to append to every prompt (e.g. your role, preferred terminology, or architectural focus):
              </p>
              <textarea
                id="pref-instructions"
                rows={3}
                placeholder="e.g. I am a software engineer; prioritize TypeScript examples, explain architectural trade-offs, and omit introductory filler."
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
                className="preference-textarea"
              />
            </div>
          </div>
        )}

        <div className="preferences-footer">
          <button type="button" className="preferences-cancel-btn" onClick={onClose} disabled={isSaving}>
            Cancel
          </button>
          <button
            type="button"
            className="preferences-save-btn"
            onClick={handleSave}
            disabled={isSaving || isLoading}
          >
            {isSaving ? (
              <>
                <RefreshCwIcon size={14} className="spin-icon" />
                <span>Saving to PostgreSQL...</span>
              </>
            ) : (
              <>
                <CheckIcon size={14} />
                <span>Save Preferences</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
