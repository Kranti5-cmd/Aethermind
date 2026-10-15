export interface DocumentMetadata {
  format?: string;
  engine?: string;
  page_count?: number;
  paragraph_count?: number;
  table_count?: number;
  line_count?: number;
  row_count?: number;
  column_count?: number;
  columns?: string[];
  rows?: string[][];
  char_count: number;
  word_count: number;
  has_selectable_text?: boolean;
}

export interface ExtractedDocument {
  id: string;
  filename: string;
  file_type: 'pdf' | 'docx' | 'txt' | 'csv' | string;
  file_size: number;
  extracted_text: string;
  metadata: DocumentMetadata;
  uploaded_at: string;
  status: 'success' | 'error' | 'processing';
  error_message?: string;
}

export interface DocumentUploadApiResponse {
  status: 'success' | 'error';
  id?: string;
  filename: string;
  file_type: string;
  file_size: number;
  extracted_text: string;
  metadata: DocumentMetadata;
  uploaded_at?: string;
}

export interface DocumentSummaryResponse {
  document_id: string;
  filename: string;
  summary: string;
  key_points: string[];
  key_entities: string[];
  metrics: string[];
}
