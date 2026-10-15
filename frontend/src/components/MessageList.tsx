import React, { useEffect, useRef } from 'react';
import type { Message } from '../types/chat';
import { UserIcon, SparklesIcon } from './Icons';
import { FormattedContent } from './FormattedContent';

interface MessageListProps {
  messages: Message[];
  isGenerating?: boolean;
}

export const MessageList: React.FC<MessageListProps> = ({ messages, isGenerating = false }) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isGenerating]);

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
                  <span className="message-time">{msg.timestamp}</span>
                </div>

                <div className={`message-bubble ${msg.isError ? 'error-bubble' : ''}`}>
                  {isUser ? (
                    <div className="message-text">{msg.content}</div>
                  ) : (
                    <FormattedContent content={msg.content} />
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
