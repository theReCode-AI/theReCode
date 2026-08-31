export interface GeminiCredential {
  id: string;
  configured: boolean;
  key_label: string | null;
  created_at: string;
  updated_at: string;
}

export interface GeminiCredentialCreate {
  api_key: string;
  key_label?: string;
}
