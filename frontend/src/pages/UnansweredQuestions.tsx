// src/pages/UnansweredQuestions.tsx
import { useState, useEffect, useCallback } from "react";
import { MessageSquare, Send, Trash2, CheckCircle, Clock, User, RefreshCw } from "lucide-react";
import { listUnanswered, answerQuestion, deleteQuestion, type QuestionOut } from "../api/unanswered";

export function UnansweredQuestions() {
  const [questions, setQuestions]         = useState<QuestionOut[]>([]);
  const [loading, setLoading]             = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [selected, setSelected]           = useState<QuestionOut | null>(null);
  const [answer, setAnswer]               = useState("");
  const [answerOpen, setAnswerOpen]       = useState(false);
  const [toast, setToast]                 = useState<{ msg: string; ok: boolean } | null>(null);

  const showToast = (msg: string, ok = true) => { setToast({ msg, ok }); setTimeout(() => setToast(null), 3500); };

  const load = useCallback(async () => {
    try { setQuestions(await listUnanswered()); }
    catch (e: any) { showToast("فشل تحميل الأسئلة: " + e.message, false); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); const t = setInterval(load, 10_000); return () => clearInterval(t); }, [load]);

  const handleAnswer = async () => {
    if (!selected || !answer.trim()) { showToast("يرجى إدخال إجابة", false); return; }
    setActionLoading(true);
    try {
      const res = await answerQuestion(selected.question_id, answer.trim());
      showToast(`تم إرسال الإجابة وإضافتها لقاعدة المعرفة (#${res.kb_id})`);
      setAnswerOpen(false); setAnswer(""); setSelected(null);
      await load();
    } catch (e: any) { showToast("فشل إرسال الإجابة: " + e.message, false); }
    finally { setActionLoading(false); }
  };

  const handleDelete = async (id: number) => {
    try { await deleteQuestion(id); showToast("تم حذف السؤال"); setQuestions(prev => prev.filter(q => q.question_id !== id)); }
    catch (e: any) { showToast("فشل الحذف: " + e.message, false); }
  };

  const fmtDate = (d: string) => new Date(d).toLocaleDateString("ar-EG", { year:"numeric",month:"short",day:"numeric",hour:"2-digit",minute:"2-digit" });

  const pending  = questions.filter(q => q.status === "pending");
  const answered = questions.filter(q => q.status === "answered");

  return (
    <div className="space-y-6" dir="rtl">
      {toast && <div className={`fixed top-4 left-1/2 -translate-x-1/2 z-50 px-6 py-3 rounded-xl shadow-lg text-white text-sm font-medium ${toast.ok ? "bg-green-600" : "bg-red-600"}`}>{toast.msg}</div>}

      <div className="bg-white rounded-xl shadow-md p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-bold text-gray-800">الأسئلة المحولة من المواطنين</h2>
            <p className="text-sm text-gray-500">الأسئلة التي لم يستطع الذكاء الاصطناعي الإجابة عليها</p>
          </div>
          <button onClick={load} disabled={loading} className="flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`}/> تحديث
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <div className="flex items-center gap-3">
              <Clock className="w-8 h-8 text-yellow-600"/>
              <div><p className="text-2xl font-bold text-yellow-900">{pending.length}</p><p className="text-sm text-yellow-700">في انتظار الرد</p></div>
            </div>
          </div>
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex items-center gap-3">
              <CheckCircle className="w-8 h-8 text-green-600"/>
              <div><p className="text-2xl font-bold text-green-900">{answered.length}</p><p className="text-sm text-green-700">تم الرد عليها</p></div>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-12 text-gray-400"><RefreshCw className="w-8 h-8 mx-auto mb-2 animate-spin"/><p>جاري التحميل...</p></div>
        ) : (<>
          {/* Pending */}
          <div className="mb-8">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">في انتظار الرد ({pending.length})</h3>
            {pending.length === 0 ? (
              <div className="text-center py-8 text-gray-400 border border-dashed rounded-lg">
                <MessageSquare className="w-10 h-10 mx-auto mb-2"/><p>لا توجد أسئلة في انتظار الرد</p>
              </div>
            ) : (
              <div className="space-y-3">
                {pending.map(q => (
                  <div key={q.question_id} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex items-start gap-3 flex-1">
                        <MessageSquare className="w-5 h-5 text-blue-500 mt-0.5 flex-shrink-0"/>
                        <div className="flex-1">
                          <p className="font-medium text-gray-900 mb-2">{q.question}</p>
                          <div className="flex items-center gap-3 text-xs text-gray-500">
                            <span className="flex items-center gap-1"><User className="w-3.5 h-3.5"/>{q.asked_by}</span>
                            <span>·</span>
                            <span>{fmtDate(q.asked_at)}</span>
                          </div>
                        </div>
                      </div>
                      <div className="flex gap-2 flex-shrink-0">
                        <button onClick={() => { setSelected(q); setAnswerOpen(true); }}
                          className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm transition-colors">
                          <Send className="w-4 h-4"/> رد
                        </button>
                        <button onClick={() => handleDelete(q.question_id)}
                          className="p-1.5 rounded-lg text-red-400 hover:text-red-600 hover:bg-red-50 transition-colors">
                          <Trash2 className="w-4 h-4"/>
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Answered */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">تم الرد عليها ({answered.length})</h3>
            {answered.length === 0 ? (
              <div className="text-center py-8 text-gray-400 border border-dashed rounded-lg">
                <CheckCircle className="w-10 h-10 mx-auto mb-2"/><p>لا توجد أسئلة تم الرد عليها</p>
              </div>
            ) : (
              <div className="space-y-3">
                {answered.map(q => (
                  <div key={q.question_id} className="border border-green-200 bg-green-50 rounded-lg p-4">
                    <div className="flex items-start gap-3">
                      <CheckCircle className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0"/>
                      <div className="flex-1">
                        <div className="flex items-start justify-between gap-4 mb-3">
                          <div>
                            <p className="font-medium text-gray-900 mb-1">{q.question}</p>
                            <p className="text-xs text-gray-500">سأل بواسطة {q.asked_by} في {fmtDate(q.asked_at)}</p>
                          </div>
                          <button onClick={() => handleDelete(q.question_id)}
                            className="p-1.5 rounded-lg text-red-400 hover:text-red-600 hover:bg-red-50 flex-shrink-0">
                            <Trash2 className="w-4 h-4"/>
                          </button>
                        </div>
                        <div className="bg-white border border-green-200 rounded-lg p-3">
                          <p className="text-sm font-medium text-gray-700 mb-1">الإجابة:</p>
                          <p className="text-gray-900 text-sm">{q.answer}</p>
                          <p className="text-xs text-gray-400 mt-2">
                            أجاب بواسطة {q.answered_by_name || "موظف"}
                            {q.answered_at ? ` في ${fmtDate(q.answered_at)}` : ""}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>)}
      </div>

      {/* Answer Modal */}
      {answerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={() => setAnswerOpen(false)}>
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl" dir="rtl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="font-bold text-gray-800">الرد على السؤال</h3>
              <button onClick={() => setAnswerOpen(false)} className="p-1 rounded hover:bg-gray-100 text-gray-500">✕</button>
            </div>
            <div className="p-4 space-y-4">
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <p className="text-sm font-medium text-gray-700 mb-1">السؤال:</p>
                <p className="text-gray-900">{selected?.question}</p>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">الإجابة:</label>
                <textarea value={answer} onChange={e => setAnswer(e.target.value)} rows={6}
                  placeholder="اكتب إجابتك هنا..."
                  className="w-full border border-gray-200 rounded-lg p-3 text-sm text-right resize-none focus:outline-none focus:ring-2 focus:ring-blue-400"/>
              </div>
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-900">
                <strong>ملاحظة:</strong> الإجابة سيتم إضافتها تلقائياً إلى قاعدة المعرفة.
              </div>
              <div className="flex gap-3 justify-end">
                <button onClick={() => { setAnswerOpen(false); setAnswer(""); setSelected(null); }}
                  className="px-4 py-2 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50">إلغاء</button>
                <button disabled={actionLoading} onClick={handleAnswer}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm disabled:opacity-50">
                  <Send className="w-4 h-4"/> إرسال الإجابة
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
