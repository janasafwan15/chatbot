// frontend/src/api/files.ts
import { apiFetch } from "./http";

export interface FileOut {
  file_id: number;
  name: string;
  file_type: string;
  size_bytes: number;
  uploaded_by: number | null;
  uploaded_by_name: string | null;
  uploaded_at: string;
  status: "pending" | "approved" | "rejected";
  rejection_reason?: string | null;
  reviewed_by?: number | null;
  reviewed_at?: string | null;
  kb_id?: number | null;
}

export interface FileDetailOut extends FileOut {
  content: string;
}

export interface FileStats {
  pending_count: number;
  approved_count: number;
  rejected_count: number;
  total_count: number;
}

// ── Upload ──────────────────────────────────────────────────

/** يقرأ ملف كنص ويرفعه للسيرفر */
export async function uploadFile(file: File): Promise<FileDetailOut> {
  const content = await readFileAsText(file);

  return apiFetch<FileDetailOut>("/files", {
    method: "POST",
    body: {
      name:       file.name,
      content,
      file_type:  file.type || "text/plain",
      size_bytes: file.size,
    },
  });
}

/**
 * يقرأ الملف ويحوّله لنص قابل للإرسال للسيرفر.
 * - النصية (.txt): يقرأها مباشرة كـ UTF-8.
 * - PDF / DOCX / DOC: يحوّلها لـ base64 data URL — الباكند يستخرج النص منها.
 */
async function readFileAsText(file: File): Promise<string> {
  // ملفات نصية عادية فقط
  if (file.type === "text/plain" || file.name.endsWith(".txt")) {
    return readPlainText(file);
  }

  // PDF و DOCX و DOC — نرسلها كـ base64 والباكند يفكّها
  return readAsBase64DataUrl(file);
}

function readPlainText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload  = () => resolve(reader.result as string);
    reader.onerror = () => reject(new Error("فشل قراءة الملف"));
    reader.readAsText(file, "UTF-8");
  });
}

/** يقرأ الملف كـ base64 data URL */
function readAsBase64DataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload  = () => resolve(reader.result as string);
    reader.onerror = () => reject(new Error("فشل قراءة الملف"));
    reader.readAsDataURL(file);
  });
}

// ── List ────────────────────────────────────────────────────

export async function listFiles(status?: "pending" | "approved" | "rejected"): Promise<FileOut[]> {
  const qs = status ? `?status=${status}` : "";
  return apiFetch<FileOut[]>(`/files${qs}`);
}

// ── Preview Text ─────────────────────────────────────────────

export interface FilePreviewText {
  file_id: number;
  name: string;
  file_type: string;
  text_preview: string;
  truncated: boolean;
  char_count: number;
}

export async function getFilePreviewText(fileId: number): Promise<FilePreviewText> {
  return apiFetch<FilePreviewText>(`/files/${fileId}/preview-text`);
}

// ── Detail ──────────────────────────────────────────────────

export async function getFile(fileId: number): Promise<FileDetailOut> {
  return apiFetch<FileDetailOut>(`/files/${fileId}`);
}

// ── Approve ─────────────────────────────────────────────────

export async function approveFile(fileId: number): Promise<{ ok: boolean; kb_id: number }> {
  return apiFetch(`/files/${fileId}/approve`, { method: "POST" });
}

// ── Reject ──────────────────────────────────────────────────

export async function rejectFile(
  fileId: number,
  rejectionReason: string
): Promise<{ ok: boolean }> {
  return apiFetch(`/files/${fileId}/reject`, {
    method: "POST",
    body: { rejection_reason: rejectionReason },
  });
}

// ── Delete ──────────────────────────────────────────────────

export async function deleteFile(fileId: number): Promise<{ ok: boolean }> {
  return apiFetch(`/files/${fileId}`, { method: "DELETE" });
}

// ── Stats ────────────────────────────────────────────────────

export async function getFilesStats(): Promise<FileStats> {
  return apiFetch<FileStats>("/files/stats/summary");
}