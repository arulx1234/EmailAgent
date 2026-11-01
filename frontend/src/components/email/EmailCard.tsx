import {
  Star,
  ShieldAlert,
  Clock,
} from "lucide-react";

import ClassificationBadge from "./ClassificationBadge";
import type { Email } from "../../types/email";

interface EmailCardProps {
  email: Email;
  onClick: (email: Email) => void;
}

export default function EmailCard({
  email,
  onClick,
}: EmailCardProps) {
  const getPriorityStyle = () => {
    switch (email.priority) {
      case "urgent":
        return "bg-red-50 text-red-700";

      case "high":
        return "bg-orange-50 text-orange-700";

      case "normal":
        return "bg-blue-50 text-blue-700";

      case "low":
        return "bg-gray-100 text-gray-600";

      default:
        return "bg-gray-100 text-gray-600";
    }
  };
  const classificationProvider = email.classificationProvider ?? "rules";

  return (
    <button
      onClick={() => onClick(email)}
      className="w-full border-b bg-white p-5 text-left transition hover:bg-gray-50"
    >
      <div className="flex items-start gap-4">

        {/* Unread indicator */}
        <div className="pt-2">
          <span
            className={`block h-2.5 w-2.5 rounded-full ${
              email.read
                ? "bg-gray-200"
                : "bg-blue-600"
            }`}
          />
        </div>

        {/* Sender avatar */}
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blue-100 text-sm font-semibold text-blue-700">
          {email.sender
            .split(" ")
            .map((name) => name[0])
            .slice(0, 2)
            .join("")}
        </div>

        {/* Main content */}
        <div className="min-w-0 flex-1">

          {/* Top row */}
          <div className="flex items-center justify-between gap-4">

            <div className="flex min-w-0 items-center gap-2">
              <h3
                className={`truncate text-sm ${
                  email.read
                    ? "font-medium text-gray-700"
                    : "font-bold text-gray-900"
                }`}
              >
                {email.sender}
              </h3>

              {!email.read && (
                <span className="text-xs text-blue-600">
                  New
                </span>
              )}
            </div>

            <span className="shrink-0 text-xs text-gray-400">
              {email.timestamp}
            </span>
          </div>

          {/* Subject */}
          <div className="mt-1 flex items-center gap-2">
            <h4 className="truncate text-sm font-semibold text-gray-900">
              {email.subject}
            </h4>

            {email.spam && (
              <ShieldAlert
                size={15}
                className="shrink-0 text-red-500"
              />
            )}
          </div>

          {/* Preview */}
          <p className="mt-1 line-clamp-1 text-sm text-gray-500">
            {email.preview}
          </p>

          {/* Bottom information */}
          <div className="mt-3 flex flex-wrap items-center gap-2">

            <ClassificationBadge category={email.classificationCategory} />

            {email.gmailLabels.map((categoryLabel) => (
              <ClassificationBadge
                key={categoryLabel}
                category={categoryLabel}
              />
            ))}

            {/* Priority */}
            <span
              title={[
                email.priorityReason,
                email.deadline ? `Deadline: ${email.deadline}` : null,
              ]
                .filter(Boolean)
                .join(" ")}
              className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${getPriorityStyle()}`}
            >
              <Clock size={12} />

              {email.priority.toUpperCase()}
              {email.timeSensitive && " · TIME-SENSITIVE"}
            </span>
            {email.timeSensitive && email.deadline && (
              <span className="text-xs font-medium text-orange-700">
                Deadline: {email.deadline}
              </span>
            )}

            {/* Confidence */}
            <span
              title={classificationProvider === "rules"
                ? "Local keyword rules were used because no AI provider was available."
                : "Classified by an AI provider."}
              className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-600"
            >
              {classificationProvider === "rules"
                ? "Rules"
                : `AI ${Math.round(email.confidence * 100)}%`}
            </span>

            {/* Security */}
            {email.securityStatus === "suspicious" && (
              <span className="inline-flex items-center gap-1 rounded-full bg-orange-50 px-2.5 py-1 text-xs font-medium text-orange-700">
                <ShieldAlert size={12} />
                Suspicious
              </span>
            )}
          </div>
        </div>

        {/* Star */}
        <div className="pt-1">
          <Star
            size={18}
            className="text-gray-300 transition hover:fill-yellow-400 hover:text-yellow-400"
          />
        </div>
      </div>
    </button>
  );
}
