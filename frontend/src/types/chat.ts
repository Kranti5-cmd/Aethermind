export interface MessageAttachment {
  id: string;
  documentId?: string;
  name: string;
  type: 'pdf' | 'docx' | 'txt' | 'csv' | 'image' | string;
  mimeType?: string;
  size?: number;
  previewUrl?: string;
  base64Data?: string;
  extractedText?: string;
  status: 'uploading' | 'processing' | 'ready' | 'error';
  progress?: number;
  error?: string;
}

export interface Message {
  id: string;
  sender: 'user' | 'assistant';
  content: string;
  timestamp: string;
  isError?: boolean;
  attachments?: MessageAttachment[];
}

export interface ChatSession {
  id: string;
  title: string;
  lastUpdated: string;
  messages: Message[];
}

export interface ChatApiResponse {
  reply: string;
  session_id: string;
  timestamp: string;
}
