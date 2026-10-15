import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { WelcomeHero } from './components/WelcomeHero';
import { MessageList } from './components/MessageList';
import { MessageInput } from './components/MessageInput';
import type { Message, ChatSession, ChatApiResponse } from './types/chat';

const SESSIONS_STORAGE_KEY = 'aethermind_sessions_v1';
const ACTIVE_SESSION_STORAGE_KEY = 'aethermind_active_session_v1';

export const App: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sessions, setSessions] = useState<ChatSession[]>(() => {
    try {
      const saved = localStorage.getItem(SESSIONS_STORAGE_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [activeSessionId, setActiveSessionId] = useState<string | null>(() => {
    try {
      return localStorage.getItem(ACTIVE_SESSION_STORAGE_KEY) || null;
    } catch {
      return null;
    }
  });

  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Sync active session messages
  useEffect(() => {
    if (activeSessionId) {
      const current = sessions.find((s) => s.id === activeSessionId);
      if (current && current.messages) {
        setMessages(current.messages);
      } else {
        setMessages([]);
      }
    } else {
      setMessages([]);
    }
  }, [activeSessionId]);

  // Persist sessions to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(SESSIONS_STORAGE_KEY, JSON.stringify(sessions));
    } catch (e) {
      console.error('Failed to save sessions:', e);
    }
  }, [sessions]);

  // Persist activeSessionId to localStorage
  useEffect(() => {
    try {
      if (activeSessionId) {
        localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, activeSessionId);
      } else {
        localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
      }
    } catch (e) {
      console.error('Failed to save activeSessionId:', e);
    }
  }, [activeSessionId]);

  const getFormattedTime = () => {
    return new Date().toLocaleTimeString([], {
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  const callChatBackend = async (
    text: string,
    sessionId?: string | null
  ): Promise<ChatApiResponse> => {
    const payload = JSON.stringify({
      message: text,
      session_id: sessionId || null,
    });

    const headers = { 'Content-Type': 'application/json' };

    // Try relative endpoint via Vite proxy first
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers,
        body: payload,
      });
      if (res.ok) {
        return await res.json();
      }
    } catch {
      // Fallback to direct backend URL if proxy is unavailable
    }

    // Direct fallback to FastAPI on port 8000
    const directRes = await fetch('http://127.0.0.1:8000/api/chat', {
      method: 'POST',
      headers,
      body: payload,
    });

    if (!directRes.ok) {
      const errText = await directRes.text().catch(() => '');
      throw new Error(`Server returned HTTP ${directRes.status}: ${errText}`);
    }

    return await directRes.json();
  };

  const handleSendMessage = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isLoading) return;

    setErrorMessage(null);

    const userTime = getFormattedTime();
    const userMsg: Message = {
      id: `msg-user-${Date.now()}`,
      sender: 'user',
      content: trimmed,
      timestamp: userTime,
    };

    let currentSessionId = activeSessionId;
    if (!currentSessionId) {
      currentSessionId = `session-${Date.now()}`;
      const sessionTitle = trimmed.length > 28 ? `${trimmed.slice(0, 28)}...` : trimmed;
      const newSession: ChatSession = {
        id: currentSessionId,
        title: sessionTitle,
        lastUpdated: 'Just now',
        messages: [userMsg],
      };
      setSessions((prev) => [newSession, ...prev]);
      setActiveSessionId(currentSessionId);
      setMessages([userMsg]);
    } else {
      setMessages((prev) => [...prev, userMsg]);
      setSessions((prev) =>
        prev.map((s) =>
          s.id === currentSessionId
            ? {
                ...s,
                lastUpdated: 'Just now',
                messages: [...(s.messages || []), userMsg],
              }
            : s
        )
      );
    }

    setIsLoading(true);

    try {
      const data = await callChatBackend(trimmed, currentSessionId);

      const assistantMsg: Message = {
        id: `msg-assistant-${Date.now()}`,
        sender: 'assistant',
        content: data.reply,
        timestamp: data.timestamp || getFormattedTime(),
      };

      setMessages((prev) => [...prev, assistantMsg]);
      setSessions((prev) =>
        prev.map((s) =>
          s.id === currentSessionId
            ? {
                ...s,
                lastUpdated: 'Just now',
                messages: [...(s.messages || []), assistantMsg],
              }
            : s
        )
      );
    } catch (err: unknown) {
      const errDetail = err instanceof Error ? err.message : 'Connection failed';
      setErrorMessage(`Unable to reach backend: ${errDetail}`);

      const errorMsg: Message = {
        id: `msg-err-${Date.now()}`,
        sender: 'assistant',
        content: `⚠️ Failed to get response from backend: ${errDetail}. Please verify that the FastAPI backend is running at http://127.0.0.1:8000.`,
        timestamp: getFormattedTime(),
        isError: true,
      };

      setMessages((prev) => [...prev, errorMsg]);
      setSessions((prev) =>
        prev.map((s) =>
          s.id === currentSessionId
            ? {
                ...s,
                messages: [...(s.messages || []), errorMsg],
              }
            : s
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewChat = () => {
    setActiveSessionId(null);
    setMessages([]);
    setErrorMessage(null);
    setSidebarOpen(false);
  };

  const handleSelectSession = async (id: string) => {
    setActiveSessionId(id);
    setErrorMessage(null);
    const target = sessions.find((s) => s.id === id);
    if (target && target.messages) {
      setMessages(target.messages);
    } else {
      setMessages([]);
    }
    setSidebarOpen(false);

    // Retrieve saved conversation messages from PostgreSQL backend if available
    try {
      const res = await fetch(`/api/conversations/${encodeURIComponent(id)}/messages`);
      if (res.ok) {
        const data = await res.json();
        if (data.messages && Array.isArray(data.messages)) {
          const mapped: Message[] = data.messages.map((m: { id: number; role?: string; sender?: string; content: string; timestamp: string }) => ({
            id: `db-${m.id}`,
            sender: (m.role === 'user' || m.sender === 'user') ? 'user' : 'assistant',
            content: m.content,
            timestamp: m.timestamp,
          }));
          setMessages(mapped);
          setSessions((prev) =>
            prev.map((s) => (s.id === id ? { ...s, messages: mapped } : s))
          );
        }
      }
    } catch {
      // Graceful fallback to existing session state if database is offline
    }
  };

  const handleDeleteSession = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const updated = sessions.filter((s) => s.id !== id);
    setSessions(updated);

    // Attempt to delete from PostgreSQL in background
    fetch(`/api/conversations/${encodeURIComponent(id)}`, { method: 'DELETE' }).catch(() => {});

    if (activeSessionId === id) {
      setActiveSessionId(null);
      setMessages([]);
      setErrorMessage(null);
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    setErrorMessage(null);
    if (activeSessionId) {
      setSessions((prev) =>
        prev.map((s) => (s.id === activeSessionId ? { ...s, messages: [] } : s))
      );
    }
  };

  const activeSession = sessions.find((s) => s.id === activeSessionId);
  const activeChatTitle = activeSession ? activeSession.title : undefined;

  return (
    <div className="app-container">
      {/* Navigation Sidebar */}
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onDeleteSession={handleDeleteSession}
      />

      {/* Main Conversation Canvas */}
      <main className="main-chat-area">
        <Header
          onToggleSidebar={() => setSidebarOpen((prev) => !prev)}
          onClearChat={handleClearChat}
          hasMessages={messages.length > 0}
          activeChatTitle={activeChatTitle}
        />

        {errorMessage && (
          <div className="error-banner">
            <span>{errorMessage}</span>
            <button
              onClick={() => setErrorMessage(null)}
              className="error-dismiss-btn"
              aria-label="Dismiss error notification"
            >
              ×
            </button>
          </div>
        )}

        {messages.length === 0 ? (
          <WelcomeHero onSelectPrompt={handleSendMessage} />
        ) : (
          <MessageList messages={messages} isGenerating={isLoading} />
        )}

        <MessageInput
          onSendMessage={handleSendMessage}
          disabled={isLoading}
        />
      </main>
    </div>
  );
};

export default App;
