import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Lock, User, AlertCircle } from "lucide-react";
import { login } from "../api/auth";
import { useAuth } from "../context/AuthContext";

export function EmployeeLogin() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const nav = useNavigate();
  const { setAuth } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!username || !password) {
      setError("يرجى إدخال اسم المستخدم وكلمة المرور");
      return;
    }

    try {
      setIsSubmitting(true);
      const res = await login(username, password);
      setAuth({
        token: res.token,
        role: res.role,
        fullName: res.full_name,
        mustChangePassword: res.must_change_password,
      });

      if (res.must_change_password) {
        nav("/change-password");
      } else if (res.role === "admin") {
        nav("/admin");
      } else {
        nav("/employee");
      }
    } catch (err: any) {
      const msg = String(err?.message || "");
      if (msg.includes("429") || msg.includes("تم تجاوز")) {
        setError("تم تجاوز عدد محاولات الدخول. يرجى الانتظار دقائق ثم المحاولة مجدداً.");
      } else if (msg.includes("inactive") || msg.includes("غير نشط")) {
        setError("هذا الحساب غير نشط. يرجى التواصل مع المدير.");
      } else {
        setError("اسم المستخدم أو كلمة المرور غير صحيحة");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-600 to-green-600 flex items-center justify-center p-4" dir="rtl">
      <div className="w-full max-w-md">
        <div className="text-center text-white mb-8">
          <div className="w-24 h-24 bg-white rounded-full mx-auto mb-4 flex items-center justify-center">
            <Lock className="w-12 h-12 text-blue-600" />
          </div>
          <h1 className="text-3xl font-bold mb-2">تسجيل الدخول</h1>
          <p className="text-blue-100">نظام إدارة كهرباء الخليل</p>
        </div>

        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-gray-700 font-semibold mb-2">اسم المستخدم</label>
              <div className="relative">
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-4 py-3 pr-12 focus:outline-none focus:ring-2 focus:ring-blue-500 text-right"
                  placeholder="أدخل اسم المستخدم"
                  autoComplete="username"
                />
                <User className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
              </div>
            </div>

            <div>
              <label className="block text-gray-700 font-semibold mb-2">كلمة المرور</label>
              <div className="relative">
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-4 py-3 pr-12 focus:outline-none focus:ring-2 focus:ring-blue-500 text-right"
                  placeholder="••••••••"
                  autoComplete="current-password"
                />
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
              </div>
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex gap-3">
                <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                <p className="text-red-700 text-sm">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white py-3 rounded-lg font-semibold transition-colors"
            >
              {isSubmitting ? "جاري الدخول..." : "تسجيل الدخول"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}