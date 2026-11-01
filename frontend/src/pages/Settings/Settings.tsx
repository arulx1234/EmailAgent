import { useEffect, useState } from "react";
import {
  Bell,
  Bot,
  CheckCircle,
  Database,
  KeyRound,
  Mail,
  Save,
  User,
} from "lucide-react";

import {
  fetchCurrentUser,
  getSavedDisplayName,
  logoutCurrentUser,
  saveDisplayName,
  startGoogleLogin,
  type GoogleUserProfile,
} from "../../services/emailApi";

export default function Settings() {
  const [autoClassify, setAutoClassify] = useState(true);
  const [securityScanning, setSecurityScanning] = useState(true);
  const [notifications, setNotifications] = useState(true);
  const [autoReview, setAutoReview] = useState(true);
  const [profile, setProfile] = useState<GoogleUserProfile>({
    name: "Not connected",
    email: "Connect Gmail",
  });

  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [isDisconnecting, setIsDisconnecting] = useState(false);

  const isConnected = profile.email !== "Connect Gmail";

  useEffect(() => {
    let isMounted = true;

    const callbackUrl = new URL(window.location.href);
    if (callbackUrl.searchParams.get("gmail") === "error") {
      const reason = callbackUrl.searchParams.get("reason");
      setConnectionError(
        reason === "expired" || reason === "state"
          ? "The Google sign-in expired before it finished. Select Connect Gmail to start a new sign-in."
          : "Google could not complete sign-in. Check your internet connection, then select Connect Gmail to try again."
      );
      callbackUrl.searchParams.delete("gmail");
      callbackUrl.searchParams.delete("reason");
      window.history.replaceState(
        {},
        "",
        `${callbackUrl.pathname}${callbackUrl.search}${callbackUrl.hash}`
      );
    }

    fetchCurrentUser()
      .then((user) => {
        if (isMounted) {
          setProfile({
            ...user,
            name: getSavedDisplayName() ?? user.name,
          });
        }
      })
      .catch(() => {
        if (isMounted) {
          setProfile({
            name: "Not connected",
            email: "Connect Gmail",
          });
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleSave = () => {
    const name = profile.name.trim();
    if (!name) {
      setSaveError("Enter a name before saving.");
      setSaved(false);
      return;
    }

    try {
      saveDisplayName(name);
      setProfile((currentProfile) => ({ ...currentProfile, name }));
      setSaveError(null);
      setSaved(true);

      window.setTimeout(() => {
        setSaved(false);
      }, 2500);
    } catch (error) {
      console.error("Unable to save the display name.", error);
      setSaveError("Could not save your name in this browser.");
      setSaved(false);
    }
  };

  const handleDisconnect = async () => {
    setIsDisconnecting(true);
    setConnectionError(null);
    try {
      await logoutCurrentUser();
      window.location.reload();
    } catch (error) {
      setConnectionError(
        error instanceof Error ? error.message : "Could not disconnect Gmail."
      );
    } finally {
      setIsDisconnecting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-100 text-gray-700">
            <User size={21} />
          </div>

          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Settings
            </h1>

            <p className="mt-1 text-sm text-gray-500">
              Configure your AI email intelligence system.
            </p>
          </div>
        </div>
      </div>

      {/* Account */}
      <section className="rounded-xl border bg-white shadow-sm">
        <div className="border-b px-6 py-5">
          <div className="flex items-center gap-3">
            <User size={19} className="text-gray-500" />

            <div>
              <h2 className="font-semibold text-gray-900">
                Account
              </h2>

              <p className="mt-1 text-xs text-gray-500">
                Your application account information.
              </p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-5 p-6 md:grid-cols-2">
          <div>
            <label htmlFor="account-name" className="text-sm font-medium text-gray-700">
              Name
            </label>

            <input
              id="account-name"
              type="text"
              value={profile.name}
              maxLength={80}
              onChange={(event) => {
                setProfile((currentProfile) => ({
                  ...currentProfile,
                  name: event.target.value,
                }));
                setSaved(false);
                setSaveError(null);
              }}
              className="mt-2 h-10 w-full rounded-lg border bg-white px-3 text-sm text-gray-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            />
          </div>

          <div>
            <label htmlFor="account-email" className="text-sm font-medium text-gray-700">
              Email
            </label>

            <input
              id="account-email"
              type="email"
              value={profile.email}
              readOnly
              aria-describedby="account-email-help"
              className="mt-2 h-10 w-full cursor-not-allowed rounded-lg border bg-gray-50 px-3 text-sm text-gray-500 outline-none"
            />
            <p id="account-email-help" className="mt-1 text-xs text-gray-500">
              Email is linked to your signed-in Google account.
            </p>
          </div>
        </div>
      </section>

      {/* Gmail Connection */}
      <section className="rounded-xl border bg-white shadow-sm">
        <div className="border-b px-6 py-5">
          <div className="flex items-center gap-3">
            <Mail size={19} className="text-gray-500" />

            <div>
              <h2 className="font-semibold text-gray-900">
                Gmail Connection
              </h2>

              <p className="mt-1 text-xs text-gray-500">
                Connect your Gmail account to process emails.
              </p>
            </div>
          </div>
        </div>

        <div className="flex flex-col justify-between gap-5 p-6 md:flex-row md:items-center">
          <div className="flex items-center gap-4">
            <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-red-50 text-red-600">
              <Mail size={22} />
            </div>

            <div>
              <p className="text-sm font-semibold text-gray-900">
                Gmail
              </p>

              <p className="mt-1 text-xs text-gray-500">
                {isConnected ? `Connected as ${profile.email}` : "Not connected yet"}
              </p>
            </div>
          </div>

          {isConnected ? (
            <button
              type="button"
              onClick={() => void handleDisconnect()}
              disabled={isDisconnecting}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-60"
            >
              {isDisconnecting ? "Disconnecting..." : "Disconnect"}
            </button>
          ) : (
            <button
              type="button"
              onClick={startGoogleLogin}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700"
            >
              Connect Gmail
            </button>
          )}
        </div>
        {connectionError && (
          <p role="alert" className="px-6 pb-5 text-sm text-red-600">
            {connectionError}
          </p>
        )}
      </section>

      {/* AI Configuration */}
      <section className="rounded-xl border bg-white shadow-sm">
        <div className="border-b px-6 py-5">
          <div className="flex items-center gap-3">
            <Bot size={19} className="text-gray-500" />

            <div>
              <h2 className="font-semibold text-gray-900">
                AI Configuration
              </h2>

              <p className="mt-1 text-xs text-gray-500">
                Control how the AI agents process emails.
              </p>
            </div>
          </div>
        </div>

        <div className="divide-y">
          {/* Auto Classification */}
          <div className="flex items-center justify-between gap-6 px-6 py-5">
            <div>
              <p className="text-sm font-medium text-gray-900">
                Automatic Classification
              </p>

              <p className="mt-1 text-xs text-gray-500">
                Automatically classify new incoming emails.
              </p>
            </div>

            <button
              type="button"
              onClick={() => setAutoClassify(!autoClassify)}
              className={`relative h-6 w-11 shrink-0 rounded-full transition ${
                autoClassify
                  ? "bg-blue-600"
                  : "bg-gray-300"
              }`}
            >
              <span
                className={`absolute top-1 h-4 w-4 rounded-full bg-white transition ${
                  autoClassify
                    ? "left-6"
                    : "left-1"
                }`}
              />
            </button>
          </div>

          {/* Security Scanning */}
          <div className="flex items-center justify-between gap-6 px-6 py-5">
            <div>
              <p className="text-sm font-medium text-gray-900">
                Security Scanning
              </p>

              <p className="mt-1 text-xs text-gray-500">
                Scan emails for spam, phishing, and suspicious content.
              </p>
            </div>

            <button
              type="button"
              onClick={() =>
                setSecurityScanning(!securityScanning)
              }
              className={`relative h-6 w-11 shrink-0 rounded-full transition ${
                securityScanning
                  ? "bg-blue-600"
                  : "bg-gray-300"
              }`}
            >
              <span
                className={`absolute top-1 h-4 w-4 rounded-full bg-white transition ${
                  securityScanning
                    ? "left-6"
                    : "left-1"
                }`}
              />
            </button>
          </div>

          {/* Automatic Review */}
          <div className="flex items-center justify-between gap-6 px-6 py-5">
            <div>
              <p className="text-sm font-medium text-gray-900">
                Automatic Review Queue
              </p>

              <p className="mt-1 text-xs text-gray-500">
                Send low-confidence classifications to human review.
              </p>
            </div>

            <button
              type="button"
              onClick={() => setAutoReview(!autoReview)}
              className={`relative h-6 w-11 shrink-0 rounded-full transition ${
                autoReview
                  ? "bg-blue-600"
                  : "bg-gray-300"
              }`}
            >
              <span
                className={`absolute top-1 h-4 w-4 rounded-full bg-white transition ${
                  autoReview
                    ? "left-6"
                    : "left-1"
                }`}
              />
            </button>
          </div>
        </div>
      </section>

      {/* Notifications */}
      <section className="rounded-xl border bg-white shadow-sm">
        <div className="border-b px-6 py-5">
          <div className="flex items-center gap-3">
            <Bell size={19} className="text-gray-500" />

            <div>
              <h2 className="font-semibold text-gray-900">
                Notifications
              </h2>

              <p className="mt-1 text-xs text-gray-500">
                Configure system notifications.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between gap-6 px-6 py-5">
          <div>
            <p className="text-sm font-medium text-gray-900">
              Security Alerts
            </p>

            <p className="mt-1 text-xs text-gray-500">
              Notify you when suspicious or dangerous emails are detected.
            </p>
          </div>

          <button
            type="button"
            onClick={() => setNotifications(!notifications)}
            className={`relative h-6 w-11 shrink-0 rounded-full transition ${
              notifications
                ? "bg-blue-600"
                : "bg-gray-300"
            }`}
          >
            <span
              className={`absolute top-1 h-4 w-4 rounded-full bg-white transition ${
                notifications
                  ? "left-6"
                  : "left-1"
              }`}
            />
          </button>
        </div>
      </section>

      {/* System */}
      <section className="rounded-xl border bg-white shadow-sm">
        <div className="border-b px-6 py-5">
          <div className="flex items-center gap-3">
            <Database size={19} className="text-gray-500" />

            <div>
              <h2 className="font-semibold text-gray-900">
                System
              </h2>

              <p className="mt-1 text-xs text-gray-500">
                Application and AI infrastructure status.
              </p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 p-6 md:grid-cols-3">
          <div className="rounded-lg bg-gray-50 p-4">
            <div className="flex items-center gap-2">
              <CheckCircle
                size={16}
                className="text-green-600"
              />

              <span className="text-xs font-medium text-gray-600">
                Backend
              </span>
            </div>

            <p className="mt-2 text-sm font-semibold text-gray-900">
              Operational
            </p>
          </div>

          <div className="rounded-lg bg-gray-50 p-4">
            <div className="flex items-center gap-2">
              <CheckCircle
                size={16}
                className="text-green-600"
              />

              <span className="text-xs font-medium text-gray-600">
                AI Agents
              </span>
            </div>

            <p className="mt-2 text-sm font-semibold text-gray-900">
              Operational
            </p>
          </div>

          <div className="rounded-lg bg-gray-50 p-4">
            <div className="flex items-center gap-2">
              <KeyRound
                size={16}
                className="text-gray-500"
              />

              <span className="text-xs font-medium text-gray-600">
                LangSmith
              </span>
            </div>

            <p className="mt-2 text-sm font-semibold text-gray-900">
              Not Connected
            </p>
          </div>
        </div>
      </section>

      {/* Save */}
      <div className="flex items-center justify-end gap-4">
        {saveError && (
          <p role="alert" className="text-sm font-medium text-red-600">
            {saveError}
          </p>
        )}

        {saved && (
          <div className="flex items-center gap-2 text-sm font-medium text-green-600">
            <CheckCircle size={17} />
            Settings saved
          </div>
        )}

        <button
          type="button"
          onClick={handleSave}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700"
        >
          <Save size={17} />
          Save Settings
        </button>
      </div>
    </div>
  );
}
