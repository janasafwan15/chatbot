/**
 * ragService.ts — خدمة RAG مع Streaming Animation (Typewriter Effect)
 *
 * الـ backend الحالي لا يدعم SSE streaming، لذلك:
 *   1) نجيب الجواب الكامل من الـ API
 *   2) نعرضه بشكل تدريجي (typewriter) لتجربة احترافية
 *   3) عند ربط streaming حقيقي مستقبلاً: فقط استبدل منطق fetch في askStreaming
 */

import { getApiBase } from "../api/http";

export type AskResponse = {
  answer: string;
  conversation_id?: number;
  mode?: string;
  intent?: string | null;
  category?: string | null;
  best_score?: number;
  confidence?: number;
  retrieval_mode?: string;
  latency_ms?: number;
  message_id?: number;
  user_message_id?: number;
};

export type StreamingCallbacks = {
  onChunk: (chunk: string, fullText: string) => void;
  onComplete: (response: AskResponse) => void;
  onError: (error: Error) => void;
};

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

function getCharDelay(textLength: number): number {
  if (textLength < 100) return 18;
  if (textLength < 300) return 12;
  if (textLength < 600) return 7;
  return 4;
}

export const ragService = {
  async checkConnection(): Promise<boolean> {
    try {
      const base = getApiBase();
      const r = await fetch(`${base}/health-rag`);
      return r.ok;
    } catch {
      return false;
    }
  },

  async ask(question: string, conversationId?: number | null): Promise<AskResponse> {
    const base = getApiBase();
    const r = await fetch(`${base}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, conversation_id: conversationId ?? null }),
    });
    if (!r.ok) {
      const t = await r.text();
      throw new Error(t || `HTTP ${r.status}`);
    }
    return r.json() as Promise<AskResponse>;
  },

  /**
   * askStreaming — Typewriter effect على الجواب.
   *
   * المكوّن يستدعي:
   *   ragService.askStreaming(question, convId, {
   *     onChunk: (_, full) => setDisplayedText(full),
   *     onComplete: (res) => setFinalData(res),
   *     onError: (e) => setError(e.message),
   *   });
   */
  async askStreaming(
    question: string,
    conversationId: number | null | undefined,
    callbacks: StreamingCallbacks
  ): Promise<void> {
    const { onChunk, onComplete, onError } = callbacks;

    let response: AskResponse;
    try {
      response = await this.ask(question, conversationId);
    } catch (err) {
      onError(err instanceof Error ? err : new Error(String(err)));
      return;
    }

    const answer = response.answer || "";
    if (!answer || answer.length < 5) {
      onChunk(answer, answer);
      onComplete(response);
      return;
    }

    const charDelay = getCharDelay(answer.length);
    const useWordMode = answer.length > 200;
    let displayed = "";

    if (useWordMode) {
      const words = answer.split(" ");
      for (const word of words) {
        displayed += (displayed ? " " : "") + word;
        onChunk(word + " ", displayed);
        await delay(charDelay * 1.5);
      }
    } else {
      for (const char of answer) {
        displayed += char;
        onChunk(char, displayed);
        await delay(charDelay);
      }
    }

    onComplete(response);
  },
};