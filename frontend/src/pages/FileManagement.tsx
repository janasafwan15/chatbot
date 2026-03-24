// src/pages/FileManagement.tsx
import { useState, useEffect, useCallback } from "react";
import { Upload, FileText, CheckCircle, XCircle, Clock, Trash2, RefreshCw } from "lucide-react";
import { listFiles, uploadFile, deleteFile, type FileOut } from "../api/files";

export function FileManagement() {
  const [files, setFiles]         = useState<FileOut[]>([]);
  const [loading, setLoading]     = useState(true);
  const [uploading, setUploading] = useState(false);
  const [toast, setToast]         = useState<{ msg: string; ok: boolean } | null>(null);

  const showToast = (msg: string, ok = true) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3500);
  };

  const loadFiles = useCallback(async () => {
    try { setFiles(await listFiles()); }
    catch (e: any) { showToast("فشل تحميل الملفات: " + e.message, false); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    loadFiles();
    const t = setInterval(loadFiles, 10_000);
    return () => clearInterval(t);
  }, [loadFiles]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files;
    if (!selected?.length) return;
    setUploading(true);
    let uploaded = 0;
    for (let i = 0; i < selected.length; i++) {
      const file = selected[i];
      const allowed = ["text/plain","application/pdf","application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"];
      if (!allowed.includes(file.type) && !file.name.endsWith(".txt")) {
        showToast(`نوع الملف "${file.name}" غير مدعوم`, false); continue;
      }
      if (file.size > 5 * 1024 * 1024) {
        showToast(`الملف "${file.name}" أكبر من 5 ميجابايت`, false); continue;
      }
      try { await uploadFile(file); uploaded++; }
      catch (err: any) { showToast(`فشل رفع "${file.name}": ${err.message}`, false); }
    }
    if (uploaded > 0) { showToast(`تم رفع ${uploaded} ملف — في انتظار موافقة الإدارة`); await loadFiles(); }
    setUploading(false);
    e.target.value = "";
  };

  const handleDelete = async (fileId: number) => {
    try { await deleteFile(fileId); showToast("تم حذف الملف"); setFiles(prev => prev.filter(f => f.file_id !== fileId)); }
    catch (err: any) { showToast("فشل الحذف: " + err.message, false); }
  };

  const fmtSize = (b: number) =>
    b < 1024 ? b + " بايت" : b < 1048576 ? (b/1024).toFixed(1)+" كيلوبايت" : (b/1048576).toFixed(1)+" ميجابايت";

  const fmtDate = (d: string) =>
    new Date(d).toLocaleDateString("ar-EG", { year:"numeric",month:"long",day:"numeric",hour:"2-digit",minute:"2-digit" });

  const badge = (s: string) => s === "approved"
    ? <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800"><CheckCircle className="w-3 h-3"/>موافق عليه</span>
    : s === "rejected"
    ? <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800"><XCircle className="w-3 h-3"/>مرفوض</span>
    : <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800"><Clock className="w-3 h-3"/>قيد المراجعة</span>;

  return (
    <div className="space-y-6" dir="rtl">
      {toast && (
        <div className={`fixed top-4 left-1/2 -translate-x-1/2 z-50 px-6 py-3 rounded-xl shadow-lg text-white text-sm font-medium ${toast.ok ? "bg-green-600" : "bg-red-600"}`}>
          {toast.msg}
        </div>
      )}
      <div className="bg-white rounded-xl shadow-md p-6">
        <h2 className="text-xl font-bold text-gray-800 mb-1">رفع ملفات البيانات</h2>
        <p className="text-sm text-gray-500 mb-4">الملفات تحتاج موافقة الإدارة قبل إضافتها للنظام</p>
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-400 transition-colors">
          <input type="file" id="file-upload" multiple accept=".txt,.pdf,.doc,.docx" onChange={handleUpload} className="hidden" disabled={uploading} />
          <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center gap-3">
            <Upload className="w-12 h-12 text-gray-400" />
            <div>
              <p className="text-lg font-medium text-gray-700">اضغط لرفع الملفات</p>
              <p className="text-sm text-gray-500 mt-1">TXT, PDF, DOC, DOCX — حتى 5 ميجابايت</p>
            </div>
            {uploading && <p className="text-blue-600 font-medium animate-pulse">جاري الرفع...</p>}
          </label>
        </div>
        <div className="mt-4 bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-800 space-y-1">
          <p>• تأكد من أن الملفات تحتوي على معلومات دقيقة وموثوقة</p>
          <p>• استخدم ملفات نصية بسيطة للحصول على أفضل نتائج</p>
          <p>• يمكنك رفع عدة ملفات في نفس الوقت</p>
        </div>
      </div>
      <div className="bg-white rounded-xl shadow-md p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-gray-800">الملفات المرفوعة</h2>
            <p className="text-sm text-gray-500">حالة ملفاتك</p>
          </div>
          <button onClick={loadFiles} disabled={loading} className="flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50 transition-colors">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> تحديث
          </button>
        </div>
        {loading ? (
          <div className="text-center py-12 text-gray-400"><RefreshCw className="w-8 h-8 mx-auto mb-2 animate-spin" /><p>جاري التحميل...</p></div>
        ) : files.length === 0 ? (
          <div className="text-center py-12 text-gray-400"><FileText className="w-12 h-12 mx-auto mb-3" /><p>لم تقم برفع أي ملفات بعد</p></div>
        ) : (
          <div className="space-y-3">
            {files.map(f => (
              <div key={f.file_id} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3 flex-1">
                    <FileText className="w-5 h-5 text-blue-500 mt-0.5 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="font-medium text-gray-900 truncate">{f.name}</span>
                        {badge(f.status)}
                      </div>
                      <p className="text-xs text-gray-500">{fmtSize(f.size_bytes)} · {fmtDate(f.uploaded_at)}</p>
                      {f.status === "approved" && f.kb_id && <p className="text-xs text-green-600 mt-1">✓ أضيف لقاعدة المعرفة #{f.kb_id}</p>}
                      {f.status === "rejected" && f.rejection_reason && <p className="text-xs text-red-600 mt-1"><span className="font-medium">سبب الرفض:</span> {f.rejection_reason}</p>}
                    </div>
                  </div>
                  {f.status === "pending" && (
                    <button onClick={() => handleDelete(f.file_id)} className="p-1.5 rounded-lg text-red-400 hover:text-red-600 hover:bg-red-50 transition-colors flex-shrink-0">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
