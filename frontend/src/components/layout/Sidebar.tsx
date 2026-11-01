import { useState, type FormEvent } from "react";
import {
  CUSTOM_LABELS_CHANGED_EVENT,
  CUSTOM_LABELS_STORAGE_KEY,
  createGmailLabel,
  deleteGmailLabel,
  GMAIL_LABELS_SYNCED_EVENT,
  syncGmailLabel,
} from "../../services/emailApi";
import {
  Mail,
  Archive,
  BarChart3,
  Settings,
  Inbox,
  Plus,
  Tag,
  X,
  RefreshCw,
} from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";

const navigation = [
  {
    name: "Emails",
    path: "/emails",
    icon: Mail,
  },
  {
    name: "Spam",
    path: "/emails?folder=spam",
    icon: Archive,
  },
  {
    name: "Analytics",
    path: "/analytics",
    icon: BarChart3,
  },
  {
    name: "Settings",
    path: "/settings",
    icon: Settings,
  },
];

interface SidebarProps {
  isMobileMenuOpen: boolean;
  onNavigate: () => void;
}

function loadCustomLabels(): { labels: string[]; error: string | null } {
  try {
    const storedLabels = window.localStorage.getItem(CUSTOM_LABELS_STORAGE_KEY);
    if (!storedLabels) {
      return { labels: [], error: null };
    }

    const parsedLabels: unknown = JSON.parse(storedLabels);
    if (
      !Array.isArray(parsedLabels) ||
      !parsedLabels.every((label) => typeof label === "string")
    ) {
      throw new Error("Saved labels must be a list of names.");
    }

    return { labels: parsedLabels, error: null };
  } catch (error) {
    console.error("Unable to load custom labels.", error);
    return { labels: [], error: "Saved labels could not be loaded." };
  }
}

