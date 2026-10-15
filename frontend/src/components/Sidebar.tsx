import React, { useState, useMemo, useEffect } from 'react';
import {
  PlusIcon,
  MessageSquareIcon,
  SparklesIcon,
  CloseIcon,
  TrashIcon,
  FileTextIcon,
  SearchIcon,
  SettingsIcon,
  UserIcon,
  BotIcon,
} from './Icons';
import type { ChatSession } from '../types/chat';

export interface SearchMatchItem {
  conversation_id: number;
  session_id: string;
  conversation_title: string;
  updated_at?: string | null;
  matched_in: 'title' | 'message';
  snippet?: string | null;
  role?: string | null;
  timestamp?: string | null;
}

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  sessions: ChatSession[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  onDeleteSession: (id: string, e: React.MouseEvent) => void;
  activeView: 'chat' | 'documents';
  onSelectView: (view: 'chat' | 'documents') => void;
  documentCount?: number;
  onOpenPreferences: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onClose,
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  activeView,
  onSelectView,
  documentCount = 0,
  onOpenPreferences,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchMatchItem[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  // Debounced search query to backend PostgreSQL database
  useEffect(() => {
    const q = searchQuery.trim();
    if (!q) {
      setSearchResults([]);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    const timer = setTimeout(async () => {
      try {
        let res: Response;
        try {
          res = await fetch(`/api/conversations/search?q=${encodeURIComponent(q)}`);
        } catch {
          res = await fetch(`http://127.0.0.1:8000/api/conversations/search?q=${encodeURIComponent(q)}`);
        }
        if (res.ok) {
          const data = await res.json();
          setSearchResults(data.results || []);
        } else {
          setSearchResults([]);
        }
      } catch (err) {
        console.warn('Backend search request failed:', err);
        setSearchResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 280);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  const filteredLocalSessions = useMemo(() => {
    if (!searchQuery.trim()) return sessions;
    const q = searchQuery.toLowerCase().trim();
    return sessions.filter((s) => s.title.toLowerCase().includes(q));
  }, [sessions, searchQuery]);

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
              <SparklesIcon size={18} className="brand-logo-icon" />
            </div>
            <div className="brand-text">
              <div className="brand-title-wrap">
                <span className="brand-name">AetherMind</span>
                <span className="brand-badge-pill">PRO</span>
              </div>
              <span className="brand-tag">Intelligence Studio</span>
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

        {/* View Switcher: Chat vs Documents */}
        <div className="sidebar-nav-switcher">
          <button
            className={`nav-tab-btn ${activeView === 'chat' ? 'active' : ''}`}
            onClick={() => onSelectView('chat')}
          >
            <MessageSquareIcon size={15} />
            <span>AI Chat</span>
          </button>
          <button
            className={`nav-tab-btn ${activeView === 'documents' ? 'active' : ''}`}
            onClick={() => onSelectView('documents')}
          >
            <FileTextIcon size={15} />
            <span>Documents</span>
            {documentCount > 0 && <span className="nav-count-badge">{documentCount}</span>}
          </button>
        </div>

        {/* New Chat Action */}
        {activeView === 'chat' && (
          <div className="sidebar-action">
            <button 
              className="new-chat-btn"
              onClick={() => {
                onNewChat();
                setSearchQuery('');
              }}
            >
              <div className="new-chat-left">
                <PlusIcon size={16} />
                <span>New Conversation</span>
              </div>
              <span className="new-chat-kbd">⌘K</span>
            </button>
          </div>
        )}

        {/* Search Conversations Input */}
        {activeView === 'chat' && (sessions.length > 0 || searchQuery) && (
          <div className="sidebar-search-box">
            <SearchIcon size={14} className="sidebar-search-icon" />
            <input
              type="text"
              placeholder="Search chats & messages..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="sidebar-search-input"
              aria-label="Search conversation history and message contents"
            />
            {searchQuery ? (
              <button
                className="search-clear-btn"
                onClick={() => setSearchQuery('')}
                aria-label="Clear search"
                type="button"
              >
                ×
              </button>
            ) : (
              <span className="search-hint-kbd">/</span>
            )}
          </div>
        )}

        {/* Recent Conversations / Search Results List */}
        <div className="sidebar-content">
          <div className="sessions-header">
            <span>
              {searchQuery
                ? `Search Results (${searchResults.length || filteredLocalSessions.length})`
                : 'Recent Conversations'}
            </span>
          </div>

          <div className="sessions-list">
            {searchQuery.trim() ? (
              // Display Search Results (with snippets if from backend search)
              searchResults.length > 0 ? (
                searchResults.map((item, idx) => (
                  <div
                    key={`search-${item.session_id}-${idx}`}
                    className={`session-search-item ${item.session_id === activeSessionId ? 'active' : ''}`}
                    onClick={() => {
                      onSelectSession(item.session_id);
                    }}
                  >
                    <div className="search-item-header">
                      <MessageSquareIcon size={14} className="session-icon" />
                      <span className="session-title" title={item.conversation_title}>
                        {item.conversation_title}
                      </span>
                    </div>
                    {item.matched_in === 'message' && item.snippet && (
                      <div className="search-item-snippet">
                        <span className="snippet-role-tag">
                          {item.role === 'user' ? (
                            <><UserIcon size={11} /> You:</>
                          ) : (
                            <><BotIcon size={11} /> AI:</>
                          )}
                        </span>
                        <span className="snippet-text">"{item.snippet}"</span>
                      </div>
                    )}
                  </div>
                ))
              ) : filteredLocalSessions.length > 0 ? (
                // Fallback to local session matches if backend returned empty
                filteredLocalSessions.map((session) => (
                  <div
                    key={session.id}
                    className={`session-item ${session.id === activeSessionId ? 'active' : ''}`}
                    onClick={() => onSelectSession(session.id)}
                  >
                    <MessageSquareIcon size={15} className="session-icon" />
                    <span className="session-title" title={session.title}>
                      {session.title}
                    </span>
                    <button
                      className="delete-session-btn"
                      onClick={(e) => onDeleteSession(session.id, e)}
                      title="Delete chat"
                      aria-label="Delete chat"
                    >
                      <TrashIcon size={13} />
                    </button>
                  </div>
                ))
              ) : isSearching ? (
                <div className="empty-sessions">
                  <p>Searching PostgreSQL database...</p>
                </div>
              ) : (
                <div className="empty-sessions">
                  <MessageSquareIcon size={24} className="empty-icon" />
                  <p>No matching messages found</p>
                  <span>Try searching for another keyword or topic</span>
                </div>
              )
            ) : filteredLocalSessions.length === 0 ? (
              <div className="empty-sessions">
                <MessageSquareIcon size={24} className="empty-icon" />
                <p>No conversation history</p>
                <span>Start a chat to save your session</span>
              </div>
            ) : (
              filteredLocalSessions.map((session) => (
                <div
                  key={session.id}
                  className={`session-item ${session.id === activeSessionId ? 'active' : ''}`}
                  onClick={() => onSelectSession(session.id)}
                >
                  <MessageSquareIcon size={15} className="session-icon" />
                  <span className="session-title" title={session.title}>
                    {session.title}
                  </span>
                  <button
                    className="delete-session-btn"
                    onClick={(e) => onDeleteSession(session.id, e)}
                    title="Delete chat"
                    aria-label="Delete chat"
                  >
                    <TrashIcon size={13} />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Sidebar Footer with Engine & DB Status + Preferences */}
        <div className="sidebar-footer">
          <button
            className="sidebar-preferences-btn"
            onClick={onOpenPreferences}
            title="Configure AI response style & language preferences"
          >
            <SettingsIcon size={15} />
            <span>AI Preferences</span>
          </button>

          <div className="status-badge">
            <span className="status-dot"></span>
            <div className="status-text-group">
              <span className="status-title">System Ready</span>
              <span className="status-subtitle">Gemini 2.5 • Neon PostgreSQL</span>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
};
