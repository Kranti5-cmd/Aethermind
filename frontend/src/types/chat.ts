export interface Message {
  id: string;
  sender: 'user' | 'assistant';
  content: string;
  timestamp: string;
  isError?: boolean;
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
