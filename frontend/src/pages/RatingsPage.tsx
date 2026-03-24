import { useAuth } from "../context/AuthContext";
import { RatingsAnalytics } from "../app/components/RatingsAnalytics";

export function RatingsPage() {
  // ✅ التوكن من memory عبر AuthContext — مش localStorage
  const { token } = useAuth();

  return (
    <div className="p-6" dir="rtl">
      <div className="bg-white rounded-xl shadow-md p-6">
        <h1 className="text-2xl font-bold text-gray-800 mb-4">التقييمات</h1>
        <RatingsAnalytics token={token} days={30} showDetails />
      </div>
    </div>
  );
}