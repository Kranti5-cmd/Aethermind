import React, { useState, useRef, useMemo, type ChangeEvent, type DragEvent } from 'react';
import {
  UploadCloudIcon,
  FileTextIcon,
  CopyIcon,
  CheckIcon,
  DownloadIcon,
  AlertCircleIcon,
  TrashIcon,
  TableIcon,
  MaximizeIcon,
  MinimizeIcon,
  SparklesIcon,
  MessageSquareIcon,
} from './Icons';
import type { ExtractedDocument, DocumentUploadApiResponse, DocumentSummaryResponse } from '../types/document';

interface DocumentsViewProps {
  documents: ExtractedDocument[];
  onAddDocument: (doc: ExtractedDocument) => void;
  onDeleteDocument: (id: string) => void;
  selectedDocId: string | null;
  onSelectDoc: (id: string) => void;
  onChatWithDocument?: (doc: ExtractedDocument) => void;
}

export const DocumentsView: React.FC<DocumentsViewProps> = ({
  documents,
  onAddDocument,
  onDeleteDocument,
  selectedDocId,
  onSelectDoc,
  onChatWithDocument,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [csvViewMode, setCsvViewMode] = useState<'table' | 'raw'>('table');
  const [summaries, setSummaries] = useState<Record<string, DocumentSummaryResponse>>({});
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [summarizeError, setSummarizeError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const selectedDoc = documents.find((d) => d.id === selectedDocId) || documents[0] || null;
  const currentSummary = selectedDoc ? summaries[selectedDoc.id] : null;

  const handleSummarizeDocument = async (docId: string) => {
    setIsSummarizing(true);
    setSummarizeError(null);
    try {
      let res: Response;
      try {
        res = await fetch(`/api/documents/${encodeURIComponent(docId)}/summarize`, {
          method: 'POST',
        });
      } catch {
        res = await fetch(`http://127.0.0.1:8000/api/documents/${encodeURIComponent(docId)}/summarize`, {
          method: 'POST',
        });
      }

      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        if (res.status === 429) {
          throw new Error('Gemini API rate limit or quota reached. Please wait a moment and try again.');
        }
        throw new Error(errJson?.detail || `Summarization failed (HTTP ${res.status})`);
      }

      const data: DocumentSummaryResponse = await res.json();
      setSummaries((prev) => ({ ...prev, [docId]: data }));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Summarization failed';
      setSummarizeError(msg);
    } finally {
      setIsSummarizing(false);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const uploadFileToBackend = async (file: File) => {
    setErrorMessage(null);
    setIsUploading(true);

    const formData = new FormData();
    formData.append('file', file);

    try {
      let res: Response;
      try {
        res = await fetch('/api/documents/upload', {
          method: 'POST',
          body: formData,
        });
      } catch {
        res = await fetch('http://127.0.0.1:8000/api/documents/upload', {
          method: 'POST',
          body: formData,
        });
      }

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || `Upload failed with status ${res.status}`);
      }

      const responseData = data as DocumentUploadApiResponse;
      const newDoc: ExtractedDocument = {
        id: responseData.id || `doc-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
        filename: responseData.filename,
        file_type: responseData.file_type,
        file_size: responseData.file_size,
        extracted_text: responseData.extracted_text,
        metadata: responseData.metadata,
        uploaded_at:
          responseData.uploaded_at ||
          new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }),
        status: 'success',
      };

      onAddDocument(newDoc);
      onSelectDoc(newDoc.id);
      setIsExpanded(false);
      setCsvViewMode('table');
    } catch (err: unknown) {
      const errDetail = err instanceof Error ? err.message : 'Upload failed';
      setErrorMessage(errDetail);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      uploadFileToBackend(file);
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      uploadFileToBackend(file);
    }
  };

  const handleCopyText = () => {
    if (!selectedDoc || !selectedDoc.extracted_text) return;
    navigator.clipboard.writeText(selectedDoc.extracted_text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadText = () => {
    if (!selectedDoc || !selectedDoc.extracted_text) return;
    const blob = new Blob([selectedDoc.extracted_text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${selectedDoc.filename.replace(/\.[^/.]+$/, '')}_extracted.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const getFormatBadgeClass = (type: string) => {
    switch (type.toLowerCase()) {
      case 'pdf':
        return 'badge-pdf';
      case 'docx':
        return 'badge-docx';
      case 'csv':
        return 'badge-csv';
      case 'txt':
        return 'badge-txt';
      default:
        return 'badge-generic';
    }
  };

  // Helper to determine if a value is numeric for proper alignment
  const isNumeric = (val: string): boolean => {
    if (!val || typeof val !== 'string') return false;
    const trimmed = val.trim().replace(/[$€£,%]/g, '');
    return !isNaN(Number(trimmed)) && trimmed !== '';
  };

  // Parse CSV data safely into columns and rows
  const parsedCsvData = useMemo(() => {
    if (!selectedDoc || selectedDoc.file_type !== 'csv') return null;

    // 1. If rows & columns are already available in metadata
    if (selectedDoc.metadata.rows && selectedDoc.metadata.rows.length > 0) {
      return {
        columns: selectedDoc.metadata.columns || [],
        rows: selectedDoc.metadata.rows,
      };
    }

    // 2. Fallback: Parse from extracted_text if metadata.rows is missing
    const text = selectedDoc.extracted_text || '';
    const lines = text.split(/\r?\n/);
    const dataPreviewIdx = lines.findIndex((l) => l.includes('--- Data Preview ---'));
    
    let rawTableLines: string[] = [];
    if (dataPreviewIdx !== -1) {
      rawTableLines = lines.slice(dataPreviewIdx + 1).filter((l) => l.trim() && !l.startsWith('---') && !l.startsWith('[...'));
    } else {
      rawTableLines = lines.filter((l) => l.trim() && !l.startsWith('---'));
    }

    if (rawTableLines.length === 0) {
      return {
        columns: selectedDoc.metadata.columns || [],
        rows: [],
      };
    }

    // Parse header and rows
    const firstLine = rawTableLines[0];
    let delimiter = '|';
    if (!firstLine.includes('|')) {
      if (firstLine.includes('\t')) delimiter = '\t';
      else if (firstLine.includes(';')) delimiter = ';';
      else if (firstLine.includes(',')) delimiter = ',';
    }

    const columns = (selectedDoc.metadata.columns && selectedDoc.metadata.columns.length > 0)
      ? selectedDoc.metadata.columns
      : firstLine.split(delimiter).map((c) => c.trim());

    // Skip header and separator lines
    const startRowIdx = (selectedDoc.metadata.columns && selectedDoc.metadata.columns.length > 0 && !rawTableLines[0].includes('---'))
      ? 0
      : (rawTableLines[1] && rawTableLines[1].includes('-+-')) ? 2 : 1;

    const rows: string[][] = [];
    for (let i = startRowIdx; i < rawTableLines.length; i++) {
      const line = rawTableLines[i].trim();
      if (!line || line.startsWith('-+-') || line.startsWith('---')) continue;
      const cells = line.split(delimiter).map((c) => c.trim());
      if (cells.length > 0 && cells.some((c) => c !== '')) {
        rows.push(cells);
      }
    }

    return { columns, rows };
  }, [selectedDoc]);

  return (
    <div className="documents-view-container">
      {/* View Header */}
      <div className="documents-hero">
        <div className="documents-hero-badge">
          <FileTextIcon size={14} />
          <span>Module 2: Document Intelligence</span>
        </div>
        <h2 className="documents-hero-title">Document Ingestion & Text Extraction</h2>
        <p className="documents-hero-desc">
          Upload PDF, Word, Plain Text, or CSV files to extract textual content and structural metadata.
        </p>
      </div>

      {/* Error Banner */}
      {errorMessage && (
        <div className="document-error-banner" role="alert">
          <div className="error-icon-wrapper">
            <AlertCircleIcon size={18} />
          </div>
          <div className="error-text">
            <strong>Extraction Error</strong>
            <span>{errorMessage}</span>
          </div>
          <button
            className="error-dismiss-btn"
            onClick={() => setErrorMessage(null)}
            aria-label="Dismiss error"
          >
            ×
          </button>
        </div>
      )}

      {/* Upload Drag & Drop Area */}
      <div
        className={`upload-dropzone ${isDragging ? 'drag-over' : ''} ${isUploading ? 'uploading' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt,.csv"
          onChange={handleFileChange}
          style={{ display: 'none' }}
          id="document-file-input"
        />

        <div className="dropzone-content">
          <div className="dropzone-icon-bubble">
            <UploadCloudIcon size={32} className={isUploading ? 'pulsing-icon' : ''} />
          </div>

          <div className="dropzone-text-group">
            <h3 className="dropzone-title">
              {isUploading ? 'Processing Document on Backend...' : 'Drag and drop files here'}
            </h3>
            <p className="dropzone-subtitle">
              {isUploading
                ? 'Parsing document text and structure using backend extraction engines'
                : 'or click to browse from your device'}
            </p>
          </div>

          <button
            type="button"
            className="browse-files-btn"
            disabled={isUploading}
            onClick={(e) => {
              e.stopPropagation();
              fileInputRef.current?.click();
            }}
          >
            {isUploading ? 'Extracting...' : 'Browse Files'}
          </button>

          <div className="supported-formats-pills">
            <span className="format-pill">PDF (.pdf)</span>
            <span className="format-pill">Word (.docx)</span>
            <span className="format-pill">Text (.txt)</span>
            <span className="format-pill">Spreadsheet (.csv)</span>
            <span className="format-pill format-limit">Max 10 MB</span>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      {documents.length > 0 && (
        <div className="documents-main-layout">
          {/* Document History Selector */}
          <div className="documents-history-bar">
            <div className="history-bar-title">
              <span>Uploaded Documents ({documents.length})</span>
            </div>
            <div className="history-chips-list">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className={`doc-chip ${selectedDoc?.id === doc.id ? 'active' : ''}`}
                  onClick={() => onSelectDoc(doc.id)}
                >
                  <span className={`doc-chip-badge ${getFormatBadgeClass(doc.file_type)}`}>
                    {doc.file_type.toUpperCase()}
                  </span>
                  <span className="doc-chip-name" title={doc.filename}>
                    {doc.filename}
                  </span>
                  <button
                    className="doc-chip-delete"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteDocument(doc.id);
                    }}
                    title="Delete document"
                    aria-label={`Delete ${doc.filename}`}
                  >
                    <TrashIcon size={12} />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Active Document Card */}
          {selectedDoc && (
            <div className="document-preview-card">
              {/* Card Header */}
              <div className="preview-card-header">
                <div className="preview-meta-left">
                  <div className={`preview-format-icon ${getFormatBadgeClass(selectedDoc.file_type)}`}>
                    <FileTextIcon size={24} />
                  </div>
                  <div className="preview-title-group">
                    <h3 className="preview-filename" title={selectedDoc.filename}>
                      {selectedDoc.filename}
                    </h3>
                    <div className="preview-tags-row">
                      <span className={`format-tag ${getFormatBadgeClass(selectedDoc.file_type)}`}>
                        {selectedDoc.file_type.toUpperCase()}
                      </span>
                      <span className="meta-tag">{formatFileSize(selectedDoc.file_size)}</span>
                      <span className="meta-tag">Uploaded at {selectedDoc.uploaded_at}</span>
                      <span className="status-tag status-success">
                        <span className="status-dot-mini" /> Processed Successfully
                      </span>
                    </div>
                  </div>
                </div>

                {/* Actions Toolbar */}
                <div className="preview-actions">
                  <button
                    className={`preview-btn summarize-btn ${isSummarizing ? 'loading' : ''}`}
                    onClick={() => handleSummarizeDocument(selectedDoc.id)}
                    disabled={isSummarizing}
                    title="Summarize document and extract key points using Gemini AI"
                  >
                    <SparklesIcon size={15} className={isSummarizing ? 'spinning-sparkle' : ''} />
                    <span>{isSummarizing ? 'Analyzing...' : currentSummary ? 'Re-summarize' : 'AI Summary'}</span>
                  </button>

                  {onChatWithDocument && (
                    <button
                      className="preview-btn chat-doc-btn"
                      onClick={() => onChatWithDocument(selectedDoc)}
                      title="Attach this document and chat with Gemini"
                    >
                      <MessageSquareIcon size={15} />
                      <span>Chat with Doc</span>
                    </button>
                  )}

                  <button
                    className="preview-btn copy-btn"
                    onClick={handleCopyText}
                    title="Copy extracted text"
                  >
                    {copied ? <CheckIcon size={15} /> : <CopyIcon size={15} />}
                    <span>{copied ? 'Copied!' : 'Copy Text'}</span>
                  </button>
                  <button
                    className="preview-btn download-btn"
                    onClick={handleDownloadText}
                    title="Download extracted text (.txt)"
                  >
                    <DownloadIcon size={15} />
                    <span>Download</span>
                  </button>
                  <button
                    className="preview-btn delete-btn"
                    onClick={() => onDeleteDocument(selectedDoc.id)}
                    title="Delete document"
                  >
                    <TrashIcon size={15} />
                    <span>Delete</span>
                  </button>
                </div>
              </div>

              {/* Polished, Relevant Metadata Cards */}
              <div className="extraction-metrics-grid">
                {/* For CSV: Rows & Columns are primary */}
                {selectedDoc.file_type === 'csv' && (
                  <>
                    <div className="metric-box">
                      <span className="metric-label">Rows</span>
                      <span className="metric-value">
                        {selectedDoc.metadata.row_count?.toLocaleString() || 0}
                      </span>
                    </div>
                    <div className="metric-box">
                      <span className="metric-label">Columns</span>
                      <span className="metric-value">
                        {selectedDoc.metadata.column_count?.toLocaleString() || 0}
                      </span>
                    </div>
                    <div className="metric-box">
                      <span className="metric-label">Characters</span>
                      <span className="metric-value">
                        {selectedDoc.metadata.char_count?.toLocaleString() || 0}
                      </span>
                    </div>
                  </>
                )}

                {/* For PDF: Pages & Words */}
                {selectedDoc.file_type === 'pdf' && (
                  <>
                    <div className="metric-box">
                      <span className="metric-label">Pages</span>
                      <span className="metric-value">{selectedDoc.metadata.page_count || 1}</span>
                    </div>
                    <div className="metric-box">
                      <span className="metric-label">Words</span>
                      <span className="metric-value">
                        {selectedDoc.metadata.word_count?.toLocaleString() || 0}
                      </span>
                    </div>
                    <div className="metric-box">
                      <span className="metric-label">Characters</span>
                      <span className="metric-value">
                        {selectedDoc.metadata.char_count?.toLocaleString() || 0}
                      </span>
                    </div>
                  </>
                )}

                {/* For DOCX: Paragraphs & Tables */}
                {selectedDoc.file_type === 'docx' && (
                  <>
                    <div className="metric-box">
                      <span className="metric-label">Paragraphs</span>
                      <span className="metric-value">
                        {selectedDoc.metadata.paragraph_count?.toLocaleString() || 0}
                      </span>
                    </div>
                    {selectedDoc.metadata.table_count !== undefined && selectedDoc.metadata.table_count > 0 && (
                      <div className="metric-box">
                        <span className="metric-label">Tables</span>
                        <span className="metric-value">{selectedDoc.metadata.table_count}</span>
                      </div>
                    )}
                    <div className="metric-box">
                      <span className="metric-label">Words</span>
                      <span className="metric-value">
                        {selectedDoc.metadata.word_count?.toLocaleString() || 0}
                      </span>
                    </div>
                    <div className="metric-box">
                      <span className="metric-label">Characters</span>
                      <span className="metric-value">
                        {selectedDoc.metadata.char_count?.toLocaleString() || 0}
                      </span>
                    </div>
                  </>
                )}

                {/* For TXT: Lines & Words */}
                {selectedDoc.file_type === 'txt' && (
                  <>
                    <div className="metric-box">
                      <span className="metric-label">Lines</span>
                      <span className="metric-value">
                        {selectedDoc.metadata.line_count?.toLocaleString() || 0}
                      </span>
                    </div>
                    <div className="metric-box">
                      <span className="metric-label">Words</span>
                      <span className="metric-value">
                        {selectedDoc.metadata.word_count?.toLocaleString() || 0}
                      </span>
                    </div>
                    <div className="metric-box">
                      <span className="metric-label">Characters</span>
                      <span className="metric-value">
                        {selectedDoc.metadata.char_count?.toLocaleString() || 0}
                      </span>
                    </div>
                  </>
                )}

                {/* Extraction Engine */}
                {selectedDoc.metadata.engine && (
                  <div className="metric-box">
                    <span className="metric-label">Engine</span>
                    <span className="metric-value">{selectedDoc.metadata.engine}</span>
                  </div>
                )}
              </div>

              {/* AI Insights & Key Extraction (Requirement 7) */}
              {summarizeError && (
                <div className="insights-error-banner" role="alert">
                  <div className="error-icon-wrapper">
                    <AlertCircleIcon size={16} />
                  </div>
                  <div className="error-text">
                    <strong>AI Extraction Issue</strong>
                    <span>{summarizeError}</span>
                  </div>
                  <button
                    className="error-dismiss-btn"
                    onClick={() => setSummarizeError(null)}
                    aria-label="Dismiss error"
                  >
                    ×
                  </button>
                </div>
              )}

              {isSummarizing && (
                <div className="ai-insights-loading-card">
                  <div className="insights-loading-spinner">
                    <SparklesIcon size={20} className="spinning-sparkle" />
                  </div>
                  <div className="insights-loading-text">
                    <h4>Synthesizing Document Insights with Gemini...</h4>
                    <p>Generating executive summary, extracting key takeaways, entities, and data points.</p>
                  </div>
                </div>
              )}

              {currentSummary && !isSummarizing && (
                <div className="ai-insights-panel">
                  <div className="ai-insights-header">
                    <div className="insights-header-left">
                      <div className="insights-sparkle-badge">
                        <SparklesIcon size={16} />
                      </div>
                      <div>
                        <h4 className="insights-title">AI Document Intelligence & Key Insights</h4>
                        <span className="insights-subtitle">
                          Synthesized with Gemini from extracted document content
                        </span>
                      </div>
                    </div>
                    {onChatWithDocument && (
                      <button
                        className="insights-chat-btn"
                        onClick={() => onChatWithDocument(selectedDoc)}
                        title="Chat about this document in AI chat"
                      >
                        <MessageSquareIcon size={14} />
                        <span>Ask in Chat</span>
                      </button>
                    )}
                  </div>

                  {/* Executive Summary */}
                  <div className="insights-summary-box">
                    <div className="insights-section-label">
                      <SparklesIcon size={13} />
                      <span>Executive Summary</span>
                    </div>
                    <p className="insights-summary-text">{currentSummary.summary}</p>
                  </div>

                  {/* Key Takeaways & Entities & Metrics Grid */}
                  <div className="insights-details-grid">
                    {currentSummary.key_points && currentSummary.key_points.length > 0 && (
                      <div className="insights-card">
                        <div className="insights-card-title">Key Findings & Takeaways</div>
                        <ul className="insights-bullets">
                          {currentSummary.key_points.map((pt, idx) => (
                            <li key={idx} className="insights-bullet-item">
                              <span className="insights-bullet-dot" />
                              <span>{pt}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    <div className="insights-card-column">
                      {currentSummary.key_entities && currentSummary.key_entities.length > 0 && (
                        <div className="insights-card">
                          <div className="insights-card-title">Key Entities & Topics</div>
                          <div className="insights-chips-wrap">
                            {currentSummary.key_entities.map((entity, idx) => (
                              <span key={idx} className="insights-chip">
                                {entity}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {currentSummary.metrics && currentSummary.metrics.length > 0 && (
                        <div className="insights-card">
                          <div className="insights-card-title">Extracted Metrics & Data Points</div>
                          <div className="insights-chips-wrap">
                            {currentSummary.metrics.map((metric, idx) => (
                              <span key={idx} className="insights-chip metric-chip">
                                {metric}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {!currentSummary && !isSummarizing && (
                <div className="ai-insights-callout">
                  <div className="insights-callout-icon">
                    <SparklesIcon size={20} />
                  </div>
                  <div className="insights-callout-content">
                    <h4>Analyze with Gemini Document Intelligence</h4>
                    <p>Extract an executive summary, key findings, participants, and numerical metrics from this document.</p>
                  </div>
                  <button
                    className="insights-callout-btn"
                    onClick={() => handleSummarizeDocument(selectedDoc.id)}
                    disabled={isSummarizing}
                  >
                    <SparklesIcon size={14} />
                    <span>Summarize & Extract Info</span>
                  </button>
                </div>
              )}

              {/* Preview Body */}
              <div className="preview-text-container">
                {/* Header with Title and Controls */}
                <div className="preview-text-header">
                  <div className="preview-header-left">
                    <span className="preview-section-title">
                      {selectedDoc.file_type === 'csv' ? 'Spreadsheet Content' : 'Extracted Text Content'}
                    </span>
                    <span className="preview-char-summary">
                      {selectedDoc.extracted_text.length.toLocaleString()} characters
                    </span>
                  </div>

                  <div className="preview-header-controls">
                    {/* View Switcher for CSV */}
                    {selectedDoc.file_type === 'csv' && (
                      <div className="csv-toggle-group">
                        <button
                          className={`csv-toggle-btn ${csvViewMode === 'table' ? 'active' : ''}`}
                          onClick={() => setCsvViewMode('table')}
                          title="View as interactive Data Table"
                        >
                          <TableIcon size={14} />
                          <span>Data Table</span>
                        </button>
                        <button
                          className={`csv-toggle-btn ${csvViewMode === 'raw' ? 'active' : ''}`}
                          onClick={() => setCsvViewMode('raw')}
                          title="View as raw text"
                        >
                          <FileTextIcon size={14} />
                          <span>Raw Text</span>
                        </button>
                      </div>
                    )}

                    {/* Expand/Collapse Toggle */}
                    <button
                      className="expand-collapse-btn"
                      onClick={() => setIsExpanded((prev) => !prev)}
                      title={isExpanded ? 'Collapse preview' : 'Expand preview'}
                    >
                      {isExpanded ? <MinimizeIcon size={14} /> : <MaximizeIcon size={14} />}
                      <span>{isExpanded ? 'Collapse' : 'Expand'}</span>
                    </button>
                  </div>
                </div>

                {/* CSV HTML Data Table Rendering */}
                {selectedDoc.file_type === 'csv' && csvViewMode === 'table' && parsedCsvData ? (
                  <div className={`csv-table-wrapper ${isExpanded ? 'expanded' : ''}`}>
                    <table className="csv-data-table">
                      <thead>
                        <tr>
                          <th className="csv-th-index">#</th>
                          {parsedCsvData.columns.map((col, idx) => (
                            <th key={idx} className="csv-th-header">
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {parsedCsvData.rows.length === 0 ? (
                          <tr>
                            <td colSpan={parsedCsvData.columns.length + 1} className="csv-empty-td">
                              No data rows found in CSV.
                            </td>
                          </tr>
                        ) : (
                          parsedCsvData.rows.map((row, rowIdx) => (
                            <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'csv-row-even' : 'csv-row-odd'}>
                              <td className="csv-td-index">{rowIdx + 1}</td>
                              {parsedCsvData.columns.map((_, colIdx) => {
                                const cellValue = row[colIdx] !== undefined ? row[colIdx] : '';
                                const numeric = isNumeric(cellValue);
                                return (
                                  <td
                                    key={colIdx}
                                    className={`csv-td-cell ${numeric ? 'numeric-cell' : 'text-cell'}`}
                                  >
                                    {cellValue}
                                  </td>
                                );
                              })}
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  /* Standard / Raw Extracted Text Viewer */
                  <div className={`preview-text-scrollbox ${isExpanded ? 'expanded' : ''}`}>
                    <pre className="preview-preformatted-text">{selectedDoc.extracted_text}</pre>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
