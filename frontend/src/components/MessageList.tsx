import React, { useEffect, useRef, useState } from 'react';
import type { Message } from '../types/chat';
import { UserIcon, SparklesIcon, FileTextIcon, TableIcon, CopyIcon, CheckIcon } from './Icons';
import { FormattedContent } from './FormattedContent';

interface MessageListProps {
  messages: Message[];
  isGenerating?: boolean;
}

function formatBytes(bytes?: number): string {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export const MessageList: React.FC<MessageListProps> = ({ messages, isGenerating = false }) => {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isGenerating]);

  const handleCopyMessage = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="messages-container">
      <div className="messages-inner">
        {messages.map((msg) => {
          const isUser = msg.sender === 'user';

          return (
            <div
              key={msg.id}
              className={`message-row ${isUser ? 'user-row' : 'assistant-row'} ${
                msg.isError ? 'error-row' : ''
              }`}
            >
              <div className="message-avatar">
                {isUser ? (
                  <div className="avatar-icon user-avatar">
                    <UserIcon size={16} />
                  </div>
                ) : (
                  <div className="avatar-icon assistant-avatar">
                    <SparklesIcon size={16} />
                  </div>
                )}
              </div>

              <div className="message-bubble-wrapper">
                <div className="message-meta">
                  <span className="sender-name">
                    {isUser ? 'You' : 'AetherMind'}
                  </span>
                  {!isUser && <span className="message-model-tag">Gemini 2.5</span>}
                  <span className="message-time">{msg.timestamp}</span>
                </div>

                <div className={`message-bubble ${msg.isError ? 'error-bubble' : ''}`}>
                  {/* Render attachments attached to this message */}
                  {msg.attachments && msg.attachments.length > 0 && (
                    <div className="message-attachments-container">
                      {msg.attachments.map((att) => (
                        <div key={att.id} className="message-attachment-chip">
                          {att.previewUrl ? (
                            <div className="message-att-preview-wrap">
                              <img
                                src={att.previewUrl}
                                alt={att.name}
                                className="message-att-preview-img"
                              />
                            </div>
                          ) : (
                            <div className="message-att-icon-wrap">
                              {att.type === 'csv' ? (
                                <TableIcon size={16} />
                              ) : (
                                <FileTextIcon size={16} />
                              )}
                            </div>
                          )}
                          <div className="message-att-info">
                            <span className="message-att-name" title={att.name}>
                              {att.name}
                            </span>
                            <span className="message-att-size">
                              {att.type.toUpperCase()}
                              {att.size ? ` • ${formatBytes(att.size)}` : ''}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {isUser ? (
                    <div className="message-text">{msg.content}</div>
                  ) : (
                    <>
                      <FormattedContent content={msg.content} />
                      <div className="assistant-msg-actions">
                        <button
                          type="button"
                          className="msg-action-copy-btn"
                          onClick={() => handleCopyMessage(msg.id, msg.content)}
                          title="Copy response"
                        >
                          {copiedId === msg.id ? (
                            <>
                              <CheckIcon size={13} className="action-check-icon" />
                              <span>Copied</span>
                            </>
                          ) : (
                            <>
                              <CopyIcon size={13} />
                              <span>Copy</span>
                            </>
                          )}
                        </button>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {/* Thinking / Generating Indicator */}
        {isGenerating && (
          <div className="message-row assistant-row typing-row">
            <div className="message-avatar">
              <div className="avatar-icon assistant-avatar thinking-avatar">
                <SparklesIcon size={16} />
              </div>
            </div>

            <div className="message-bubble-wrapper">
              <div className="message-meta">
                <span className="sender-name">AetherMind</span>
                <span className="thinking-tag">Thinking...</span>
              </div>

              <div className="message-bubble typing-bubble">
                <div className="typing-dots">
                  <span className="typing-dot"></span>
                  <span className="typing-dot"></span>
                  <span className="typing-dot"></span>
                </div>
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
};
