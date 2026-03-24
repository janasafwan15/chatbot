import { useState, useEffect } from "react";
import { X, Save } from "lucide-react";
import { ragService } from "../services/ragService";
import { getApiBase, setApiBase } from "../api/http";

interface Props {
  onClose: () => void;
  onSave?: () => void;
}

export function OllamaSettings({ onClose, onSave }: Props) {
  const [baseUrl, setBaseUrl] = useState(getApiBase());
  const [connected, setConnected] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);

  // فحص الاتصال عند الفتح
  useEffect(() => {
    checkConnection();
  }, []);

  const checkConnection = async () => {
    setLoading(true);
    const ok = await ragService.checkConnection();
    setConnected(ok);
    setLoading(false);
  };

  const handleSave = async () => {
    // ✅ احفظ العنوان للواجهة كاملة
    setApiBase(baseUrl);
    await checkConnection();
    onSave?.();
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl shadow-2xl w-[420px] max-w-full p-6" dir="rtl">

        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-gray-800">
            إعدادات الاتصال بالخادم
          </h2>

          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg"
          >
            <X size={20} />
          </button>
        </div>

        {/* URL */}
        <div className="space-y-2 mb-5">
          <label className="text-sm text-gray-600 font-semibold">
            عنوان السيرفر
          </label>

          <input
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 outline-none"
            placeholder="http://127.0.0.1:8010"
          />
        </div>

        {/* Status */}
        <div className="mb-6">
          {loading && (
            <p className="text-gray-500 text-sm">جارٍ الفحص...</p>
          )}

          {connected === true && (
            <p className="text-green-600 text-sm font-semibold">
              ✅ متصل بالسيرفر
            </p>
          )}

          {connected === false && (
            <p className="text-red-600 text-sm font-semibold">
              ❌ غير متصل — شغّل FastAPI أولاً
            </p>
          )}
        </div>

        {/* Buttons */}
        <div className="flex gap-3">
          <button
            onClick={handleSave}
            className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-2 rounded-lg flex items-center justify-center gap-2"
          >
            <Save size={18} />
            حفظ
          </button>

          <button
            onClick={checkConnection}
            className="flex-1 bg-gray-100 hover:bg-gray-200 py-2 rounded-lg"
          >
            اختبار الاتصال
          </button>
        </div>
      </div>
    </div>
  );
}
