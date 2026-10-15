import React, { useState, useRef, useEffect } from 'react';
import type { MessageAttachment } from '../types/chat';
import type { ExtractedDocument, DocumentUploadApiResponse } from '../types/document';
import {
  SendIcon,
  PlusIcon,
  FileTextIcon,
  ImageIcon,
  FilesIcon,
  CloseIcon,
  AlertCircleIcon,
  TableIcon,
  BookOpenIcon,
  CheckIcon,
} from './Icons';

interface MessageInputProps {
  onSendMessage: (text: string, attachments?: MessageAttachment[]) => void;
  disabled?: boolean;
  availableDocuments?: ExtractedDocument[];
  onDocumentUploaded?: (doc: ExtractedDocument) => void;
  initialDocument?: ExtractedDocument | null;
  onClearInitialDocument?: () => void;
}

const MAX_DOC_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB
const MAX_IMG_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB
const SUPPORTED_DOC_EXTS = ['.pdf', '.docx', '.txt', '.csv'];
const SUPPORTED_IMG_EXTS = ['.png', '.jpg', '.jpeg', '.webp'];

function formatBytes(bytes?: number): string {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileType(fileName: string): string {
  const ext = fileName.slice(fileName.lastIndexOf('.')).toLowerCase();
  if (ext === '.pdf') return 'pdf';
  if (ext === '.docx') return 'docx';
  if (ext === '.txt') return 'txt';
  if (ext === '.csv') return 'csv';
  if (SUPPORTED_IMG_EXTS.includes(ext)) return 'image';
  return 'document';
}

export const MessageInput: React.FC<MessageInputProps> = ({
  onSendMessage,
  disabled = false,
  availableDocuments = [],
  onDocumentUploaded,
  initialDocument,
  onClearInitialDocument,
}) => {
  const [inputText, setInputText] = useState('');
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [showDocPicker, setShowDocPicker] = useState(false);
  const [attachments, setAttachments] = useState<MessageAttachment[]>([]);
  const [validationError, setValidationError] = useState<string | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const docInputRef = useRef<HTMLInputElement>(null);
  const imgInputRef = useRef<HTMLInputElement>(null);
  const multiInputRef = useRef<HTMLInputElement>(null);

  // Auto-resize textarea height to fit content up to 160px
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const nextHeight = Math.min(textareaRef.current.scrollHeight, 160);
      textareaRef.current.style.height = `${nextHeight}px`;
    }
  }, [inputText]);

  // Close attachment flyout menu when clicking outside or pressing Escape
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsMenuOpen(false);
        setShowDocPicker(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsMenuOpen(false);
        setShowDocPicker(false);
      }
    };

    if (isMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleKeyDown);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isMenuOpen]);

  const removeAttachment = (id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  };

  // Attach a previously uploaded document from Document Intelligence library
  const attachExistingDoc = (doc: ExtractedDocument) => {
    const isAlreadyAttached = attachments.some(
      (a) => (a.documentId && a.documentId === doc.id) || a.name === doc.filename
    );
    if (isAlreadyAttached) return;

    const newAtt: MessageAttachment = {
      id: `att-exist-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      documentId: doc.id,
      name: doc.filename,
      type: doc.file_type,
      size: doc.file_size,
      extractedText: doc.extracted_text,
      status: 'ready',
      progress: 100,
    };

    setAttachments((prev) => [...prev, newAtt]);
    setIsMenuOpen(false);
    setShowDocPicker(false);
    setValidationError(null);
  };

  // Auto-attach document when navigating from DocumentsView "Chat with Doc"
  useEffect(() => {
    if (initialDocument) {
      attachExistingDoc(initialDocument);
      if (onClearInitialDocument) {
        onClearInitialDocument();
      }
    }
  }, [initialDocument]);

  // Upload document file to backend extraction API
  const processDocumentFile = async (file: File) => {
    const fileExt = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
    if (!SUPPORTED_DOC_EXTS.includes(fileExt)) {
      setValidationError(
        `"${file.name}" is not a supported document format. Allowed: PDF, DOCX, TXT, CSV.`
      );
      return;
    }

    if (file.size > MAX_DOC_SIZE_BYTES) {
      setValidationError(
        `"${file.name}" exceeds the 10 MB document limit (${formatBytes(file.size)}).`
      );
      return;
    }

    const attId = `att-doc-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    const newAtt: MessageAttachment = {
      id: attId,
      name: file.name,
      type: getFileType(file.name),
      mimeType: file.type || 'application/octet-stream',
      size: file.size,
      status: 'uploading',
      progress: 25,
    };

    setAttachments((prev) => [...prev, newAtt]);

    const formData = new FormData();
    formData.append('file', file);

    try {
      setAttachments((prev) =>
        prev.map((a) => (a.id === attId ? { ...a, status: 'processing', progress: 50 } : a))
      );

      let res = await fetch('/api/documents/upload', {
        method: 'POST',
        body: formData,
      });

      // Fallback direct to port 8000 if proxy failed
      if (!res.ok && res.status >= 500) {
        try {
          const directRes = await fetch('http://127.0.0.1:8000/api/documents/upload', {
            method: 'POST',
            body: formData,
          });
          if (directRes.ok) res = directRes;
        } catch {
          // keep original response
        }
      }

      if (!res.ok) {
        const errorData = await res.json().catch(() => null);
        const errorDetail = errorData?.detail || `Upload failed (HTTP ${res.status})`;
        setAttachments((prev) =>
          prev.map((a) => (a.id === attId ? { ...a, status: 'error', error: errorDetail } : a))
        );
        return;
      }

      const data: DocumentUploadApiResponse = await res.json();
      const persistentId = data.id || attId;

      setAttachments((prev) =>
        prev.map((a) =>
          a.id === attId
            ? {
                ...a,
                documentId: persistentId,
                status: 'ready',
                extractedText: data.extracted_text,
                size: data.file_size || file.size,
                progress: 100,
              }
            : a
        )
      );

      // Add to Document Intelligence library in frontend state
      if (onDocumentUploaded) {
        onDocumentUploaded({
          id: persistentId,
          filename: data.filename,
          file_type: data.file_type,
          file_size: data.file_size || file.size,
          extracted_text: data.extracted_text,
          metadata: data.metadata || {},
          uploaded_at:
            data.uploaded_at ||
            new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }),
          status: 'success',
        });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Network failure';
      setAttachments((prev) =>
        prev.map((a) => (a.id === attId ? { ...a, status: 'error', error: msg } : a))
      );
    }
  };

  // Process image file via FileReader for client preview and backend multimodal delivery
  const processImageFile = (file: File) => {
    const fileExt = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
    if (!SUPPORTED_IMG_EXTS.includes(fileExt)) {
      setValidationError(
        `"${file.name}" is not a supported image format. Allowed: PNG, JPG, JPEG, WEBP.`
      );
      return;
    }

    if (file.size > MAX_IMG_SIZE_BYTES) {
      setValidationError(
        `"${file.name}" exceeds the 5 MB image limit (${formatBytes(file.size)}).`
      );
      return;
    }

    const attId = `att-img-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    const newAtt: MessageAttachment = {
      id: attId,
      name: file.name,
      type: 'image',
      mimeType: file.type || 'image/png',
      size: file.size,
      status: 'uploading',
      progress: 30,
    };

    setAttachments((prev) => [...prev, newAtt]);

    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUrl = e.target?.result as string;
      setAttachments((prev) =>
        prev.map((a) =>
          a.id === attId
            ? {
                ...a,
                status: 'ready',
                previewUrl: dataUrl,
                base64Data: dataUrl,
                progress: 100,
              }
            : a
        )
      );
    };

    reader.onerror = () => {
      setAttachments((prev) =>
        prev.map((a) => (a.id === attId ? { ...a, status: 'error', error: 'Failed to read image' } : a))
      );
    };

    reader.readAsDataURL(file);
  };

  // Handle file input changes
  const handleFilesSelected = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setValidationError(null);

    Array.from(files).forEach((file) => {
      const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
      if (SUPPORTED_DOC_EXTS.includes(ext)) {
        processDocumentFile(file);
      } else if (SUPPORTED_IMG_EXTS.includes(ext)) {
        processImageFile(file);
      } else {
        setValidationError(
          `Unsupported file type: "${file.name}". Please select PDF, DOCX, TXT, CSV, or Image.`
        );
      }
    });
  };

  const triggerInput = (type: 'document' | 'image' | 'multiple') => {
    setIsMenuOpen(false);
    setShowDocPicker(false);
    setValidationError(null);
    if (type === 'document' && docInputRef.current) {
      docInputRef.current.value = '';
      docInputRef.current.click();
    } else if (type === 'image' && imgInputRef.current) {
      imgInputRef.current.value = '';
      imgInputRef.current.click();
    } else if (type === 'multiple' && multiInputRef.current) {
      multiInputRef.current.value = '';
      multiInputRef.current.click();
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = inputText.trim();
    const readyAttachments = attachments.filter((a) => a.status === 'ready');
    const hasPending = attachments.some(
      (a) => a.status === 'uploading' || a.status === 'processing'
    );

    if (hasPending || disabled) return;
    if (!trimmed && readyAttachments.length === 0) return;

    onSendMessage(trimmed, readyAttachments.length > 0 ? readyAttachments : undefined);
    setInputText('');
    setAttachments([]);
    setValidationError(null);

    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const isSendDisabled =
    disabled ||
    (inputText.trim().length === 0 && !attachments.some((a) => a.status === 'ready')) ||
    attachments.some((a) => a.status === 'uploading' || a.status === 'processing');

  return (
    <div className="input-bar-container">
      {/* Hidden file inputs for menu actions */}
      <input
        type="file"
        ref={docInputRef}
        style={{ display: 'none' }}
        accept=".pdf,.docx,.txt,.csv"
        onChange={(e) => handleFilesSelected(e.target.files)}
      />
      <input
        type="file"
        ref={imgInputRef}
        style={{ display: 'none' }}
        accept="image/png,image/jpeg,image/webp"
        onChange={(e) => handleFilesSelected(e.target.files)}
      />
      <input
        type="file"
        ref={multiInputRef}
        style={{ display: 'none' }}
        multiple
        accept=".pdf,.docx,.txt,.csv,image/png,image/jpeg,image/webp"
        onChange={(e) => handleFilesSelected(e.target.files)}
      />

      <form className="input-form" onSubmit={handleSubmit}>
        {/* Error banner if validation fails */}
        {validationError && (
          <div className="attachment-error-banner" role="alert">
            <AlertCircleIcon size={16} className="error-icon" />
            <span className="error-text">{validationError}</span>
            <button
              type="button"
              className="error-dismiss-btn"
              onClick={() => setValidationError(null)}
              aria-label="Dismiss error"
            >
              <CloseIcon size={14} />
            </button>
          </div>
        )}

        {/* Attachment preview tray */}
        {attachments.length > 0 && (
          <div className="attachments-tray" aria-label="Attached files">
            {attachments.map((att) => (
              <div
                key={att.id}
                className={`attachment-chip ${att.status === 'error' ? 'chip-error' : ''} ${
                  att.status === 'ready' ? 'chip-ready' : ''
                }`}
              >
                {att.previewUrl ? (
                  <div className="chip-thumbnail-wrap">
                    <img src={att.previewUrl} alt={att.name} className="chip-thumbnail" />
                  </div>
                ) : (
                  <div className="chip-icon-wrap">
                    {att.type === 'csv' ? <TableIcon size={16} /> : <FileTextIcon size={16} />}
                  </div>
                )}

                <div className="chip-details">
                  <span className="chip-filename" title={att.name}>
                    {att.name}
                  </span>
                  <div className="chip-status-line">
                    {att.status === 'uploading' && (
                      <span className="chip-status uploading">
                        <span className="chip-spinner" /> Uploading...
                      </span>
                    )}
                    {att.status === 'processing' && (
                      <span className="chip-status processing">
                        <span className="chip-spinner" /> Extracting text...
                      </span>
                    )}
                    {att.status === 'ready' && (
                      <span className="chip-status ready">
                        {att.size ? formatBytes(att.size) : 'Ready'}
                      </span>
                    )}
                    {att.status === 'error' && (
                      <span className="chip-status error" title={att.error}>
                        {att.error || 'Failed'}
                      </span>
                    )}
                  </div>
                </div>

                <button
                  type="button"
                  className="chip-remove-btn"
                  onClick={() => removeAttachment(att.id)}
                  title={`Remove ${att.name}`}
                  aria-label={`Remove ${att.name}`}
                >
                  <CloseIcon size={12} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="input-box-wrapper">
          {/* Plus (+) Button and Dropdown Menu */}
          <div className="plus-menu-container" ref={menuRef}>
            <button
              type="button"
              className={`plus-btn ${isMenuOpen ? 'active' : ''}`}
              onClick={() => {
                setIsMenuOpen((prev) => !prev);
                setShowDocPicker(false);
              }}
              aria-label="Add attachment"
              title="Add attachment"
              aria-expanded={isMenuOpen}
              aria-haspopup="menu"
            >
              <PlusIcon size={18} />
            </button>

            {isMenuOpen && (
              <div className="attachment-dropdown-menu" role="menu">
                {/* 1. Attach Existing Document from Library */}
                <button
                  type="button"
                  className="attachment-menu-item"
                  onClick={() => setShowDocPicker((prev) => !prev)}
                  role="menuitem"
                >
                  <div className="menu-icon-box library-icon">
                    <BookOpenIcon size={16} />
                  </div>
                  <div className="menu-text-box">
                    <span className="menu-label">Attach from Documents</span>
                    <span className="menu-sublabel">
                      {availableDocuments.length > 0
                        ? `${availableDocuments.length} document${
                            availableDocuments.length > 1 ? 's' : ''
                          } in library`
                        : 'Select from uploaded documents'}
                    </span>
                  </div>
                </button>

                {/* Sub-view: Existing Documents Picker */}
                {showDocPicker && (
                  <div className="existing-docs-picker" role="region" aria-label="Available Documents">
                    <div className="picker-header">
                      <span className="picker-title">Select Document</span>
                      <button
                        type="button"
                        onClick={() => setShowDocPicker(false)}
                        className="picker-close-btn"
                        aria-label="Close document picker"
                      >
                        <CloseIcon size={12} />
                      </button>
                    </div>

                    {availableDocuments.length === 0 ? (
                      <div className="picker-empty">
                        <p>No documents uploaded yet.</p>
                        <button
                          type="button"
                          className="picker-upload-action"
                          onClick={() => triggerInput('document')}
                        >
                          Upload a Document Now
                        </button>
                      </div>
                    ) : (
                      <div className="picker-list">
                        {availableDocuments.map((doc) => {
                          const isAlreadyAttached = attachments.some(
                            (a) =>
                              (a.documentId && a.documentId === doc.id) ||
                              a.name === doc.filename
                          );
                          return (
                            <button
                              key={doc.id}
                              type="button"
                              className={`picker-doc-item ${
                                isAlreadyAttached ? 'already-attached' : ''
                              }`}
                              disabled={isAlreadyAttached}
                              onClick={() => attachExistingDoc(doc)}
                              title={
                                isAlreadyAttached
                                  ? `${doc.filename} is already attached`
                                  : `Attach ${doc.filename}`
                              }
                            >
                              <div className="picker-doc-icon">
                                {doc.file_type === 'csv' ? (
                                  <TableIcon size={14} />
                                ) : (
                                  <FileTextIcon size={14} />
                                )}
                              </div>
                              <div className="picker-doc-info">
                                <span className="picker-doc-name">{doc.filename}</span>
                                <span className="picker-doc-meta">
                                  {doc.file_type.toUpperCase()} • {formatBytes(doc.file_size)}
                                </span>
                              </div>
                              {isAlreadyAttached && (
                                <span className="picker-attached-badge">
                                  <CheckIcon size={12} />
                                </span>
                              )}
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}

                <div className="menu-divider" />

                {/* 2. Upload New Document */}
                <button
                  type="button"
                  className="attachment-menu-item"
                  onClick={() => triggerInput('document')}
                  role="menuitem"
                >
                  <div className="menu-icon-box doc-icon">
                    <FileTextIcon size={16} />
                  </div>
                  <div className="menu-text-box">
                    <span className="menu-label">Upload New Document</span>
                    <span className="menu-sublabel">PDF, DOCX, TXT, CSV (max 10MB)</span>
                  </div>
                </button>

                {/* 3. Upload Image */}
                <button
                  type="button"
                  className="attachment-menu-item"
                  onClick={() => triggerInput('image')}
                  role="menuitem"
                >
                  <div className="menu-icon-box img-icon">
                    <ImageIcon size={16} />
                  </div>
                  <div className="menu-text-box">
                    <span className="menu-label">Upload Image</span>
                    <span className="menu-sublabel">PNG, JPG, JPEG, WEBP (max 5MB)</span>
                  </div>
                </button>

                <div className="menu-divider" />

                {/* 4. Upload Multiple Files */}
                <button
                  type="button"
                  className="attachment-menu-item"
                  onClick={() => triggerInput('multiple')}
                  role="menuitem"
                >
                  <div className="menu-icon-box multi-icon">
                    <FilesIcon size={16} />
                  </div>
                  <div className="menu-text-box">
                    <span className="menu-label">Upload Multiple Files</span>
                    <span className="menu-sublabel">Select multiple docs or images</span>
                  </div>
                </button>
              </div>
            )}
          </div>

          <textarea
            ref={textareaRef}
            className="chat-textarea"
            placeholder={
              attachments.length > 0
                ? 'Ask a question about attached document(s) or leave blank to summarize...'
                : 'Message AetherMind...'
            }
            rows={1}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            aria-label="Message input"
          />

          <button
            type="submit"
            className="send-button"
            disabled={isSendDisabled}
            title="Send message (Enter)"
            aria-label="Send message"
          >
            <SendIcon size={18} />
          </button>
        </div>

        <div className="input-disclaimer">
          <span>AetherMind AI answers based on provided documents. Verify important information.</span>
        </div>
      </form>
    </div>
  );
};
