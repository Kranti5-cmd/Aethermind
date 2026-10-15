import React, { useState } from 'react';
import { CopyIcon, CheckIcon } from './Icons';

interface FormattedContentProps {
  content: string;
}

export const FormattedContent: React.FC<FormattedContentProps> = ({ content }) => {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const handleCopy = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => {
      setCopiedIndex((prev) => (prev === index ? null : prev));
    }, 2000);
  };

  // Split by code blocks: ```lang ... ```
  const parts = content.split(/(```[\s\S]*?```)/g);

  const renderInlineFormatted = (text: string) => {
    // Process headers
    const lines = text.split('\n');
    return lines.map((line, lineIdx) => {
      if (line.startsWith('### ')) {
        return (
          <h3 key={lineIdx} className="content-h3">
            {renderInlineSpans(line.replace('### ', ''))}
          </h3>
        );
      }
      if (line.startsWith('#### ')) {
        return (
          <h4 key={lineIdx} className="content-h4">
            {renderInlineSpans(line.replace('#### ', ''))}
          </h4>
        );
      }
      if (line.startsWith('- ') || line.startsWith('* ')) {
        return (
          <div key={lineIdx} className="content-bullet">
            <span className="bullet-dot">•</span>
            <span>{renderInlineSpans(line.substring(2))}</span>
          </div>
        );
      }
      // Numbered list item
      const numMatch = line.match(/^(\d+\.)\s+(.*)$/);
      if (numMatch) {
        return (
          <div key={lineIdx} className="content-bullet">
            <span className="bullet-num">{numMatch[1]}</span>
            <span>{renderInlineSpans(numMatch[2])}</span>
          </div>
        );
      }
      if (!line.trim()) {
        return <div key={lineIdx} className="content-space" />;
      }
      return (
        <p key={lineIdx} className="content-p">
          {renderInlineSpans(line)}
        </p>
      );
    });
  };

  const renderInlineSpans = (text: string) => {
    // Matches **bold** and `code`
    const regex = /(\*\*.*?\*\*|`.*?`)/g;
    const tokens = text.split(regex);

    return tokens.map((token, idx) => {
      if (token.startsWith('**') && token.endsWith('**')) {
        return <strong key={idx}>{token.slice(2, -2)}</strong>;
      }
      if (token.startsWith('`') && token.endsWith('`')) {
        return <code key={idx} className="inline-code">{token.slice(1, -1)}</code>;
      }
      return token;
    });
  };

  return (
    <div className="formatted-content">
      {parts.map((part, index) => {
        if (part.startsWith('```') && part.endsWith('```')) {
          const firstLineEnd = part.indexOf('\n');
          const language =
            firstLineEnd > 3 ? part.substring(3, firstLineEnd).trim() : 'code';
          const codeBody =
            firstLineEnd !== -1
              ? part.substring(firstLineEnd + 1, part.length - 3)
              : part.slice(3, -3);

          const isCopied = copiedIndex === index;

          return (
            <div key={index} className="code-block-container">
              <div className="code-block-header">
                <span className="code-block-lang">{language || 'code'}</span>
                <button
                  type="button"
                  className="code-copy-btn"
                  onClick={() => handleCopy(codeBody, index)}
                  title="Copy snippet"
                >
                  {isCopied ? (
                    <>
                      <CheckIcon size={14} className="copy-check-icon" />
                      <span>Copied</span>
                    </>
                  ) : (
                    <>
                      <CopyIcon size={14} />
                      <span>Copy</span>
                    </>
                  )}
                </button>
              </div>
              <pre className="code-block-pre">
                <code>{codeBody}</code>
              </pre>
            </div>
          );
        }

        return <React.Fragment key={index}>{renderInlineFormatted(part)}</React.Fragment>;
      })}
    </div>
  );
};
