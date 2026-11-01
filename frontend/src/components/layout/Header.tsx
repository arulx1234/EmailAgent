import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bell,
  Search,
  ChevronDown,
  Menu,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import {
  DISPLAY_NAME_CHANGED_EVENT,
  fetchCurrentUser,
  getSavedDisplayName,
  MAILBOX_REFRESHED_EVENT,
  type MailboxRefreshEventDetail,
  type GmailEmail,
  type GoogleUserProfile,
} from "../../services/emailApi";

const fallbackUser: GoogleUserProfile = {
  name: "Not connected",
  email: "Connect Gmail",
};

interface HeaderProps {
  onMenuClick: () => void;
}

export default function Header({ onMenuClick }: HeaderProps) {
  const navigate = useNavigate();
  const [user, setUser] = useState<GoogleUserProfile>(fallbackUser);
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const notificationsRef = useRef<HTMLDivElement>(null);
  const [notifications, setNotifications] = useState<GmailEmail[]>([]);
  const [notificationError, setNotificationError] = useState<string | null>(null);

  useEffect(() => {
    if (!isNotificationsOpen) {
      return;
    }

    function closeOnOutsideClick(event: PointerEvent) {
      if (
        event.target instanceof Node &&
        !notificationsRef.current?.contains(event.target)
      ) {
        setIsNotificationsOpen(false);
      }
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsNotificationsOpen(false);
      }
    }

    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [isNotificationsOpen]);

  useEffect(() => {
    let isMounted = true;

    const handleDisplayNameChange = (event: Event) => {
      if (event instanceof CustomEvent && typeof event.detail === "string") {
        setUser((currentUser) => ({ ...currentUser, name: event.detail }));
      }
    };

    window.addEventListener(DISPLAY_NAME_CHANGED_EVENT, handleDisplayNameChange);

    function handleMailboxRefresh(event: Event) {
      if (
        event instanceof CustomEvent &&
        event.detail &&
        typeof event.detail === "object"
      ) {
        const detail = event.detail as MailboxRefreshEventDetail;
        setNotifications(
          detail.emails.filter((email) => email.is_unread)
        );
      }
    }

    window.addEventListener(MAILBOX_REFRESHED_EVENT, handleMailboxRefresh);

    fetchCurrentUser()
      .then((profile) => {
        if (isMounted) {
          setUser({
            ...profile,
            name: getSavedDisplayName() ?? profile.name,
          });
        }
      })
      .catch(() => {
        if (isMounted) {
          setUser(fallbackUser);
        }
      });

    return () => {
      isMounted = false;
      window.removeEventListener(DISPLAY_NAME_CHANGED_EVENT, handleDisplayNameChange);
      window.removeEventListener(MAILBOX_REFRESHED_EVENT, handleMailboxRefresh);
    };
  }, []);

  function loadNotifications() {
    // The app refresh broadcasts the latest mailbox snapshot to this header.
    // Avoid starting another slow Gmail request when the bell is opened.
    setNotificationError(null);
  }

  function toggleNotifications() {
    const shouldOpen = !isNotificationsOpen;
    setIsNotificationsOpen(shouldOpen);

    if (shouldOpen) {
      setIsProfileOpen(false);
      void loadNotifications();
    }
  }

  function openNotification(email: GmailEmail) {
    setIsNotificationsOpen(false);
    navigate(`/emails?email=${encodeURIComponent(email.id)}`);
  }

  const initials = useMemo(() => {
    if (!user.name || user.name === "Not connected") {
      return "G";
    }

    const [first, second] = user.name.trim().split(/\s+/);
    return (first?.[0] ?? "").toUpperCase() + (second?.[0] ?? "").toUpperCase();
  }, [user.name]);

  return (
    <header className="fixed left-64 right-0 top-0 z-30 h-16 border-b border-slate-200/80 bg-white/75 backdrop-blur-xl max-md:left-0">
      <div className="flex h-full items-center justify-between gap-2 px-6 max-md:px-3">
        <button
          type="button"
          aria-label="Open navigation menu"
          onClick={onMenuClick}
          className="hidden shrink-0 rounded-full p-2 text-slate-600 transition hover:bg-slate-100 max-md:inline-flex"
        >
          <Menu size={21} />
        </button>

        <div className="relative w-full max-w-xl min-w-0">
          <Search
            size={18}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />

          <input
            type="text"
            placeholder="Search emails..."
            className="
              h-10 w-full rounded-xl border border-slate-200
              bg-slate-50/80 pl-10 pr-4 text-sm text-slate-700
              outline-none transition-all duration-200
              placeholder:text-slate-400 focus:border-blue-400 focus:bg-white focus:shadow-[0_0_0_4px_rgba(59,130,246,0.10)]
            "
          />
        </div>

        <div className="flex shrink-0 items-center gap-5 pl-6 max-md:gap-2 max-md:pl-1">
          <div className="relative" ref={notificationsRef}>
            <button
              type="button"
              aria-label="Notifications"
              aria-haspopup="dialog"
              aria-expanded={isNotificationsOpen}
              onClick={toggleNotifications}
              className="relative rounded-full p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
            >
              <Bell size={18} />
              {notifications.length > 0 && (
                <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white ring-2 ring-white">
                  {notifications.length > 9 ? "9+" : notifications.length}
                </span>
              )}
            </button>

            {isNotificationsOpen && (
              <section
                aria-label="Unread email notifications"
                className="absolute right-0 top-12 z-50 w-80 max-w-[calc(100vw-1rem)] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl"
              >
                <div className="border-b border-slate-100 px-4 py-3">
                  <h2 className="text-sm font-semibold text-slate-900">
                    Unread emails
                  </h2>
                  <p className="mt-0.5 text-xs text-slate-500">
                    Latest unread messages from Gmail
                  </p>
                </div>

                {notificationError ? (
                  <div className="px-4 py-5 text-sm text-red-600">
                    <p>{notificationError}</p>
                    <button
                      type="button"
                      onClick={() => void loadNotifications()}
                      className="mt-2 font-medium text-blue-700 hover:underline"
                    >
                      Try again
                    </button>
                  </div>
                ) : notifications.length === 0 ? (
                  <p className="px-4 py-6 text-center text-sm text-slate-500">
                    You have no unread emails.
                  </p>
                ) : (
                  <ul className="max-h-80 overflow-y-auto">
                    {notifications.map((email) => (
                      <li key={email.id}>
                        <button
                          type="button"
                          onClick={() => openNotification(email)}
                          className="w-full border-b border-slate-100 px-4 py-3 text-left transition hover:bg-slate-50"
                        >
                          <span className="block truncate text-sm font-medium text-slate-800">
                            {email.sender}
                          </span>
                          <span className="mt-0.5 block truncate text-sm text-slate-700">
                            {email.subject}
                          </span>
                          <span className="mt-0.5 block truncate text-xs text-slate-500">
                            {email.snippet}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            )}
          </div>

          <div className="h-6 w-px bg-slate-200" />

          <div className="relative">
            <button
              type="button"
              aria-label="Profile"
              aria-haspopup="menu"
              aria-expanded={isProfileOpen}
              onClick={() => {
                setIsProfileOpen((open) => !open);
                setIsNotificationsOpen(false);
              }}
              className="flex items-center gap-2 rounded-xl px-2 py-1.5 transition hover:bg-slate-50"
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-blue-100 to-indigo-100 text-sm font-semibold text-blue-700">
                {initials}
              </div>
              <ChevronDown
                size={16}
                className={`text-slate-400 transition-transform ${
                  isProfileOpen ? "rotate-180" : ""
                }`}
              />
            </button>

            {isProfileOpen && (
              <section
                role="menu"
                aria-label="Profile details"
                className="absolute right-0 top-12 z-50 w-72 max-w-[calc(100vw-1rem)] rounded-xl border border-slate-200 bg-white p-4 shadow-xl"
              >
                <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                  Signed in as
                </p>
                <p className="mt-2 truncate text-sm font-semibold text-slate-900">
                  {user.name}
                </p>
                <p className="mt-1 break-all text-sm text-slate-600">
                  {user.email}
                </p>
              </section>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
