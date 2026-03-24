import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Lock, AlertCircle, CheckCircle } from "lucide-react";
import { changePassword } from "../api/auth";
import { useAuth } from "../context/AuthContext";

export function ForceChangePassword() {
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const nav = useNavigate();
  const { role, mustChangePassword, clearMustChangePassword, logout } = useAuth();

  if (!mustChangePassword) {
    nav(role === "admin" ? "/admin" : "/employee", { replace: true });
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!oldPassword || !newPassword || !confirmPassword) {
      setError("يرجى تعبئة جميع الحقول");
      return;
    }
    if (newPassword.length < 8) {
      setError("كلمة المرور الجديدة يجب أن تكون 8 أحرف على الأقل");
      return;
    }
    if (!/[A-Z]/.test(newPassword)) {
      setError("كلمة المرور يجب أن تحتوي على حرف كبير واحد على الأقل");
      return;
    }
    if (!/\d/.test(newPassword)) {
      setError("كلمة المرور يجب أن تحتوي على رقم واحد على الأقل");
      return;
    }
    if (!/[^A-Za-z0-9]/.test(newPassword)) {
      setError("كلمة المرور يجب أن تحتوي على رمز خاص مثل !@#$");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("كلمة المرور الجديدة وتأكيدها غير متطابقين");
      return;
    }
    if (oldPassword === newPassword) {
      setError("كلمة المرور الجديدة يجب أن تكون مختلفة عن القديمة");
      return;
    }

    try {
      setIsSubmitting(true);
      await changePassword(oldPassword, newPassword);
      clearMustChangePassword();
      nav(role === "admin" ? "/admin" : "/employee", { replace: true });
    } catch (err: any) {
      const detail = err?.detail || err?.message || "";
      if (detail.toLowerCase().includes("old password")) {
        setError("كلمة المرور الحالية غير صحيحة");
      } else {
        setError("حدث خطأ، يرجى المحاولة مجدداً");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-500 to-red-600 flex items-center justify-center p-4" dir="rtl">
      <div className="w-full max-w-md">
        <div className="text-center text-white mb-8">
          <div className="w-24 h-24 bg-white rounded-full mx-auto mb-4 flex items-center justify-center">
            <Lock className="w-12 h-12 text-orange-500" />
          </div>
          <h1 className="text-3xl font-bold mb-2">تغيير كلمة المرور</h1>
          <p className="text-orange-100">يجب عليك تغيير كلمة المرور قبل المتابعة</p>
        </div>

        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <div className="bg-orange-50 border border-orange-200 rounded-lg p-4 flex gap-3 mb-6">
            <AlertCircle className="w-5 h-5 text-orange-500 flex-shrink-0 mt-0.5" />
            <p className="text-orange-700 text-sm">
              هذه أول مرة تسجل دخولك. لحماية حسابك، يرجى تغيير كلمة المرور الافتراضية الآن.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-gray-700 font-semibold mb-2">كلمة المرور الحالية</label>
              <input
                type="password"
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-orange-500 text-right"
                placeholder="أدخل كلمة المرور الحالية"
                autoComplete="current-password"
              />
            </div>

            <div>
              <label className="block text-gray-700 font-semibold mb-2">كلمة المرور الجديدة</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-orange-500 text-right"
                placeholder="8 أحرف: حرف كبير + رقم + رمز خاص"
                autoComplete="new-password"
              />
            </div>

            <div>
              <label className="block text-gray-700 font-semibold mb-2">تأكيد كلمة المرور الجديدة</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-orange-500 text-right"
                placeholder="أعد إدخال كلمة المرور الجديدة"
                autoComplete="new-password"
              />
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
              className="w-full bg-orange-500 hover:bg-orange-600 disabled:bg-gray-400 text-white py-3 rounded-lg font-semibold transition-colors flex items-center justify-center gap-2"
            >
              {isSubmitting ? (
                "جاري التغيير..."
              ) : (
                <>
                  <CheckCircle className="w-5 h-5" />
                  تغيير كلمة المرور والمتابعة
                </>
              )}
            </button>

            <button
              type="button"
              onClick={() => { logout(); nav("/login", { replace: true }); }}
              className="w-full text-gray-500 hover:text-gray-700 text-sm py-2 transition-colors"
            >
              تسجيل الخروج
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}