import { Navigate, Routes, Route } from "react-router-dom";

import Emails from "../pages/Emails/Emails";
import Analytics from "../pages/Analytics/Analytics";
import Settings from "../pages/Settings/Settings";

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/emails" replace />} />

      <Route
        path="/emails"
        element={<Emails />}
      />

      <Route
        path="/analytics"
        element={<Analytics />}
      />

      <Route
        path="/settings"
        element={<Settings />}
      />

      <Route path="*" element={<Navigate to="/emails" replace />} />
    </Routes>
  );
}
