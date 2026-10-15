import React, { useState } from 'react';
import { CopyIcon, CheckIcon, DownloadIcon } from './Icons';

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

  const renderInlineSpans = (text: string) => {
    // Matches: [link text](url), **bold**, `code`
    const regex = /(\[.*?\]\(.*?\)|\*\*.*?\*\*|`.*?`)/g;
    const tokens = text.split(regex);

    return tokens.map((token, idx) => {
      if (token.startsWith('**') && token.endsWith('**')) {
        return <strong key={idx}>{token.slice(2, -2)}</strong>;
      }
      if (token.startsWith('`') && token.endsWith('`')) {
        return <code key={idx} className="inline-code">{token.slice(1, -1)}</code>;
      }
      // Markdown link: [text](url)
      const linkMatch = token.match(/^\[(.*?)\]\((.*?)\)$/);
      if (linkMatch) {
        const linkText = linkMatch[1];
        const linkUrl = linkMatch[2];
        const isPdf = linkUrl.includes('/api/pdf/download/') || linkUrl.toLowerCase().endsWith('.pdf');

        if (isPdf) {
          return (
            <a
              key={idx}
              href={linkUrl}
              target="_blank"
              rel="noopener noreferrer"
              download
              className="chat-pdf-download-btn"
              title="Download generated PDF file"
            >
              <DownloadIcon size={14} />
              <span>{linkText}</span>
            </a>
          );
        }

        return (
          <a
            key={idx}
            href={linkUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="chat-inline-link"
          >
            {linkText}
          </a>
        );
      }
      return token;
    });
  };

  const renderInlineFormatted = (rawText: string) => {
    const lines = rawText.split('\n');
    const nodes: React.ReactNode[] = [];
    let i = 0;

    while (i < lines.length) {
      const line = lines[i];
      const trimmed = line.trim();

      // Horizontal rule
      if (trimmed === '---' || trimmed === '***' || trimmed === '___') {
        nodes.push(<hr key={i} className="content-hr" />);
        i++;
        continue;
      }

      // Check for Markdown Table
      if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
        const tableLines: string[] = [];
        while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
          tableLines.push(lines[i].trim());
          i++;
        }

        if (tableLines.length > 0) {
          const rows = tableLines.map((tl) =>
            tl
              .slice(1, -1)
              .split('|')
              .map((c) => c.trim())
          );
          // Check if row 1 is separator
          const hasSeparator = rows.length > 1 && rows[1].every((c) => /^:?-+:?$/.test(c));
          const headerRow = rows[0];
          const bodyRows = hasSeparator ? rows.slice(2) : rows.slice(1);

          nodes.push(
            <div key={`table-${i}`} className="content-table-wrapper">
              <table className="content-table">
                <thead>
                  <tr>
                    {headerRow.map((cell, cIdx) => (
                      <th key={cIdx}>{renderInlineSpans(cell)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {bodyRows.map((row, rIdx) => (
                    <tr key={rIdx}>
                      {row.map((cell, cIdx) => (
                        <td key={cIdx}>{renderInlineSpans(cell)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
          continue;
        }
      }

      // Headings
      if (line.startsWith('### ')) {
        nodes.push(
          <h3 key={i} className="content-h3">
            {renderInlineSpans(line.replace('### ', ''))}
          </h3>
        );
        i++;
        continue;
      }
      if (line.startsWith('## ')) {
        nodes.push(
          <h2 key={i} className="content-h2">
            {renderInlineSpans(line.replace('## ', ''))}
          </h2>
        );
        i++;
        continue;
      }
      if (line.startsWith('# ')) {
        nodes.push(
          <h1 key={i} className="content-h1">
            {renderInlineSpans(line.replace('# ', ''))}
          </h1>
        );
        i++;
        continue;
      }
      if (line.startsWith('#### ')) {
        nodes.push(
          <h4 key={i} className="content-h4">
            {renderInlineSpans(line.replace('#### ', ''))}
          </h4>
        );
        i++;
        continue;
      }

      // Bullet lists
      if (line.startsWith('- ') || line.startsWith('* ')) {
        nodes.push(
          <div key={i} className="content-bullet">
            <span className="bullet-dot">•</span>
            <span>{renderInlineSpans(line.substring(2))}</span>
          </div>
        );
        i++;
        continue;
      }

      // Numbered lists
      const numMatch = line.match(/^(\d+\.)\s+(.*)$/);
      if (numMatch) {
        nodes.push(
          <div key={i} className="content-bullet">
            <span className="bullet-num">{numMatch[1]}</span>
            <span>{renderInlineSpans(numMatch[2])}</span>
          </div>
        );
        i++;
        continue;
      }

      // Blank line
      if (!trimmed) {
        nodes.push(<div key={i} className="content-space" />);
        i++;
        continue;
      }

      // Standard paragraph
      nodes.push(
        <p key={i} className="content-p">
          {renderInlineSpans(line)}
        </p>
      );
      i++;
    }

    return nodes;
  };

  // Split by code blocks: ```lang ... ```
  const parts = content.split(/(```[\s\S]*?```)/g);

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
