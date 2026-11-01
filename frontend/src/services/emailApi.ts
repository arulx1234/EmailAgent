export interface GmailEmail {
  id: string;
  thread_id: string | null;
  sender: string;
  to: string;
  subject: string;
  date: string;
  snippet: string;
  body?: string;
  category_label?: string;
  category_labels?: string[];
  classification: Omit<EmailClassification, "id">;
  labels: string[];
  is_unread: boolean;
}

export interface GoogleUserProfile {
  name: string;
  email: string;
  picture?: string;
}

interface GmailEmailsResponse {
  count: number;
  emails: GmailEmail[];
  warnings?: string[];
}

export interface EmailClassification {
  id: string;
  provider?: "openai" | "gemini" | "groq" | "rules";
  category: "work" | "personal" | "finance" | "promotions" | "security" | "other";
  priority: "low" | "normal" | "high" | "urgent";
  time_sensitive: boolean;
  deadline: string | null;
  confidence: number;
  reason: string;
  priority_reason: string;
}

interface GmailLabelSyncResponse {
  label_name: string;
  matched_count: number;
  removed_count: number;
}

interface GmailLabelResponse {
  id: string;
  name: string;
}

export interface ReplyDraftProcessingResult {
  reviewed_count: number;
  created_count: number;
  skipped_count: number;
  warnings: string[];
}

export interface MailboxRefreshEventDetail {
  emails: GmailEmail[];
  draftStatus: string;
}

const API_BASE_URL = "http://localhost:8000";
const DISPLAY_NAME_STORAGE_KEY = "ai-mail-display-name";
export const DISPLAY_NAME_CHANGED_EVENT = "ai-mail-display-name-changed";
export const MAILBOX_REFRESHED_EVENT = "ai-mail-mailbox-refreshed";
export const GMAIL_LABELS_SYNCED_EVENT = "ai-mail-labels-synced";
export const CUSTOM_LABELS_STORAGE_KEY = "ai-mail-custom-labels";
export const CUSTOM_LABELS_CHANGED_EVENT = "ai-mail-custom-labels-changed";

export function getSavedDisplayName(): string | null {
  return window.localStorage.getItem(DISPLAY_NAME_STORAGE_KEY);
}

export function saveDisplayName(name: string): void {
  window.localStorage.setItem(DISPLAY_NAME_STORAGE_KEY, name);
  window.dispatchEvent(
    new CustomEvent<string>(DISPLAY_NAME_CHANGED_EVENT, { detail: name })
  );
}

export async function fetchEmails(
  maxResults = 10,
  folder: "all" | "spam" = "all",
  label?: string,
  categoryLabel?: string,
  refresh = false,
  customCategories: string[] = []
): Promise<GmailEmailsResponse> {
  const query = new URLSearchParams({
    max_results: String(maxResults),
    folder,
  });
  if (label) query.set("label", label);
  if (categoryLabel) query.set("category_label", categoryLabel);
  if (refresh) query.set("refresh", "true");
  customCategories.forEach((customCategory) =>
    query.append("custom_labels", customCategory)
  );
  const response = await fetch(
    `${API_BASE_URL}/api/emails?${query.toString()}`,
    { cache: "no-store", credentials: "include" }
  );

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error("Connect Gmail from Settings to view your mailbox.");
    }

    throw new Error(
      `Failed to fetch emails: ${response.status} ${response.statusText}`
    );
  }

  return response.json() as Promise<GmailEmailsResponse>;
}

export async function processReplyDrafts(): Promise<ReplyDraftProcessingResult> {
  const response = await fetch(`${API_BASE_URL}/api/emails/drafts/process`, {
    method: "POST",
    credentials: "include",
  });

  if (!response.ok) {
    let detail = "";
    try {
      const errorResponse = (await response.json()) as { detail?: unknown };
      if (typeof errorResponse.detail === "string") {
        detail = errorResponse.detail;
      }
    } catch {
      detail = "";
    }

    throw new Error(
      detail ||
        `Failed to check for reply drafts: ${response.status} ${response.statusText}`
    );
  }

  return response.json() as Promise<ReplyDraftProcessingResult>;
}

export async function syncGmailLabel(
  name: string
): Promise<GmailLabelSyncResponse> {
  const response = await fetch(`${API_BASE_URL}/api/labels/sync`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });

  if (!response.ok) {
    let detail = "";
    try {
      const errorResponse = (await response.json()) as { detail?: unknown };
      if (typeof errorResponse.detail === "string") {
        detail = errorResponse.detail;
      }
    } catch {
      detail = "";
    }

    throw new Error(
      detail ||
        `Failed to sync Gmail label: ${response.status} ${response.statusText}`
    );
  }

  return response.json() as Promise<GmailLabelSyncResponse>;
}

export async function createGmailLabel(name: string): Promise<GmailLabelResponse> {
  const response = await fetch(`${API_BASE_URL}/api/labels`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });

  if (!response.ok) {
    let detail = "";
    try {
      const errorResponse = (await response.json()) as { detail?: unknown };
      if (typeof errorResponse.detail === "string") {
        detail = errorResponse.detail;
      }
    } catch {
      detail = "";
    }

    throw new Error(
      detail ||
        `Failed to create Gmail label: ${response.status} ${response.statusText}`
    );
  }

  return response.json() as Promise<GmailLabelResponse>;
}

export async function deleteGmailLabel(name: string): Promise<void> {
  const query = new URLSearchParams({ name });
  const response = await fetch(`${API_BASE_URL}/api/labels?${query}`, {
    method: "DELETE",
    credentials: "include",
  });

  if (!response.ok) {
    let detail = "";
    try {
      const errorResponse = (await response.json()) as { detail?: unknown };
      if (typeof errorResponse.detail === "string") detail = errorResponse.detail;
    } catch {
      detail = "";
    }
    throw new Error(
      detail || `Failed to delete Gmail label: ${response.status} ${response.statusText}`
    );
  }
}

export async function fetchCurrentUser(): Promise<GoogleUserProfile> {
  const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error(
      `Failed to load profile: ${response.status} ${response.statusText}`
    );
  }

  return response.json() as Promise<GoogleUserProfile>;
}

export function startGoogleLogin(): void {
  window.location.assign(`${API_BASE_URL}/api/auth/google`);
}

export async function logoutCurrentUser(): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/auth/logout`, {
    method: "POST",
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error(
      `Failed to disconnect Gmail: ${response.status} ${response.statusText}`
    );
  }
}
