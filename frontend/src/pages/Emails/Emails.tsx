import { useEffect, useMemo, useRef, useState } from "react";
import { Mail, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";

import EmailFilters from "../../components/email/EmailFilters";
import EmailList from "../../components/email/EmailList";
import {
  CUSTOM_LABELS_CHANGED_EVENT,
  CUSTOM_LABELS_STORAGE_KEY,
  fetchEmails,
  GMAIL_LABELS_SYNCED_EVENT,
  type GmailEmail,
} from "../../services/emailApi";
import type { Email } from "../../types/email";
import EmailDetail from "../../components/email/EmailDetail";
import { useSearchParams } from "react-router-dom";

function toEmail(gmailEmail: GmailEmail, selectedLabel?: string): Email {
  const senderHeader = gmailEmail.sender;
  const senderEmail = senderHeader.match(/<([^>]+)>/)?.[1] ?? senderHeader;
  const sender = senderHeader.replace(/<[^>]+>/, "").replace(/"/g, "").trim();
  const parsedDate = new Date(gmailEmail.date);

  return {
    id: gmailEmail.id,
    threadId: gmailEmail.thread_id ?? gmailEmail.id,
    sender: sender || senderHeader,
    senderEmail,
    subject: gmailEmail.subject,
    preview: gmailEmail.snippet,
    body: gmailEmail.body || gmailEmail.snippet,
    timestamp: Number.isNaN(parsedDate.getTime())
      ? gmailEmail.date
      : parsedDate.toLocaleString(),
    read: !gmailEmail.is_unread,
    classificationCategory: gmailEmail.classification.category,
    gmailLabels:
      gmailEmail.category_labels ??
      (gmailEmail.category_label
        ? [gmailEmail.category_label]
        : selectedLabel
          ? [selectedLabel]
          : []),
    priority: gmailEmail.classification.priority,
    timeSensitive: gmailEmail.classification.time_sensitive,
    deadline: gmailEmail.classification.deadline,
    priorityReason: gmailEmail.classification.priority_reason,
    confidence: gmailEmail.classification.confidence,
    classificationProvider: gmailEmail.classification.provider ?? "rules",
    spam: gmailEmail.labels.includes("SPAM"),
    securityStatus: "unknown",
  };
}

export default function Emails() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeLabel = searchParams.get("label")?.trim() || null;
  const activeFolder = searchParams.get("folder") === "spam" ? "spam" : "all";
  const selectedEmailId = searchParams.get("email");
  const [search, setSearch] = useState("");
  const [selectedLabel, setSelectedLabel] = useState("all");
  const [customCategories, setCustomCategories] = useState<string[]>(() => {
    try {
      const storedCategories = window.localStorage.getItem(
        CUSTOM_LABELS_STORAGE_KEY
      );
      if (!storedCategories) return [];
      const parsedCategories: unknown = JSON.parse(storedCategories);
      if (
        !Array.isArray(parsedCategories) ||
        !parsedCategories.every((value) => typeof value === "string")
      ) {
        throw new Error("Saved custom categories must be a list of names.");
      }
      return parsedCategories;
    } catch (error) {
      console.error("Unable to load custom categories.", error);
      return [];
    }
  });
  const [priority, setPriority] = useState("all");
  const [readStatus, setReadStatus] = useState<"all" | "unread" | "read">(
    "all"
  );
  const [timeSensitiveOnly, setTimeSensitiveOnly] = useState(false);
  const [needsAttentionOnly, setNeedsAttentionOnly] = useState(false);
  const [emails, setEmails] = useState<Email[]>([]);
  const [classificationCategory, setClassificationCategory] = useState("all");
  const [retryCount, setRetryCount] = useState(0);
  const forceRefreshNextFetch = useRef(false);
  const [completedQueryKey, setCompletedQueryKey] = useState<string | null>(
    null
  );
  const [queryError, setQueryError] = useState<{
    key: string;
    message: string;
  } | null>(null);
  const [queryWarnings, setQueryWarnings] = useState<{
    key: string;
    messages: string[];
  } | null>(null);
  const draftStatus =
    "Inbox checks run in the background. Select Refresh to update this list.";
  const selectedCategoryLabel =
    customCategories.find(
      (customCategory) =>
        customCategory.toLowerCase() === selectedLabel.toLowerCase()
    ) ?? undefined;
  const queryKey = JSON.stringify([
    activeFolder,
    activeLabel,
    selectedLabel,
    selectedCategoryLabel,
    retryCount,
  ]);
  const isLoading = completedQueryKey !== queryKey;
  const error = queryError?.key === queryKey ? queryError.message : null;
  const warnings =
    queryWarnings?.key === queryKey ? queryWarnings.messages : [];
  const selectedEmail =
    emails.find((email) => email.id === selectedEmailId) ?? null;

  function refreshEmails() {
    forceRefreshNextFetch.current = true;
    setRetryCount((count) => count + 1);
  }

  useEffect(() => {
    let cancelled = false;
    const forceRefresh = forceRefreshNextFetch.current;
    forceRefreshNextFetch.current = false;

    fetchEmails(
      25,
      activeFolder,
      activeLabel ?? undefined,
      selectedCategoryLabel,
      forceRefresh,
      customCategories
    )
      .then((response) => {
        if (!cancelled) {
          const loadedEmails = response.emails.map((email) =>
            toEmail(email, selectedCategoryLabel ?? activeLabel ?? undefined)
          );
          setEmails(loadedEmails);
          setQueryWarnings({
            key: queryKey,
            messages: response.warnings ?? [],
          });
        }
      })
      .catch((fetchError: unknown) => {
        if (!cancelled) {
          setQueryError({
            key: queryKey,
            message:
              fetchError instanceof Error
                ? fetchError.message
                : "Unable to load emails.",
          });
        }
      })
      .finally(() => {
        if (!cancelled) {
          setCompletedQueryKey(queryKey);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [
    activeFolder,
    activeLabel,
    customCategories,
    selectedLabel,
    selectedCategoryLabel,
    retryCount,
    queryKey,
  ]);

  useEffect(() => {
    function handleCustomCategoriesChanged(event: Event) {
      const updatedCategories = (event as CustomEvent<string[]>).detail;
      setCustomCategories(updatedCategories);
      setSelectedLabel((currentLabel) =>
        updatedCategories.some(
          (customCategory) =>
            customCategory.toLowerCase() === currentLabel.toLowerCase()
        )
          ? currentLabel
          : "all"
      );
    }

    window.addEventListener(
      CUSTOM_LABELS_CHANGED_EVENT,
      handleCustomCategoriesChanged
    );
    return () =>
      window.removeEventListener(
        CUSTOM_LABELS_CHANGED_EVENT,
        handleCustomCategoriesChanged
      );
  }, []);

  useEffect(() => {
    function handleLabelsSynced() {
      forceRefreshNextFetch.current = true;
      setRetryCount((count) => count + 1);
    }

    window.addEventListener(GMAIL_LABELS_SYNCED_EVENT, handleLabelsSynced);
    return () =>
      window.removeEventListener(GMAIL_LABELS_SYNCED_EVENT, handleLabelsSynced);
  }, []);

  const filteredEmails = useMemo(() => {
    return emails.filter((email) => {
      const searchTerm = search.toLowerCase().trim();

      const matchesSearch =
        searchTerm === "" ||
        email.sender.toLowerCase().includes(searchTerm) ||
        email.senderEmail.toLowerCase().includes(searchTerm) ||
        email.subject.toLowerCase().includes(searchTerm) ||
        email.preview.toLowerCase().includes(searchTerm);

      const matchesPriority =
        priority === "all" ||
        email.priority === priority;
      const matchesClassificationCategory =
        classificationCategory === "all" ||
        email.classificationCategory === classificationCategory;

      const matchesReadStatus =
        readStatus === "all" ||
        (readStatus === "unread" && !email.read) ||
        (readStatus === "read" && email.read);
      const matchesTimeSensitive =
        !timeSensitiveOnly || email.timeSensitive;
      const matchesNeedsAttention =
        !needsAttentionOnly ||
        email.priority === "high" ||
        email.priority === "urgent";

      return (
        matchesSearch &&
        matchesClassificationCategory &&
        matchesPriority &&
        matchesReadStatus &&
        matchesTimeSensitive &&
        matchesNeedsAttention
      );
    });
  }, [
    emails,
    search,
    selectedLabel,
    classificationCategory,
    priority,
    readStatus,
    timeSensitiveOnly,
    needsAttentionOnly,
  ]);

  function closeSelectedEmail() {
    setSearchParams((params) => {
      params.delete("email");
      return params;
    }, { replace: true });
  }

  if (selectedEmail) {
    return (
      <div className="space-y-4">
        <p role="status" className="text-sm text-slate-500">
          {draftStatus}
        </p>
        <EmailDetail email={selectedEmail} onClose={closeSelectedEmail} />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Page Header */}
      <div>
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-700">
              <Mail size={21} />
            </div>

            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                Emails
              </h1>

              <p className="mt-1 text-sm text-gray-500">
                {activeFolder === "spam"
                  ? "Gmail messages currently in your Spam folder."
                  : "View emails organized by your added Gmail labels."}
              </p>
              {activeLabel && (
                <p className="mt-1 text-sm font-medium text-blue-700">
                  Emails matching "{activeLabel}"
                </p>
              )}
            </div>
          </div>

          <button
            type="button"
            onClick={refreshEmails}
            disabled={isLoading}
            className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RefreshCw size={16} className={isLoading ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </div>
      <p role="status" className="text-sm text-slate-500">
        {draftStatus}
      </p>

      {/* Filters */}
      <EmailFilters
        search={search}
        selectedLabel={selectedLabel}
        classificationCategory={classificationCategory}
        customCategories={customCategories}
        priority={priority}
        readStatus={readStatus}
        timeSensitiveOnly={timeSensitiveOnly}
        needsAttentionOnly={needsAttentionOnly}
        onSearchChange={setSearch}
        onSelectedLabelChange={setSelectedLabel}
        onClassificationCategoryChange={setClassificationCategory}
        onPriorityChange={setPriority}
        onReadStatusChange={setReadStatus}
        onTimeSensitiveOnlyChange={setTimeSensitiveOnly}
        onNeedsAttentionOnlyChange={setNeedsAttentionOnly}
      />

      {/* Results Count */}
      {!isLoading && !error && <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          Showing{" "}
          <span className="font-medium text-gray-900">
            {filteredEmails.length}
          </span>{" "}
          of{" "}
          <span className="font-medium text-gray-900">
            {emails.length}
          </span>{" "}
          emails
        </p>

        {(search ||
          selectedLabel !== "all" ||
          classificationCategory !== "all" ||
          priority !== "all" ||
          readStatus !== "all" ||
          timeSensitiveOnly ||
          needsAttentionOnly) && (
          <button
            type="button"
            onClick={() => {
              setSearch("");
              setSelectedLabel("all");
              setClassificationCategory("all");
              setPriority("all");
              setReadStatus("all");
              setTimeSensitiveOnly(false);
              setNeedsAttentionOnly(false);
            }}
            className="text-sm font-medium text-blue-600 hover:text-blue-700"
          >
            Clear filters
          </button>
        )}
      </div>}

      {/* Email Content */}
      {warnings.length > 0 && (
        <div
          role="status"
          className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
        >
          {warnings.join(" ")}
        </div>
      )}
      {isLoading ? (
        <div className="rounded-xl border bg-white px-6 py-12 text-center text-sm text-gray-500">
          Loading emails...
        </div>
      ) : error ? (
        <div className="rounded-xl border bg-white px-6 py-12 text-center">
          <p className="text-sm text-red-600">{error}</p>
          {error.includes("Connect Gmail") && (
            <Link
              to="/settings"
              className="mt-4 inline-flex rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700"
            >
              Connect Gmail
            </Link>
          )}
          <button
            type="button"
            onClick={refreshEmails}
            className="mt-4 text-sm font-medium text-blue-600 hover:text-blue-700"
          >
            Try again
          </button>
        </div>
      ) : (
        <EmailList
          emails={filteredEmails}
          onSelectEmail={(email) => {
            setSearchParams((params) => {
              params.set("email", email.id);
              return params;
            });
          }}
        />
      )}
    </div>
  );
}
