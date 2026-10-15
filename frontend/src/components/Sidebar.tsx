import React from 'react';
import { PlusIcon, MessageSquareIcon, SparklesIcon, CloseIcon, TrashIcon } from './Icons';
import type { ChatSession } from '../types/chat';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  sessions: ChatSession[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  onDeleteSession: (id: string, e: React.MouseEvent) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onClose,
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
}) => {
  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div 
          className="sidebar-backdrop" 
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
        {/* Brand Header */}
        <div className="sidebar-header">
          <div className="brand-container">
            <div className="brand-logo">
              <SparklesIcon size={20} className="brand-logo-icon" />
            </div>
            <div className="brand-text">
              <span className="brand-name">AetherMind</span>
              <span className="brand-tag">Assistant</span>
            </div>
          </div>
          <button 
            className="mobile-close-btn"
            onClick={onClose}
            aria-label="Close sidebar"
          >
            <CloseIcon size={18} />
          </button>
        </div>

        {/* New Chat Action */}
        <div className="sidebar-action">
          <button 
            className="new-chat-btn"
            onClick={onNewChat}
          >
            <PlusIcon size={18} />
            <span>New Chat</span>
          </button>
        </div>

        {/* Recent Conversations List */}
        <div className="sidebar-content">
          <div className="sessions-header">
            <span>Recent Conversations</span>
          </div>

          <div className="sessions-list">
            {sessions.length === 0 ? (
              <div className="empty-sessions">
                <MessageSquareIcon size={24} className="empty-icon" />
                <p>No chat history yet</p>
                <span>Start a new conversation to see it here</span>
              </div>
            ) : (
              sessions.map((session) => (
                <div
                  key={session.id}
                  className={`session-item ${session.id === activeSessionId ? 'active' : ''}`}
                  onClick={() => onSelectSession(session.id)}
                >
                  <MessageSquareIcon size={16} className="session-icon" />
                  <span className="session-title" title={session.title}>
                    {session.title}
                  </span>
                  <button
                    className="delete-session-btn"
                    onClick={(e) => onDeleteSession(session.id, e)}
                    title="Delete chat"
                    aria-label="Delete chat"
                  >
                    <TrashIcon size={14} />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Sidebar Footer with Status */}
        <div className="sidebar-footer">
          <div className="status-badge">
            <span className="status-dot"></span>
            <span className="status-text">Ready to Assist</span>
          </div>
        </div>
      </aside>
    </>
  );
};
