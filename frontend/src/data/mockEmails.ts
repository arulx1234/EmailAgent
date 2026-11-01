import type { Email } from "../types/email";

export const mockEmails: Email[] = [
  {
    id: "email-001",
    threadId: "thread-001",
    sender: "John Smith",
    senderEmail: "john@example.com",
    subject: "Refund request for my recent order",
    preview:
      "Hello, I would like to request a refund for my recent order. Could you please help me with the process?",
    body:
      "Hello Support Team,\n\nI would like to request a refund for my recent order ORD-12345. The product did not meet my expectations.\n\nPlease let me know what information you need from me.\n\nThank you,\nJohn Smith",
    timestamp: "2 min ago",
    read: false,
    classificationCategory: "other",
    gmailLabels: ["Customer Support"],
    subcategory: "Refund Request",
    priority: "high",
    timeSensitive: false,
    confidence: 0.96,
    spam: false,
    securityStatus: "safe",
  },

  {
    id: "email-002",
    threadId: "thread-002",
    sender: "Amazon",
    senderEmail: "shipment@amazon.com",
    subject: "Your order has shipped",
    preview:
      "Your package is on its way. Track your delivery and see the latest shipping information.",
    body:
      "Your Amazon order has shipped and is on its way.\n\nExpected delivery: Tomorrow.",
    timestamp: "12 min ago",
    read: true,
    classificationCategory: "other",
    gmailLabels: ["Shopping"],
    subcategory: "Order Update",
    priority: "normal",
    timeSensitive: false,
    confidence: 0.99,
    spam: false,
    securityStatus: "safe",
  },

  {
    id: "email-003",
    threadId: "thread-003",
    sender: "Sarah Johnson",
    senderEmail: "sarah@company.com",
    subject: "Project meeting tomorrow",
    preview:
      "Hi, just a reminder that we have our project meeting tomorrow at 10 AM.",
    body:
      "Hi Team,\n\nJust a reminder that we have our project meeting tomorrow at 10 AM.\n\nAgenda:\n- Project progress\n- Current blockers\n- Next steps\n\nRegards,\nSarah",
    timestamp: "25 min ago",
    read: true,
    classificationCategory: "work",
    gmailLabels: [],
    subcategory: "Meeting",
    priority: "urgent",
    timeSensitive: true,
    deadline: "tomorrow at 10 AM",
    priorityReason: "The project meeting is scheduled for tomorrow.",
    confidence: 0.94,
    spam: false,
    securityStatus: "safe",
  },

  {
    id: "email-004",
    threadId: "thread-004",
    sender: "Netflix",
    senderEmail: "info@netflix.com",
    subject: "Your monthly subscription",
    preview:
      "Your monthly subscription payment has been processed successfully.",
    body:
      "Your monthly Netflix subscription payment has been processed successfully.",
    timestamp: "1 hour ago",
    read: true,
    classificationCategory: "finance",
    gmailLabels: [],
    subcategory: "Subscription",
    priority: "low",
    timeSensitive: false,
    confidence: 0.97,
    spam: false,
    securityStatus: "safe",
  },

  {
    id: "email-005",
    threadId: "thread-005",
    sender: "Marketing Team",
    senderEmail: "offers@example.com",
    subject: "50% discount available today",
    preview:
      "Don't miss our exclusive offer. Get 50% off your next purchase today.",
    body:
      "Don't miss our exclusive offer.\n\nGet 50% off your next purchase today.",
    timestamp: "2 hours ago",
    read: true,
    classificationCategory: "promotions",
    gmailLabels: [],
    subcategory: "Promotion",
    priority: "low",
    timeSensitive: false,
    confidence: 0.91,
    spam: false,
    securityStatus: "safe",
  },

  {
    id: "email-006",
    threadId: "thread-006",
    sender: "Unknown Sender",
    senderEmail: "security-alert@example.net",
    subject: "Urgent: Verify your account",
    preview:
      "Your account will be suspended unless you verify your information immediately.",
    body:
      "URGENT!\n\nYour account will be suspended unless you verify your information immediately.\n\nClick the link below to continue.",
    timestamp: "3 hours ago",
    read: false,
    classificationCategory: "security",
    gmailLabels: [],
    subcategory: "Phishing",
    priority: "urgent",
    timeSensitive: false,
    confidence: 0.61,
    spam: true,
    securityStatus: "suspicious",
  },
];
