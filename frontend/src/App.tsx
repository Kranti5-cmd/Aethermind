import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { WelcomeHero } from './components/WelcomeHero';
import { MessageList } from './components/MessageList';
import { MessageInput } from './components/MessageInput';
import { DocumentsView } from './components/DocumentsView';
import { PreferencesModal } from './components/PreferencesModal';
import type { Message, ChatSession, ChatApiResponse, MessageAttachment } from './types/chat';
import type { ExtractedDocument } from './types/document';

const SESSIONS_STORAGE_KEY = 'aethermind_sessions_v1';
const ACTIVE_SESSION_STORAGE_KEY = 'aethermind_active_session_v1';
const DOCUMENTS_STORAGE_KEY = 'aethermind_documents_v1';

export const App: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [preferencesOpen, setPreferencesOpen] = useState(false);
  const [activeView, setActiveView] = useState<'chat' | 'documents'>('chat');

  // Documents state
  const [documents, setDocuments] = useState<ExtractedDocument[]>(() => {
    try {
      const saved = localStorage.getItem(DOCUMENTS_STORAGE_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [docToAttachInChat, setDocToAttachInChat] = useState<ExtractedDocument | null>(null);
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

  // Persist documents to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(DOCUMENTS_STORAGE_KEY, JSON.stringify(documents));
    } catch (e) {
      console.error('Failed to save documents:', e);
    }
  }, [documents]);

  // Load saved documents and conversation history from backend on startup
  useEffect(() => {
    const fetchBackendDocs = async () => {
      try {
        let res: Response;
        try {
          res = await fetch('/api/documents');
        } catch {
          res = await fetch('http://127.0.0.1:8000/api/documents');
        }
        if (res.ok) {
          const remoteDocs = await res.json();
          if (Array.isArray(remoteDocs) && remoteDocs.length > 0) {
            setDocuments((prev) => {
              const localMap = new Map(prev.map((d) => [d.id, d]));
              remoteDocs.forEach((rd: any) => {
                const existing = localMap.get(rd.id);
                localMap.set(rd.id, {
                  id: rd.id,
                  filename: rd.filename,
                  file_type: rd.file_type,
                  file_size: rd.file_size,
                  extracted_text: existing?.extracted_text || rd.extracted_text || '',
                  metadata: rd.metadata || existing?.metadata || {},
                  uploaded_at: rd.uploaded_at || existing?.uploaded_at || 'Recently',
                  status: 'success',
                });
              });
              return Array.from(localMap.values());
            });
          }
        }
      } catch (e) {
        // Fallback to localStorage if backend is loading
      }
    };

    const fetchBackendConversations = async () => {
      try {
        let res: Response;
        try {
          res = await fetch('/api/conversations');
        } catch {
          res = await fetch('http://127.0.0.1:8000/api/conversations');
        }
        if (res.ok) {
          const remoteConvs = await res.json();
          if (Array.isArray(remoteConvs) && remoteConvs.length > 0) {
            setSessions((prev) => {
              const localMap = new Map(prev.map((s) => [s.id, s]));
              remoteConvs.forEach((rc: { session_id: string; title: string; updated_at?: string }) => {
                const existing = localMap.get(rc.session_id);
                localMap.set(rc.session_id, {
                  id: rc.session_id,
                  title: rc.title || existing?.title || 'Conversation',
                  lastUpdated: rc.updated_at ? new Date(rc.updated_at).toLocaleDateString() : (existing?.lastUpdated || 'Recently'),
                  messages: existing?.messages || [],
                });
              });
              return Array.from(localMap.values());
            });
          }
        }
      } catch (e) {
        // Fallback to localStorage if backend is loading
      }
    };

    fetchBackendDocs();
    fetchBackendConversations();
  }, []);

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
    sessionId?: string | null,
    documentIds?: string[],
    documents?: { id?: string; name: string; type: string; extracted_text?: string; size?: number }[],
    images?: { name: string; mime_type: string; base64_data: string; size?: number }[]
  ): Promise<ChatApiResponse> => {
    const payload = JSON.stringify({
      message: text,
      session_id: sessionId || null,
      document_ids: documentIds && documentIds.length > 0 ? documentIds : null,
      documents: documents && documents.length > 0 ? documents : null,
      images: images && images.length > 0 ? images : null,
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
      if (res.status === 429) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail || '429 Rate limit or quota exceeded');
      }
    } catch (fetchErr) {
      if (fetchErr instanceof Error && fetchErr.message.includes('429')) {
        throw fetchErr;
      }
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
      let parsedDetail = errText;
      try {
        const jsonErr = JSON.parse(errText);
        parsedDetail = jsonErr.detail || errText;
      } catch {}
      throw new Error(`HTTP ${directRes.status}: ${parsedDetail}`);
    }

    return await directRes.json();
  };

  const handleSendMessage = async (
    text: string,
    attachments?: MessageAttachment[]
  ) => {
    const trimmed = text.trim();
    const hasAttachments = Boolean(attachments && attachments.length > 0);
    if ((!trimmed && !hasAttachments) || isLoading) return;

    setErrorMessage(null);

    const userTime = getFormattedTime();
    let displayContent = trimmed;
    if (!displayContent && hasAttachments) {
      const names = attachments!.map((a) => a.name).join(', ');
      displayContent = `Attached: ${names}`;
    }

    const userMsg: Message = {
      id: `msg-user-${Date.now()}`,
      sender: 'user',
      content: displayContent,
      timestamp: userTime,
      attachments: attachments,
    };

    let currentSessionId = activeSessionId;
    if (!currentSessionId) {
      currentSessionId = `session-${Date.now()}`;
      const sessionTitle =
        displayContent.length > 28 ? `${displayContent.slice(0, 28)}...` : displayContent;
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
      // Document IDs from PostgreSQL Document Intelligence
      const documentIds = attachments
        ?.filter((a) => a.type !== 'image' && a.documentId)
        .map((a) => a.documentId!);

      const docPayload = attachments
        ?.filter((a) => a.type !== 'image' && a.status === 'ready')
        .map((a) => ({
          id: a.documentId,
          name: a.name,
          type: a.type,
          extracted_text: a.extractedText || '',
          size: a.size,
        }));

      const imgPayload = attachments
        ?.filter((a) => a.type === 'image' && a.status === 'ready' && a.base64Data)
        .map((a) => ({
          name: a.name,
          mime_type: a.mimeType || 'image/png',
          base64_data: a.base64Data!,
          size: a.size,
        }));

      const data = await callChatBackend(
        trimmed,
        currentSessionId,
        documentIds,
        docPayload,
        imgPayload
      );

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
      const isQuota =
        errDetail.includes('429') ||
        errDetail.toLowerCase().includes('quota') ||
        errDetail.includes('RESOURCE_EXHAUSTED');

      let userFacingError = `⚠️ Failed to get response from backend: ${errDetail}. Please verify that the FastAPI backend is running at http://127.0.0.1:8000.`;

      if (isQuota) {
        userFacingError =
          '⚠️ Google Gemini API quota or rate limit has been temporarily reached. Please wait a moment before sending another message, or verify your API quota at https://ai.google.dev. Your conversation and attachments remain safely preserved.';
        setErrorMessage('Gemini API quota exceeded. Please wait a moment before retrying.');
      } else {
        setErrorMessage(`Unable to reach backend: ${errDetail}`);
      }

      const errorMsg: Message = {
        id: `msg-err-${Date.now()}`,
        sender: 'assistant',
        content: userFacingError,
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
    setActiveView('chat');
    setActiveSessionId(null);
    setMessages([]);
    setErrorMessage(null);
    setSidebarOpen(false);
  };

  const handleSelectSession = async (id: string) => {
    setActiveView('chat');
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

  const handleAddDocument = (doc: ExtractedDocument) => {
    setDocuments((prev) => [doc, ...prev]);
    setSelectedDocId(doc.id);
  };

  const handleDeleteDocument = (id: string) => {
    setDocuments((prev) => prev.filter((d) => d.id !== id));
    if (selectedDocId === id) {
      setSelectedDocId(null);
    }
    // Delete from PostgreSQL backend in background
    fetch(`/api/documents/${encodeURIComponent(id)}`, { method: 'DELETE' }).catch(() => {});
  };

  const handleChatWithDocument = (doc: ExtractedDocument) => {
    setDocToAttachInChat(doc);
    setActiveView('chat');
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
        activeView={activeView}
        onSelectView={(view) => {
          setActiveView(view);
          setSidebarOpen(false);
        }}
        documentCount={documents.length}
        onOpenPreferences={() => setPreferencesOpen(true)}
      />

      {/* Main Conversation or Document Area */}
      <main className="main-chat-area">
        <Header
          onToggleSidebar={() => setSidebarOpen((prev) => !prev)}
          onClearChat={handleClearChat}
          onNewChat={handleNewChat}
          hasMessages={messages.length > 0}
          activeChatTitle={activeChatTitle}
          activeView={activeView}
          onOpenPreferences={() => setPreferencesOpen(true)}
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

        {activeView === 'documents' ? (
          <DocumentsView
            documents={documents}
            onAddDocument={handleAddDocument}
            onDeleteDocument={handleDeleteDocument}
            selectedDocId={selectedDocId}
            onSelectDoc={setSelectedDocId}
            onChatWithDocument={handleChatWithDocument}
          />
        ) : (
          <>
            {messages.length === 0 ? (
              <WelcomeHero onSelectPrompt={handleSendMessage} />
            ) : (
              <MessageList messages={messages} isGenerating={isLoading} />
            )}

            <MessageInput
              onSendMessage={handleSendMessage}
              disabled={isLoading}
              availableDocuments={documents}
              onDocumentUploaded={handleAddDocument}
              initialDocument={docToAttachInChat}
              onClearInitialDocument={() => setDocToAttachInChat(null)}
            />
          </>
        )}
      </main>

      {/* Module 5: Personalized Preferences Modal */}
      <PreferencesModal
        isOpen={preferencesOpen}
        onClose={() => setPreferencesOpen(false)}
      />
    </div>
  );
};

export default App;
