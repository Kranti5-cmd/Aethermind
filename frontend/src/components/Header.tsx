import React from 'react';
import { MenuIcon, SparklesIcon, TrashIcon, FileTextIcon, PlusIcon, SettingsIcon } from './Icons';

interface HeaderProps {
  onToggleSidebar: () => void;
  onClearChat: () => void;
  onNewChat?: () => void;
  hasMessages: boolean;
  activeChatTitle?: string;
  activeView?: 'chat' | 'documents';
  onOpenPreferences?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  onToggleSidebar,
  onClearChat,
  onNewChat,
  hasMessages,
  activeChatTitle,
  activeView = 'chat',
  onOpenPreferences,
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
            {activeView === 'documents' ? (
              <FileTextIcon size={16} />
            ) : (
              <SparklesIcon size={16} />
            )}
          </div>
          <div className="header-title-group">
            <h1 className="header-title">
              {activeView === 'documents'
                ? 'Document Intelligence Studio'
                : activeChatTitle || 'AetherMind Assistant'}
            </h1>
            <span className="header-model-pill">
              {activeView === 'documents' ? 'Module 2: Ingestion' : 'Gemini 2.5'}
            </span>
          </div>
        </div>
      </div>

      <div className="header-right">
        <div className="header-status-indicator" title="Connected to FastAPI & Gemini Engine">
          <span className="status-dot" />
          <span className="status-label">Engine Online</span>
        </div>

        {onOpenPreferences && (
          <button
            className="header-action-btn"
            onClick={onOpenPreferences}
            title="Configure AI preferences & response style"
          >
            <SettingsIcon size={15} />
            <span className="btn-label">Preferences</span>
          </button>
        )}

        {activeView === 'chat' && onNewChat && (
          <button
            className="header-new-chat-btn"
            onClick={onNewChat}
            title="Start a new chat session"
          >
            <PlusIcon size={14} />
            <span className="btn-label">New Chat</span>
          </button>
        )}

        {activeView === 'chat' && hasMessages && (
          <button
            className="header-action-btn"
            onClick={onClearChat}
            title="Clear current conversation"
          >
            <TrashIcon size={15} />
            <span className="btn-label">Clear</span>
          </button>
        )}
      </div>
    </header>
  );
};

