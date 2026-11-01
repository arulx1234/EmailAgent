export interface Email {
  id: string;
  threadId: string;

  sender: string;
  senderEmail: string;

  subject: string;
  preview: string;
  body: string;

  timestamp: string;
  read: boolean;

  classificationCategory: "work" | "personal" | "finance" | "promotions" | "security" | "other";
  gmailLabels: string[];
  subcategory?: string;

  priority: "low" | "normal" | "high" | "urgent";
  timeSensitive: boolean;
  deadline?: string | null;
  priorityReason?: string;

  confidence: number;
  classificationProvider?: "openai" | "gemini" | "groq" | "rules";

  spam: boolean;
  securityStatus: "safe" | "suspicious" | "dangerous" | "unknown";
}
