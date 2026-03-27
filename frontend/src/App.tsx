import { Routes, Route, Navigate, useNavigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { ErrorBoundary } from "./app/components/ErrorBoundary";

import { RoleSelection } from "./pages/RoleSelection";
import { CitizenChatbot } from "./pages/CitizenChatbot";
import { EmployeeLogin } from "./pages/EmployeeLogin";
import { EmployeeDashboard } from "./pages/EmployeeDashboard";
import { AdminDashboard } from "./pages/AdminDashboard";
import { ForceChangePassword } from "./pages/ForceChangePassword";
import AdvancedAnalytics from "./pages/AdvancedAnalytics";
import { RatingsAnalytics } from "./pages/RatingsAnalytics";


type AppRole = "citizen" | "employee" | "admin";
type AuthRole = "employee" | "supervisor" | "admin";

function Protected({ allow, children }: { allow: AuthRole[]; children: React.ReactElement }) {
  const { role, token } = useAuth();
  if (!token || !role) return <Navigate to="/login" replace />;
  if (!allow.includes(role as AuthRole)) return <Navigate to="/" replace />;
  return children;
}

function AppRoutes() {
  const nav = useNavigate();
  const { logout } = useAuth();

  return (
    <Routes>
      <Route
        path="/"
        element={
          <ErrorBoundary message="خطأ في صفحة الاختيار">
            <RoleSelection
              onSelectRole={(r: AppRole) => {
                if (r === "citizen") nav("/citizen");
                else nav("/login");
              }}
            />
          </ErrorBoundary>
        }
      />

      <Route
        path="/citizen"
        element={
          <ErrorBoundary message="خطأ في نظام الدعم الذكي">
            <CitizenChatbot />
          </ErrorBoundary>
        }
      />

      <Route
        path="/login"
        element={
          <ErrorBoundary message="خطأ في صفحة تسجيل الدخول">
            <EmployeeLogin />
          </ErrorBoundary>
        }
      />

      <Route
        path="/employee"
        element={
          <Protected allow={["employee", "supervisor"]}>
            <ErrorBoundary message="خطأ في لوحة تحكم الموظف">
              <EmployeeDashboard onLogout={logout} />
            </ErrorBoundary>
          </Protected>
        }
      />

      <Route
        path="/admin"
        element={
          <Protected allow={["admin"]}>
            <ErrorBoundary message="خطأ في لوحة تحكم الأدمن">
              <AdminDashboard onLogout={logout} />
            </ErrorBoundary>
          </Protected>
        }
      />

      <Route
        path="/change-password"
        element={
          <ErrorBoundary message="خطأ في صفحة تغيير كلمة المرور">
            <ForceChangePassword />
          </ErrorBoundary>
        }
      />

      <Route
        path="/advanced-analytics"
        element={
          <Protected allow={["employee", "supervisor", "admin"]}>
            <ErrorBoundary message="خطأ في التحليلات المتقدمة">
              <AdvancedAnalyticsWrapper />
            </ErrorBoundary>
          </Protected>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
      <Route path="/ratings" element={<RatingsAnalytics showDetails={true} />} />
    </Routes>
  );
}

function AdvancedAnalyticsWrapper() {
  const { token, role } = useAuth();
  return <AdvancedAnalytics token={token!} role={role!} />;
}

export default function App() {
  return (
    <AuthProvider>
      {/* ErrorBoundary خارجي يمسك أي خطأ فاتت من الـ routes */}
      <ErrorBoundary message="خطأ عام في التطبيق">
        <AppRoutes />
      </ErrorBoundary>
    </AuthProvider>
  );
}