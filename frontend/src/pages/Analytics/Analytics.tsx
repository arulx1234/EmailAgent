import {
  Activity,
  BarChart3,
  CheckCircle,
  Clock,
  Mail,
  ShieldAlert,
  TrendingUp,
} from "lucide-react";

const classificationData = [
  { category: "Customer Support", count: 342, percentage: 27 },
  { category: "Shopping", count: 286, percentage: 23 },
  { category: "Work", count: 241, percentage: 19 },
  { category: "Finance", count: 178, percentage: 14 },
  { category: "Marketing", count: 126, percentage: 10 },
  { category: "Security", count: 75, percentage: 6 },
];

const activityData = [
  { day: "Mon", emails: 182 },
  { day: "Tue", emails: 241 },
  { day: "Wed", emails: 198 },
  { day: "Thu", emails: 276 },
  { day: "Fri", emails: 231 },
  { day: "Sat", emails: 142 },
  { day: "Sun", emails: 178 },
];

export default function Analytics() {
  const totalEmails = classificationData.reduce(
    (total, item) => total + item.count,
    0
  );

  const maxActivity = Math.max(
    ...activityData.map((item) => item.emails)
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-700">
            <BarChart3 size={21} />
          </div>

          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Analytics
            </h1>

            <p className="mt-1 text-sm text-gray-500">
              Monitor email processing, classification, and AI performance.
            </p>
          </div>
        </div>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-xl border bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">
                Emails Processed
              </p>

              <p className="mt-1 text-2xl font-bold text-gray-900">
                1,248
              </p>

              <p className="mt-2 flex items-center gap-1 text-xs font-medium text-green-600">
                <TrendingUp size={13} />
                +12.4% this week
              </p>
            </div>

            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
              <Mail size={20} />
            </div>
          </div>
        </div>

        <div className="rounded-xl border bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">
                Classification Accuracy
              </p>

              <p className="mt-1 text-2xl font-bold text-gray-900">
                96.8%
              </p>

              <p className="mt-2 flex items-center gap-1 text-xs font-medium text-green-600">
                <TrendingUp size={13} />
                +1.8% this week
              </p>
            </div>

            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-50 text-green-600">
              <CheckCircle size={20} />
            </div>
          </div>
        </div>

        <div className="rounded-xl border bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">
                Avg Processing Time
              </p>

              <p className="mt-1 text-2xl font-bold text-gray-900">
                1.4s
              </p>

              <p className="mt-2 flex items-center gap-1 text-xs font-medium text-green-600">
                <TrendingUp size={13} />
                8.2% faster
              </p>
            </div>

            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-50 text-purple-600">
              <Clock size={20} />
            </div>
          </div>
        </div>

        <div className="rounded-xl border bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">
                Security Alerts
              </p>

              <p className="mt-1 text-2xl font-bold text-gray-900">
                34
              </p>

              <p className="mt-2 text-xs font-medium text-orange-600">
                2.7% of processed emails
              </p>
            </div>

            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-50 text-red-600">
              <ShieldAlert size={20} />
            </div>
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        {/* Email Activity */}
        <div className="rounded-xl border bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-gray-900">
                Email Activity
              </h2>

              <p className="mt-1 text-xs text-gray-500">
                Emails processed over the last 7 days
              </p>
            </div>

            <Activity
              size={20}
              className="text-blue-600"
            />
          </div>

          <div className="mt-8 flex h-56 items-end justify-between gap-3">
            {activityData.map((item) => (
              <div
                key={item.day}
                className="flex h-full flex-1 flex-col items-center justify-end gap-2"
              >
                <span className="text-xs font-medium text-gray-500">
                  {item.emails}
                </span>

                <div
                  className="w-full max-w-10 rounded-t-md bg-blue-500 transition hover:bg-blue-600"
                  style={{
                    height: `${(item.emails / maxActivity) * 75}%`,
                  }}
                />

                <span className="text-xs text-gray-400">
                  {item.day}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Classification Distribution */}
        <div className="rounded-xl border bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-gray-900">
                Classification Distribution
              </h2>

              <p className="mt-1 text-xs text-gray-500">
                How emails are being classified
              </p>
            </div>

            <BarChart3
              size={20}
              className="text-blue-600"
            />
          </div>

          <div className="mt-6 space-y-5">
            {classificationData.map((item) => (
              <div key={item.category}>
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm text-gray-700">
                    {item.category}
                  </span>

                  <span className="text-xs font-medium text-gray-500">
                    {item.count} ({item.percentage}%)
                  </span>
                </div>

                <div className="h-2 overflow-hidden rounded-full bg-gray-100">
                  <div
                    className="h-full rounded-full bg-blue-500"
                    style={{
                      width: `${item.percentage}%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 border-t pt-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-600">
                Total Classified
              </span>

              <span className="text-sm font-bold text-gray-900">
                {totalEmails.toLocaleString()}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* AI Performance */}
      <div className="rounded-xl border bg-white p-6 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-50 text-purple-600">
            <Activity size={20} />
          </div>

          <div>
            <h2 className="font-semibold text-gray-900">
              AI System Performance
            </h2>

            <p className="mt-1 text-xs text-gray-500">
              Current performance across the multi-agent pipeline
            </p>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="rounded-lg bg-gray-50 p-4">
            <p className="text-xs text-gray-500">
              Agent Success Rate
            </p>

            <p className="mt-2 text-xl font-bold text-gray-900">
              98.4%
            </p>

            <div className="mt-3 h-2 rounded-full bg-gray-200">
              <div
                className="h-2 rounded-full bg-green-500"
                style={{ width: "98.4%" }}
              />
            </div>
          </div>

          <div className="rounded-lg bg-gray-50 p-4">
            <p className="text-xs text-gray-500">
              Human Review Rate
            </p>

            <p className="mt-2 text-xl font-bold text-gray-900">
              6.9%
            </p>

            <div className="mt-3 h-2 rounded-full bg-gray-200">
              <div
                className="h-2 rounded-full bg-yellow-500"
                style={{ width: "6.9%" }}
              />
            </div>
          </div>

          <div className="rounded-lg bg-gray-50 p-4">
            <p className="text-xs text-gray-500">
              Threat Detection Rate
            </p>

            <p className="mt-2 text-xl font-bold text-gray-900">
              99.1%
            </p>

            <div className="mt-3 h-2 rounded-full bg-gray-200">
              <div
                className="h-2 rounded-full bg-red-500"
                style={{ width: "99.1%" }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}