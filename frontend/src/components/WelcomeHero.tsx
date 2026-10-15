import React from 'react';
import { SparklesIcon, LightbulbIcon, CompassIcon, CodeIcon, BookOpenIcon } from './Icons';

interface WelcomeHeroProps {
  onSelectPrompt: (promptText: string) => void;
}

export const WelcomeHero: React.FC<WelcomeHeroProps> = ({ onSelectPrompt }) => {
  const suggestions = [
    {
      category: 'BRAINSTORMING',
      icon: <LightbulbIcon size={18} />,
      title: 'Architectural Ideation',
      description: 'Develop high-performance architectures & scalable patterns',
      prompt: 'Help me brainstorm ideas for designing a high-performance conversational AI architecture.',
      colorClass: 'card-amber',
    },
    {
      category: 'EXPLORATION',
      icon: <CompassIcon size={18} />,
      title: 'Deep Knowledge Synthesis',
      description: 'Explain vector embeddings, cosine distance, and RAG retrieval',
      prompt: 'Explain how vector embeddings and retrieval-augmented generation work together.',
      colorClass: 'card-cyan',
    },
    {
      category: 'ENGINEERING',
      icon: <CodeIcon size={18} />,
      title: 'Asynchronous APIs',
      description: 'Write, review, and optimize clean FastAPI endpoints with async handlers',
      prompt: 'What are the best practices for structuring asynchronous APIs in FastAPI?',
      colorClass: 'card-violet',
    },
    {
      category: 'DOCUMENT INTELLIGENCE',
      icon: <BookOpenIcon size={18} />,
      title: 'Document Analysis & Q&A',
      description: 'Extract tables from CSV, analyze PDFs, and summarize key takeaways',
      prompt: 'Summarize the attached document and extract key takeaways with data points.',
      colorClass: 'card-emerald',
    },
  ];

  return (
    <div className="welcome-hero-v2">
      <div className="hero-top-badge">
        <span className="hero-badge-dot"></span>
        <span className="hero-badge-text">AetherMind v2.5 • Multi-Modal Intelligence Engine</span>
      </div>

      <div className="hero-main-banner">
        <div className="hero-emblem-v2">
          <SparklesIcon size={24} className="hero-sparkle-v2" />
        </div>
        <div className="hero-headings-v2">
          <h1 className="hero-title-v2">
            What will we <span className="hero-gradient-text">create & discover</span> today?
          </h1>
          <p className="hero-subtitle-v2">
            Your high-precision AI workspace for multi-turn conversations, full-fidelity document extraction,
            and instant knowledge synthesis powered by Gemini.
          </p>
        </div>
      </div>

      <div className="hero-capabilities-bar">
        <span className="cap-tag"><span className="cap-dot dot-pdf"></span>PDF & DOCX RAG</span>
        <span className="cap-tag"><span className="cap-dot dot-csv"></span>CSV Data Extraction</span>
        <span className="cap-tag"><span className="cap-dot dot-pdf-gen"></span>ReportLab PDF Export</span>
        <span className="cap-tag"><span className="cap-dot dot-pg"></span>Neon PostgreSQL Storage</span>
      </div>

      <div className="suggestions-grid-v2">
        {suggestions.map((item, idx) => (
          <button
            key={idx}
            className={`suggestion-card-v2 ${item.colorClass}`}
            onClick={() => onSelectPrompt(item.prompt)}
            type="button"
          >
            <div className="card-top-row">
              <span className="card-category-tag">{item.category}</span>
              <div className="card-icon-bubble">{item.icon}</div>
            </div>
            <div className="card-content-body">
              <h3 className="card-item-title">{item.title}</h3>
              <p className="card-item-desc">{item.description}</p>
            </div>
            <div className="card-footer-action">
              <span className="card-action-text">Use prompt</span>
              <span className="card-action-arrow">→</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
};
