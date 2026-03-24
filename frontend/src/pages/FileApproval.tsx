// src/pages/FileApproval.tsx
import { useState, useEffect, useCallback } from "react";
import { FileText, CheckCircle, XCircle, Clock, Eye, RefreshCw } from "lucide-react";
import { listFiles, getFile, approveFile, rejectFile, type FileOut, type FileDetailOut } from "../api/files";

export function FileApproval() {
  const [files, setFiles]                 = useState<FileOut[]>([]);
  const [loading, setLoading]             = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [activeTab, setActiveTab]         = useState<"pending"|"approved"|"rejected">("pending");
  const [toast, setToast]                 = useState<{ msg: string; ok: boolean } | null>(null);

  // نافذة المعاينة
  const [preview, setPreview]             = useState<FileDetailOut | null>(null);
  const [previewOpen, setPreviewOpen]     = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);

  // نافذة الرفض
  const [rejectTarget, setRejectTarget]   = useState<FileOut | null>(null);
  const [rejectReason, setRejectReason]   = useState("");
  const [rejectOpen, setRejectOpen]       = useState(false);

  const showToast = (msg: string, ok = true) => { setToast({ msg, ok }); setTimeout(() => setToast(null), 3500); };

  const loadFiles = useCallback(async () => {
    try { setFiles(await listFiles()); }
    catch (e: any) { showToast("فشل تحميل الملفات: " + e.message, false); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadFiles(); const t = setInterval(loadFiles, 10_000); return () => clearInterval(t); }, [loadFiles]);

  const handleApprove = async (fileId: number) => {
    setActionLoading(true);
    try {
      const res = await approveFile(fileId);
      showToast(`تمت الموافقة وإضافته لقاعدة المعرفة (#${res.kb_id})`);
      setPreviewOpen(false);
      await loadFiles();
    } catch (e: any) { showToast("فشل الموافقة: " + e.message, false); }
    finally { setActionLoading(false); }
  };

  const handleReject = async () => {
    if (!rejectTarget) return;
    if (!rejectReason.trim()) { showToast("يرجى إدخال سبب الرفض", false); return; }
    setActionLoading(true);
    try {
      await rejectFile(rejectTarget.file_id, rejectReason.trim());
      showToast("تم رفض الملف");
      setRejectOpen(false); setRejectReason(""); setRejectTarget(null);
      await loadFiles();
    } catch (e: any) { showToast("فشل الرفض: " + e.message, false); }
    finally { setActionLoading(false); }
  };

  const handlePreview = async (file: FileOut) => {
    setPreviewOpen(true); setPreviewLoading(true);
    try { setPreview(await getFile(file.file_id)); }
    catch { showToast("فشل تحميل المحتوى", false); setPreviewOpen(false); }
    finally { setPreviewLoading(false); }
  };

  const fmtSize = (b: number) => b < 1024 ? b+" بايت" : b < 1048576 ? (b/1024).toFixed(1)+" كيلوبايت" : (b/1048576).toFixed(1)+" ميجابايت";
  const fmtDate = (d: string) => new Date(d).toLocaleDateString("ar-EG", { year:"numeric",month:"long",day:"numeric",hour:"2-digit",minute:"2-digit" });

  const badge = (s: string) => s === "approved"
    ? <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800"><CheckCircle className="w-3 h-3"/>موافق عليه</span>
    : s === "rejected"
    ? <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800"><XCircle className="w-3 h-3"/>مرفوض</span>
    : <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800"><Clock className="w-3 h-3"/>قيد المراجعة</span>;

  const pending  = files.filter(f => f.status === "pending");
  const approved = files.filter(f => f.status === "approved");
  const rejected = files.filter(f => f.status === "rejected");
  const shown    = activeTab === "pending" ? pending : activeTab === "approved" ? approved : rejected;

  const tabBtn = (id: typeof activeTab, label: string, count: number) => (
    <button onClick={() => setActiveTab(id)}
      className={`flex-1 py-2 text-sm font-medium rounded-lg transition-colors ${activeTab === id ? "bg-white shadow text-blue-600" : "text-gray-500 hover:text-gray-700"}`}>
      {label} ({count})
    </button>
  );

  return (
    <div className="space-y-6" dir="rtl">
      {toast && <div className={`fixed top-4 left-1/2 -translate-x-1/2 z-50 px-6 py-3 rounded-xl shadow-lg text-white text-sm font-medium ${toast.ok ? "bg-green-600" : "bg-red-600"}`}>{toast.msg}</div>}

      <div className="bg-white rounded-xl shadow-md p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-bold text-gray-800">إدارة الملفات المرفوعة</h2>
            <p className="text-sm text-gray-500">مراجعة والموافقة على الملفات</p>
          </div>
          <button onClick={loadFiles} disabled={loading} className="flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`}/> تحديث
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          {[{icon:<Clock className="w-8 h-8 text-yellow-600"/>,count:pending.length,label:"في انتظار المراجعة",bg:"bg-yellow-50 border-yellow-200",txt:"text-yellow-900"},
            {icon:<CheckCircle className="w-8 h-8 text-green-600"/>,count:approved.length,label:"موافق عليها",bg:"bg-green-50 border-green-200",txt:"text-green-900"},
            {icon:<XCircle className="w-8 h-8 text-red-600"/>,count:rejected.length,label:"مرفوضة",bg:"bg-red-50 border-red-200",txt:"text-red-900"}
          ].map((s,i) => (
            <div key={i} className={`border rounded-lg p-4 ${s.bg}`}>
              <div className="flex items-center gap-3">
                {s.icon}
                <div><p className={`text-2xl font-bold ${s.txt}`}>{s.count}</p><p className={`text-sm ${s.txt} opacity-80`}>{s.label}</p></div>
              </div>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1 mb-4">
          {tabBtn("pending","قيد المراجعة",pending.length)}
          {tabBtn("approved","موافق عليها",approved.length)}
          {tabBtn("rejected","مرفوضة",rejected.length)}
        </div>

        {loading ? (
          <div className="text-center py-12 text-gray-400"><RefreshCw className="w-8 h-8 mx-auto mb-2 animate-spin"/><p>جاري التحميل...</p></div>
        ) : shown.length === 0 ? (
          <div className="text-center py-12 text-gray-400"><FileText className="w-12 h-12 mx-auto mb-3"/><p>لا توجد ملفات</p></div>
        ) : (
          <div className="space-y-3">
            {shown.map(f => (
              <div key={f.file_id} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3 flex-1">
                    <FileText className="w-5 h-5 text-blue-500 mt-0.5 flex-shrink-0"/>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="font-medium text-gray-900 truncate">{f.name}</span>
                        {badge(f.status)}
                      </div>
                      <p className="text-xs text-gray-500">رفع بواسطة: {f.uploaded_by_name || "موظف"} · {fmtSize(f.size_bytes)} · {fmtDate(f.uploaded_at)}</p>
                      {f.status === "approved" && f.kb_id && <p className="text-xs text-green-600 mt-1">✓ قاعدة المعرفة #{f.kb_id}</p>}
                      {f.status === "rejected" && f.rejection_reason && <p className="text-xs text-red-600 mt-1"><span className="font-medium">سبب الرفض:</span> {f.rejection_reason}</p>}
                    </div>
                  </div>
                  <div className="flex gap-2 flex-shrink-0">
                    <button onClick={() => handlePreview(f)} className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-100 transition-colors">
                      <Eye className="w-4 h-4"/> عرض
                    </button>
                    {f.status === "pending" && (<>
                      <button disabled={actionLoading} onClick={() => handleApprove(f.file_id)}
                        className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-green-600 hover:bg-green-700 text-white text-sm transition-colors disabled:opacity-50">
                        <CheckCircle className="w-4 h-4"/> موافقة
                      </button>
                      <button disabled={actionLoading} onClick={() => { setRejectTarget(f); setRejectOpen(true); }}
                        className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm transition-colors disabled:opacity-50">
                        <XCircle className="w-4 h-4"/> رفض
                      </button>
                    </>)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Preview Modal */}
      {previewOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={() => setPreviewOpen(false)}>
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col" dir="rtl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="font-bold text-gray-800">{preview?.name ?? "معاينة الملف"}</h3>
              <button onClick={() => setPreviewOpen(false)} className="p-1 rounded hover:bg-gray-100 text-gray-500">✕</button>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              {previewLoading ? (
                <div className="text-center py-8"><RefreshCw className="w-6 h-6 mx-auto animate-spin text-gray-400"/></div>
              ) : (
                <pre className="whitespace-pre-wrap text-sm font-mono text-right bg-gray-50 rounded-lg p-4">
                  {preview?.content?.substring(0, 2000)}
                  {(preview?.content?.length ?? 0) > 2000 && "\n\n... (تم اقتطاع المحتوى)"}
                </pre>
              )}
            </div>
            {preview?.status === "pending" && (
              <div className="flex gap-3 justify-end p-4 border-t">
                <button disabled={actionLoading} onClick={() => handleApprove(preview.file_id)}
                  className="flex items-center gap-1 px-4 py-2 rounded-lg bg-green-600 hover:bg-green-700 text-white text-sm disabled:opacity-50">
                  <CheckCircle className="w-4 h-4"/> موافقة
                </button>
                <button disabled={actionLoading} onClick={() => { setRejectTarget(preview); setPreviewOpen(false); setRejectOpen(true); }}
                  className="flex items-center gap-1 px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm disabled:opacity-50">
                  <XCircle className="w-4 h-4"/> رفض
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Reject Modal */}
      {rejectOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={() => setRejectOpen(false)}>
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md" dir="rtl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="font-bold text-gray-800">رفض الملف</h3>
              <button onClick={() => setRejectOpen(false)} className="p-1 rounded hover:bg-gray-100 text-gray-500">✕</button>
            </div>
            <div className="p-4 space-y-4">
              <p className="text-sm text-gray-600">يرجى توضيح سبب رفض الملف "{rejectTarget?.name}"</p>
              <textarea value={rejectReason} onChange={e => setRejectReason(e.target.value)} rows={4}
                placeholder="اكتب سبب الرفض هنا..."
                className="w-full border border-gray-200 rounded-lg p-3 text-sm text-right resize-none focus:outline-none focus:ring-2 focus:ring-red-400"/>
              <div className="flex gap-3 justify-end">
                <button onClick={() => { setRejectOpen(false); setRejectReason(""); setRejectTarget(null); }}
                  className="px-4 py-2 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50">إلغاء</button>
                <button disabled={actionLoading} onClick={handleReject}
                  className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm disabled:opacity-50">تأكيد الرفض</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
