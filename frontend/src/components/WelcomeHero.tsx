import React from 'react';
import { SparklesIcon, LightbulbIcon, CompassIcon, CodeIcon, BookOpenIcon } from './Icons';

interface WelcomeHeroProps {
  onSelectPrompt: (promptText: string) => void;
}

export const WelcomeHero: React.FC<WelcomeHeroProps> = ({ onSelectPrompt }) => {
  const suggestions = [
    {
      icon: <LightbulbIcon size={20} />,
      title: 'Brainstorm Solutions',
      description: 'Develop innovative approaches for architectural challenges',
      prompt: 'Help me brainstorm ideas for designing a high-performance conversational AI architecture.',
    },
    {
      icon: <CompassIcon size={20} />,
      title: 'Explore Knowledge',
      description: 'Break down complex subjects into intuitive explanations',
      prompt: 'Explain how vector embeddings and retrieval-augmented generation work together.',
    },
    {
      icon: <CodeIcon size={20} />,
      title: 'Code & Debugging',
      description: 'Write, review, or optimize clean code and algorithms',
      prompt: 'What are the best practices for structuring asynchronous APIs in FastAPI?',
    },
    {
      icon: <BookOpenIcon size={20} />,
      title: 'Research & Synthesis',
      description: 'Summarize documents and distill actionable takeaways',
      prompt: 'How can I structure a personal knowledge assistant to organize my research papers?',
    },
  ];

  return (
    <div className="welcome-hero">
      <div className="hero-emblem-wrapper">
        <div className="hero-emblem-glow"></div>
        <div className="hero-emblem">
          <SparklesIcon size={38} className="hero-sparkle" />
        </div>
      </div>

      <div className="hero-headings">
        <h2 className="hero-title">
          Where would you like to begin with <span className="gradient-text">AetherMind</span>?
        </h2>
        <p className="hero-subtitle">
          Your personal knowledge assistant and intelligent conversation partner. 
          Ask questions, brainstorm strategies, or explore complex topics effortlessly.
        </p>
      </div>

      <div className="suggestions-grid">
        {suggestions.map((item, idx) => (
          <button
            key={idx}
            className="suggestion-card"
            onClick={() => onSelectPrompt(item.prompt)}
          >
            <div className="suggestion-icon-wrap">
              {item.icon}
            </div>
            <div className="suggestion-text">
              <span className="suggestion-title">{item.title}</span>
              <span className="suggestion-desc">{item.description}</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
};
