import React from 'react';
import { MenuIcon, SparklesIcon, TrashIcon } from './Icons';

interface HeaderProps {
  onToggleSidebar: () => void;
  onClearChat: () => void;
  hasMessages: boolean;
  activeChatTitle?: string;
}

export const Header: React.FC<HeaderProps> = ({
  onToggleSidebar,
  onClearChat,
  hasMessages,
  activeChatTitle,
}) => {
  return (
    <header className="chat-header">
      <div className="header-left">
        <button
          className="menu-toggle-btn"
          onClick={onToggleSidebar}
          aria-label="Toggle navigation menu"
        >
          <MenuIcon size={20} />
        </button>

        <div className="header-brand">
          <div className="header-logo-badge">
            <SparklesIcon size={16} />
          </div>
          <div className="header-title-group">
            <h1 className="header-title">
              {activeChatTitle || 'AetherMind'}
            </h1>
            <span className="header-model-pill">Knowledge Engine</span>
          </div>
        </div>
      </div>

      <div className="header-right">
        {hasMessages && (
          <button
            className="header-action-btn"
            onClick={onClearChat}
            title="Clear current conversation"
          >
            <TrashIcon size={16} />
            <span className="btn-label">Clear Chat</span>
          </button>
        )}
      </div>
    </header>
  );
};