export default function Sidebar({
  isMobileMenuOpen,
  onNavigate,
}: SidebarProps) {
  const location = useLocation();
  const locationParams = new URLSearchParams(location.search);
  const selectedLabel = locationParams.get("label");
  const spamFolderSelected = locationParams.get("folder") === "spam";
  const [storedLabels] = useState(loadCustomLabels);
  const [labels, setLabels] = useState(storedLabels.labels);
  const [storageError, setStorageError] = useState(storedLabels.error);
  const [isAddingLabel, setIsAddingLabel] = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const [formError, setFormError] = useState("");
  const [isCreatingLabel, setIsCreatingLabel] = useState(false);
  const [syncingLabel, setSyncingLabel] = useState<string | null>(null);
  const [removingLabel, setRemovingLabel] = useState<string | null>(null);
  const [syncStatus, setSyncStatus] = useState<string | null>(null);

  function saveLabels(updatedLabels: string[]) {
    try {
      window.localStorage.setItem(
        CUSTOM_LABELS_STORAGE_KEY,
        JSON.stringify(updatedLabels)
      );
      setLabels(updatedLabels);
      setStorageError(null);
      window.dispatchEvent(
        new CustomEvent<string[]>(CUSTOM_LABELS_CHANGED_EVENT, {
          detail: updatedLabels,
        })
      );
      return true;
    } catch (error) {
      console.error("Unable to save custom labels.", error);
      setStorageError("Labels could not be saved in this browser.");
      return false;
    }
  }

  async function handleAddLabel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const label = newLabel.trim();

    if (!label) {
      setFormError("Enter a label name.");
      return;
    }
    if (label.length > 30) {
      setFormError("Label names must be 30 characters or fewer.");
      return;
    }
    if (labels.some((existingLabel) => existingLabel.toLowerCase() === label.toLowerCase())) {
      setFormError("That label already exists.");
      return;
    }

    setIsCreatingLabel(true);
    setFormError("");
    setSyncStatus(null);
    try {
      const gmailLabel = await createGmailLabel(label);
      if (saveLabels([...labels, gmailLabel.name])) {
        setNewLabel("");
        setFormError("");
        setIsAddingLabel(false);
        try {
          const result = await syncGmailLabel(gmailLabel.name);
          setSyncStatus(
            `${result.label_name}: matched ${result.matched_count} emails` +
              (result.removed_count > 0
                ? `, removed ${result.removed_count} unrelated labels.`
                : ".")
          );
          window.dispatchEvent(
            new CustomEvent<string>(GMAIL_LABELS_SYNCED_EVENT, {
              detail: gmailLabel.name,
            })
          );
        } catch (error) {
          setStorageError(
            error instanceof Error
              ? `Label created, but its matching Gmail messages could not be synced: ${error.message}`
              : "Label created, but its matching Gmail messages could not be synced."
          );
        }
      } else {
        setFormError("The Gmail label was created, but could not be saved in this browser.");
      }
    } catch (error) {
      setFormError(
        error instanceof Error ? error.message : "Unable to create Gmail label."
      );
    } finally {
      setIsCreatingLabel(false);
    }
  }

  async function handleSyncLabel(label: string) {
    setSyncingLabel(label);
    setStorageError(null);
    setSyncStatus(null);
    try {
      const result = await syncGmailLabel(label);
      setSyncStatus(
        `${result.label_name}: matched ${result.matched_count} emails` +
          (result.removed_count > 0
            ? `, removed ${result.removed_count} unrelated labels.`
            : ".")
      );
      window.dispatchEvent(
        new CustomEvent<string>(GMAIL_LABELS_SYNCED_EVENT, { detail: label })
      );
    } catch (error) {
      setStorageError(
        error instanceof Error
          ? `Could not recheck ${label}: ${error.message}`
          : `Could not recheck ${label}.`
      );
    } finally {
      setSyncingLabel(null);
    }
  }

  async function handleRemoveLabel(labelToRemove: string) {
    setRemovingLabel(labelToRemove);
    setStorageError(null);
    setSyncStatus(null);
    try {
      await deleteGmailLabel(labelToRemove);
      if (saveLabels(labels.filter((label) => label !== labelToRemove))) {
        setSyncStatus(`${labelToRemove} was deleted from Gmail.`);
      }
    } catch (error) {
      setStorageError(
        error instanceof Error
          ? `Could not delete ${labelToRemove}: ${error.message}`
          : `Could not delete ${labelToRemove} from Gmail.`
      );
    } finally {
      setRemovingLabel(null);
    }
  }

  return (
    <aside
      aria-label="Sidebar navigation"
      className={`fixed left-0 top-0 z-50 h-screen w-64 border-r border-slate-200/80 bg-white/95 shadow-[6px_0_30px_rgba(15,23,42,0.04)] backdrop-blur-xl transition-transform duration-200 md:z-40 md:bg-white/80 md:translate-x-0 ${
        isMobileMenuOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
      }`}
    >
      <div className="flex h-18 items-center gap-3 border-b border-slate-200 px-6 py-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-600 via-indigo-600 to-violet-600 text-white shadow-lg shadow-blue-500/20">
          <Inbox size={20} />
        </div>

        <div>
          <h1 className="text-base font-semibold tracking-tight text-slate-900">
            AI Mail
          </h1>

          <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">
            Intelligence
          </p>
        </div>
      </div>

      <div className="h-[calc(100vh-10rem)] overflow-y-auto p-4">
        <nav aria-label="Main navigation" className="space-y-1">
          {navigation.map((item) => {
            const Icon = item.icon;

            return (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={onNavigate}
                className={({ isActive }) => {
                  const selected =
                    isActive &&
                    (item.name === "Spam"
                      ? spamFolderSelected
                      : item.name === "Emails"
                        ? !spamFolderSelected
                        : true);

                  return (
                  `
                flex items-center gap-3 rounded-xl px-3 py-2.5
                text-sm font-medium transition-all duration-200
                ${
                  selected
                    ? "bg-gradient-to-r from-blue-50 to-indigo-50 text-blue-700 shadow-sm ring-1 ring-blue-100"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                }
                `
                  );
                }}
              >
                <Icon size={18} />

                <span>{item.name}</span>
              </NavLink>
            );
          })}
        </nav>

        <section aria-labelledby="sidebar-labels-heading" className="mt-7">
          <div className="mb-2 flex items-center justify-between px-3">
            <h2
              id="sidebar-labels-heading"
              className="text-xs font-semibold uppercase tracking-wider text-slate-400"
            >
              Labels
            </h2>
            <button
              type="button"
              onClick={() => {
                setIsAddingLabel(true);
                setFormError("");
              }}
              aria-label="Add label"
              title="Add label"
              className="rounded-md p-1 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
            >
              <Plus size={16} />
            </button>
          </div>

          {labels.map((label) => (
            <div
              key={label}
              className="group flex items-center gap-3 rounded-xl px-3 py-2 text-sm text-slate-600"
            >
              <NavLink
                to={`/emails?label=${encodeURIComponent(label)}`}
                onClick={onNavigate}
                className={`flex min-w-0 flex-1 items-center gap-3 truncate rounded-md ${
                  selectedLabel === label
                    ? "font-medium text-blue-700"
                    : "hover:text-slate-900"
                }`}
                title={`Show emails relevant to ${label}`}
              >
                <Tag size={16} className="shrink-0 text-slate-400" />
                <span className="min-w-0 truncate">{label}</span>
              </NavLink>
              <button
                type="button"
                onClick={() => void handleSyncLabel(label)}
                disabled={syncingLabel !== null}
                aria-label={`Recheck emails for ${label}`}
                title={`Recheck emails for ${label}`}
                className="rounded p-1 text-slate-400 opacity-0 transition hover:bg-slate-100 hover:text-blue-600 focus:opacity-100 group-hover:opacity-100 disabled:cursor-wait disabled:opacity-50"
              >
                <RefreshCw
                  size={14}
                  className={syncingLabel === label ? "animate-spin" : ""}
                />
              </button>
              <button
                type="button"
                onClick={() => void handleRemoveLabel(label)}
                disabled={removingLabel !== null}
                aria-label={`Remove ${label} label`}
                title={`Remove ${label}`}
                className="rounded p-1 text-slate-400 opacity-0 transition hover:bg-slate-100 hover:text-red-600 focus:opacity-100 group-hover:opacity-100 disabled:cursor-wait disabled:opacity-50"
              >
                <X size={14} />
              </button>
            </div>
          ))}

          {isAddingLabel && (
            <form onSubmit={handleAddLabel} className="mt-2 px-2">
              <label
                htmlFor="new-sidebar-label"
                className="mb-1 block px-1 text-xs font-medium text-slate-600"
              >
                Label name
              </label>
              <input
                autoFocus
                id="new-sidebar-label"
                type="text"
                value={newLabel}
                onChange={(event) => {
                  setNewLabel(event.target.value);
                  setFormError("");
                }}
                maxLength={30}
                placeholder="e.g. Work"
                className="h-9 w-full rounded-lg border border-slate-200 bg-white px-2.5 text-sm text-slate-800 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
              />
              {formError && (
                <p role="alert" className="mt-1 text-xs text-red-600">
                  {formError}
                </p>
              )}
              <div className="mt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => {
                    if (isCreatingLabel) return;
                    setIsAddingLabel(false);
                    setNewLabel("");
                    setFormError("");
                  }}
                  disabled={isCreatingLabel}
                  className="rounded-lg px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreatingLabel}
                  className="rounded-lg bg-blue-600 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
                >
                  {isCreatingLabel ? "Adding..." : "Add"}
                </button>
              </div>
            </form>
          )}

          {storageError && (
            <p role="alert" className="mt-2 px-3 text-xs text-red-600">
              {storageError}
            </p>
          )}
          {syncStatus && (
            <p role="status" className="mt-2 px-3 text-xs text-emerald-700">
              {syncStatus}
            </p>
          )}
        </section>
      </div>

      <div className="absolute bottom-5 left-4 right-4">
        <div className="rounded-2xl border border-emerald-100 bg-gradient-to-r from-emerald-50 to-teal-50 p-3 shadow-sm">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,0.15)]" />

            <span className="text-xs font-semibold text-emerald-700">
              AI System Online
            </span>
          </div>

          <p className="mt-1 text-xs text-slate-600">
            All agents operational
          </p>
        </div>
      </div>
    </aside>
  );
}
