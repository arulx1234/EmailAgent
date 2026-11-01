import { ArrowLeft, Clock } from "lucide-react";

import type { Email } from "../../types/email";

interface EmailDetailProps {
  email: Email;
  onClose: () => void;
}

export default function EmailDetail({
  email,
  onClose,
}: EmailDetailProps) {
  return (
    <article className="mx-auto max-w-4xl overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-100 px-5 py-4 sm:px-8">
        <button
          type="button"
          onClick={onClose}
          className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 transition hover:text-slate-900"
        >
          <ArrowLeft size={18} />
          Back to emails
        </button>
      </div>

      <header className="border-b border-slate-100 px-5 py-6 sm:px-8">
        <h1 className="break-words text-2xl font-semibold text-slate-900">
          {email.subject}
        </h1>

        <div className="mt-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
          <div className="min-w-0">
            <p className="break-words text-sm font-semibold text-slate-800">
              {email.sender}
            </p>
            {email.senderEmail && email.senderEmail !== email.sender && (
              <p className="mt-0.5 break-all text-sm text-slate-500">
                {email.senderEmail}
              </p>
            )}
          </div>

          <p className="inline-flex shrink-0 items-center gap-1.5 text-sm text-slate-500">
            <Clock size={15} />
            {email.timestamp}
          </p>
        </div>
      </header>

      <div className="px-5 py-7 sm:px-8 sm:py-8">
        <div className="whitespace-pre-wrap break-words text-sm leading-7 text-slate-700 [overflow-wrap:anywhere]">
          {email.body || email.preview}
        </div>
      </div>
    </article>
  );
}
