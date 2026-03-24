import { useState } from "react";
import { Star, Send, X } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface RatingModalProps {
  onClose: () => void;
  onRate: (rating: number, feedback: string) => void | Promise<void>;
  disabled?: boolean;
}

export function RatingModal({ onClose, onRate, disabled = false }: RatingModalProps) {
  const [rating, setRating] = useState(0);
  const [hoveredRating, setHoveredRating] = useState(0);
  const [feedback, setFeedback] = useState("");

  const handleSubmit = async () => {
    if (disabled) return;
    if (rating > 0) {
      await onRate(rating, feedback);
      onClose();
    }
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
        onClick={onClose}
        dir="rtl"
      >
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
          className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-8"
        >
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-gray-800">قيّم تجربتك</h2>
            <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>

          <div className="text-center mb-6">
            <p className="text-gray-600 mb-4">كيف كانت تجربتك مع نظام الدعم الذكي؟</p>

            <div className="flex justify-center gap-2 mb-2" dir="ltr">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  disabled={disabled}
                  onClick={() => setRating(star)}
                  onMouseEnter={() => setHoveredRating(star)}
                  onMouseLeave={() => setHoveredRating(0)}
                  className={`transform transition-transform ${
                    disabled ? "opacity-60 cursor-not-allowed" : "hover:scale-110"
                  }`}
                >
                  <Star
                    className={`w-12 h-12 transition-colors ${
                      star <= (hoveredRating || rating) ? "fill-yellow-400 text-yellow-400" : "text-gray-300"
                    }`}
                  />
                </button>
              ))}
            </div>

            {rating > 0 && (
              <motion.p initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="text-sm font-semibold text-blue-600">
                {rating === 1 && "سيء جداً 😞"}
                {rating === 2 && "سيء 😕"}
                {rating === 3 && "مقبول 😐"}
                {rating === 4 && "جيد 😊"}
                {rating === 5 && "ممتاز 🤩"}
              </motion.p>
            )}
          </div>

          <div className="mb-6">
            <label className="block text-gray-700 font-semibold mb-2">هل لديك أي ملاحظات أو اقتراحات؟ (اختياري)</label>
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              rows={4}
              disabled={disabled}
              className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none disabled:bg-gray-50"
              placeholder="أخبرنا عن تجربتك..."
            />
          </div>

          <div className="flex gap-3">
            <button
              onClick={handleSubmit}
              disabled={rating === 0 || disabled}
              className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-6 py-3 rounded-lg font-semibold transition-colors flex items-center justify-center gap-2"
            >
              <Send className="w-5 h-5" />
              إرسال التقييم
            </button>

            <button
              onClick={onClose}
              className="px-6 py-3 border border-gray-300 rounded-lg font-semibold hover:bg-gray-50 transition-colors"
            >
              إلغاء
            </button>
          </div>

          <p className="text-xs text-gray-500 text-center mt-4">تقييمك يساعدنا على تحسين خدماتنا</p>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
