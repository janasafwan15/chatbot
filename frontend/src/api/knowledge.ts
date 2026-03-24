import { apiFetch } from "./http";

export type KnowledgeItem = {
  kb_id: number;
  title_ar: string;
  content_ar: string;
  category: string;
  is_active: boolean;
  intent_code?: string | null;
};

export type KnowledgeCreate = {
  title_ar: string;
  content_ar: string;
  category: string;
  intent_code?: string | null;
  external_links?: string | null;
  is_active: boolean;
};

export const listKnowledge = (token?: string) =>
  apiFetch<KnowledgeItem[]>("/kb", { token });

export const createKnowledge = (token: string, body: KnowledgeCreate) =>
  apiFetch<KnowledgeItem>("/kb", { token, method: "POST", body });

export const updateKnowledge = (token: string, id: number, body: KnowledgeCreate) =>
  apiFetch<KnowledgeItem>(`/kb/${id}`, { token, method: "PUT", body });

export const deleteKnowledge = (token: string, id: number) =>
  apiFetch<void>(`/kb/${id}`, { token, method: "DELETE" });
