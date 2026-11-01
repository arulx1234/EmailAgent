import EmailCard from "./EmailCard";
import type { Email } from "../../types/email";
import { mockEmails } from "../../data/mockEmails";

interface EmailListProps {
  emails?: Email[];
  onSelectEmail: (email: Email) => void;
}

export default function EmailList({
  emails,
  onSelectEmail,
}: EmailListProps) {
  const emailsToRender = emails ?? mockEmails;

  return (
    <div className="overflow-hidden rounded-xl border bg-white shadow-sm">
      {emailsToRender.length > 0 ? (
        emailsToRender.map((email) => (
          <EmailCard
            key={email.id}
            email={email}
            onClick={onSelectEmail}
          />
        ))
      ) : (
        <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gray-100">
            <span className="text-xl text-gray-400">✉</span>
          </div>

          <h3 className="mt-4 text-sm font-semibold text-gray-900">
            No emails found
          </h3>

          <p className="mt-1 text-sm text-gray-500">
            Try changing your search or filters.
          </p>
        </div>
      )}
    </div>
  );
}