import { useEffect, useState } from "react";
import { BrowserRouter } from "react-router-dom";

import Sidebar from "./components/layout/Sidebar";
import Header from "./components/layout/Header";
import PageContainer from "./components/layout/PageContainer";

import AppRoutes from "./app/routes";
import {
  CUSTOM_LABELS_STORAGE_KEY,
  fetchEmails,
  MAILBOX_REFRESHED_EVENT,
  processReplyDrafts,
  type MailboxRefreshEventDetail,
} from "./services/emailApi";

export default function App() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    let stopped = false;
    let running = false;
    let draftsRunning = false;

    async function refreshConnectedMailbox() {
      if (stopped || running) {
        return;
      }

      running = true;
      let draftStatus = "Mailbox refreshed.";
      try {
        let customLabels: string[] = [];
        try {
          const savedLabels = window.localStorage.getItem(CUSTOM_LABELS_STORAGE_KEY);
          const parsedLabels: unknown = savedLabels ? JSON.parse(savedLabels) : [];
          if (
            Array.isArray(parsedLabels) &&
            parsedLabels.every((label) => typeof label === "string")
          ) {
            customLabels = parsedLabels;
          }
        } catch {
          customLabels = [];
        }
        const response = await fetchEmails(
          50,
          "all",
          undefined,
          undefined,
          false,
          customLabels
        );
        if (!stopped) {
          const detail: MailboxRefreshEventDetail = {
            emails: response.emails,
            draftStatus,
          };
          window.dispatchEvent(
            new CustomEvent<MailboxRefreshEventDetail>(MAILBOX_REFRESHED_EVENT, { detail })
          );
        }
        if (!draftsRunning) {
          draftsRunning = true;
          void processReplyDrafts().then((result) => {
            if (result.warnings.length > 0) {
              draftStatus = result.warnings.join(" ");
            } else if (result.created_count > 0) {
              const noun = result.created_count === 1 ? "draft" : "drafts";
              draftStatus = `Created ${result.created_count} unsent ${noun} in Gmail. Review and send them manually.`;
            } else if (result.reviewed_count > 0) {
              draftStatus = `Checked ${result.reviewed_count} new Inbox message${result.reviewed_count === 1 ? "" : "s"}; none needed a reply.`;
            } else if (result.skipped_count > 0) {
              draftStatus = "Checked new Inbox messages; no additional reply drafts were needed.";
            } else {
              draftStatus = "Mailbox is up to date. No new Inbox messages to review for reply drafts.";
            }
            if (!stopped) {
              window.dispatchEvent(
                new CustomEvent<MailboxRefreshEventDetail>(MAILBOX_REFRESHED_EVENT, {
                  detail: { emails: response.emails, draftStatus },
                })
              );
            }
          }).catch(() => undefined).finally(() => {
            draftsRunning = false;
          });
        }
      } catch (error: unknown) {
        if (!stopped) {
          const detail: MailboxRefreshEventDetail = {
            emails: [],
            draftStatus:
              error instanceof Error
                ? error.message
                : "Unable to refresh the Gmail mailbox.",
          };
          window.dispatchEvent(
            new CustomEvent<MailboxRefreshEventDetail>(
              MAILBOX_REFRESHED_EVENT,
              { detail }
            )
          );
        }
      } finally {
        running = false;
      }
    }

    function refreshWhenVisible() {
      if (document.visibilityState === "visible") {
        void refreshConnectedMailbox();
      }
    }

    const intervalId = window.setInterval(
      refreshConnectedMailbox,
      60_000
    );
    document.addEventListener("visibilitychange", refreshWhenVisible);
    refreshConnectedMailbox();

    return () => {
      stopped = true;
      window.clearInterval(intervalId);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
    };
  }, []);

  return (
    <BrowserRouter>
      <>
        {isMobileMenuOpen && (
          <button
            type="button"
            aria-label="Close navigation menu"
            onClick={() => setIsMobileMenuOpen(false)}
            className="fixed inset-0 z-40 bg-slate-900/40 md:hidden"
          />
        )}

        <Sidebar
          isMobileMenuOpen={isMobileMenuOpen}
          onNavigate={() => setIsMobileMenuOpen(false)}
        />

        <Header onMenuClick={() => setIsMobileMenuOpen((open) => !open)} />

        <PageContainer>
          <AppRoutes />
        </PageContainer>
      </>
    </BrowserRouter>
  );
}
