import { useState } from "react";
import { Search, SlidersHorizontal } from "lucide-react";

interface EmailFiltersProps {
  search: string;
  selectedLabel: string;
  classificationCategory: string;
  customCategories: string[];
  priority: string;
  readStatus: "all" | "unread" | "read";
  timeSensitiveOnly: boolean;
  needsAttentionOnly: boolean;
  onSearchChange: (value: string) => void;
  onSelectedLabelChange: (value: string) => void;
  onClassificationCategoryChange: (value: string) => void;
  onPriorityChange: (value: string) => void;
  onReadStatusChange: (value: "all" | "unread" | "read") => void;
  onTimeSensitiveOnlyChange: (value: boolean) => void;
  onNeedsAttentionOnlyChange: (value: boolean) => void;
}

export default function EmailFilters({
  search,
  selectedLabel,
  classificationCategory,
  customCategories,
  priority,
  readStatus,
  timeSensitiveOnly,
  needsAttentionOnly,
  onSearchChange,
  onSelectedLabelChange,
  onClassificationCategoryChange,
  onPriorityChange,
  onReadStatusChange,
  onTimeSensitiveOnlyChange,
  onNeedsAttentionOnlyChange,
}: EmailFiltersProps) {
  const [isMoreFiltersOpen, setIsMoreFiltersOpen] = useState(false);

  return (
    <div className="rounded-xl border bg-white p-3 shadow-sm">
      <div className="flex flex-col gap-2 lg:flex-row lg:items-center">

        {/* Search */}
        <div className="relative flex-1">
          <Search
            size={18}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
          />

          <input
            type="text"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search emails..."
            className="
              h-9 w-full rounded-lg border
              bg-gray-50 pl-10 pr-4
              text-sm text-gray-900
              outline-none
              transition
              placeholder:text-gray-400
              focus:border-blue-500
              focus:bg-white
            "
          />
        </div>

        {/* Added Gmail labels */}
        <select
          value={selectedLabel}
          onChange={(e) => onSelectedLabelChange(e.target.value)}
          className="
            h-9 rounded-lg border
            bg-white px-3
            text-sm text-gray-700
            outline-none
            focus:border-blue-500
          "
        >
          <option value="all">All labels</option>
          {customCategories.length > 0 && (
            <optgroup label="Your Gmail labels">
              {customCategories.map((customCategory) => (
                <option key={customCategory} value={customCategory}>
                  {customCategory}
                </option>
              ))}
            </optgroup>
          )}
          {customCategories.length === 0 && (
            <option value="all" disabled>No added labels yet</option>
          )}
        </select>

        {/* AI classification category */}
        <select
          aria-label="AI classification category"
          value={classificationCategory}
          onChange={(event) => onClassificationCategoryChange(event.target.value)}
          className="h-9 rounded-lg border bg-white px-3 text-sm text-gray-700 outline-none focus:border-blue-500"
        >
          <option value="all">All AI categories</option>
          <option value="work">Work</option>
          <option value="personal">Personal</option>
          <option value="finance">Finance</option>
          <option value="promotions">Promotions</option>
          <option value="security">Security</option>
          <option value="other">Other</option>
        </select>

        {/* Priority */}
        <select
          value={priority}
          onChange={(e) => onPriorityChange(e.target.value)}
          className="
            h-9 rounded-lg border
            bg-white px-3
            text-sm text-gray-700
            outline-none
            focus:border-blue-500
          "
        >
          <option value="all">All Priorities</option>
          <option value="urgent">Urgent</option>
          <option value="high">High</option>
          <option value="normal">Normal</option>
          <option value="low">Low</option>
        </select>

        {/* Filter button */}
        <button
          type="button"
          aria-expanded={isMoreFiltersOpen}
          aria-controls="email-more-filters"
          onClick={() => setIsMoreFiltersOpen((open) => !open)}
          className="
            flex h-9 items-center
            justify-center gap-2
            rounded-lg border
            px-3
            text-sm font-medium
            text-gray-700
            transition
            hover:bg-gray-50
          "
        >
          <SlidersHorizontal size={16} />
          More Filters
          {(readStatus !== "all" || timeSensitiveOnly || needsAttentionOnly) && (
            <span className="h-2 w-2 rounded-full bg-blue-600" aria-label="Additional filters active" />
          )}
        </button>
      </div>

      {isMoreFiltersOpen && (
        <div
          id="email-more-filters"
          className="mt-3 grid gap-3 border-t border-slate-100 pt-3 sm:grid-cols-2 lg:grid-cols-3"
        >
          <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
            Read status
            <select
              value={readStatus}
              onChange={(event) => {
                const value = event.target.value;
                if (value === "all" || value === "unread" || value === "read") {
                  onReadStatusChange(value);
                }
              }}
              className="h-9 rounded-lg border bg-white px-3 text-sm font-normal text-gray-700 outline-none focus:border-blue-500"
            >
              <option value="all">All messages</option>
              <option value="unread">Unread only</option>
              <option value="read">Read only</option>
            </select>
          </label>

          <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={timeSensitiveOnly}
              onChange={(event) =>
                onTimeSensitiveOnlyChange(event.target.checked)
              }
              className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
            />
            Has a deadline
          </label>

          <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={needsAttentionOnly}
              onChange={(event) =>
                onNeedsAttentionOnlyChange(event.target.checked)
              }
              className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
            />
            High or urgent priority
          </label>
        </div>
      )}
    </div>
  );
}
