import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Bot, User, Settings, MessageSquare, PlusCircle, Copy, Check } from "lucide-react";

import { ragService } from "../services/ragService";
import { OllamaSettings } from "./OllamaSettings";
import { RatingModal } from "../app/components/RatingModal";
import { submitConversationRating } from "../api/conversationRating";
import { submitUnanswered } from "../api/unanswered";

// ─── Types ────────────────────────────────────────────────
interface Message {
  id: number;
  text: string;
  sender: "user" | "bot";
  timestamp: Date;
  type?: "text" | "link" | "info" | "error";
  links?: { text: string; url: string }[];
  // meta مخفية — مش للمستخدم العادي
  meta?: { intent?: string | null; category?: string | null; mode?: string | null; score?: number | null };
}

interface PersistedSession {
  conversationId: number | null;
  messages: Array<Omit<Message, "timestamp"> & { timestamp: string }>;
}

const SESSION_KEY = "hepco_chat_session";
const TIMEOUT_MS = 60_000; // 60 ثانية حد أقصى للانتظار



const WELCOME_MESSAGE: Message = {
  id: 1,
  text: "مرحباً بك في نظام الدعم الذكي لكهرباء الخليل 👋\n\nكيف يمكنني مساعدتك اليوم؟",
  sender: "bot",
  timestamp: new Date(),
  type: "text",
};

const quickQuestions = ["ساعات العمل", "رقم الهاتف", "الفاتورة", "اشتراك جديد", "تقديم شكوى"];

// ─── Copy Button Component ────────────────────────────────
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback
      const el = document.createElement("textarea");
      el.value = text;
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <button
      onClick={handleCopy}
      title="نسخ الجواب"
      className="mt-2 flex items-center gap-1 text-xs text-gray-400 hover:text-blue-500 transition-colors"
    >
      {copied ? (
        <>
          <Check className="w-3.5 h-3.5 text-green-500" />
          <span className="text-green-500">تم النسخ!</span>
        </>
      ) : (
        <>
          <Copy className="w-3.5 h-3.5" />
          <span>نسخ</span>
        </>
      )}
    </button>
  );
}

// ─── Main Component ───────────────────────────────────────
export function CitizenChatbot() {
  // ─ State ─
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [inputText, setInputText] = useState("");
  const [isTyping, setIsTyping] = useState(false);

  const [useOllama, setUseOllama] = useState(true);
  const [ollamaConnected, setOllamaConnected] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  const [conversationId, setConversationId] = useState<number | null>(null);

  const [showRatingModal, setShowRatingModal] = useState(false);
  const [ratingSent, setRatingSent] = useState(false);
  const [conversationRating, setConversationRating] = useState<{ rating: number; feedback: string } | null>(null);

  // FIX 4: timeout ref لإلغاء الانتظار
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });

  useEffect(() => { scrollToBottom(); }, [messages]);

  // ─── FIX 2: تحميل الجلسة من localStorage ────────────────
  useEffect(() => {
    try {
      const raw = localStorage.getItem(SESSION_KEY);
      if (raw) {
        const session: PersistedSession = JSON.parse(raw);
        if (session.conversationId) {
          setConversationId(session.conversationId);
        }
        if (session.messages && session.messages.length > 0) {
          const restored: Message[] = session.messages.map((m) => ({
            ...m,
            timestamp: new Date(m.timestamp),
          }));
          setMessages(restored);
        }
      }
    } catch {
      // لو في أي خطأ بالـ parse — ابدأ من جديد
      localStorage.removeItem(SESSION_KEY);
    }
    checkConnection();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ─── FIX 2: حفظ الجلسة كل ما تتغير الرسائل ────────────
  useEffect(() => {
    if (messages.length <= 1 && !conversationId) return; // لا تحفظ رسالة الترحيب فقط
    try {
      const session: PersistedSession = {
        conversationId,
        messages: messages.map((m) => ({ ...m, timestamp: m.timestamp.toISOString() })),
      };
      localStorage.setItem(SESSION_KEY, JSON.stringify(session));
    } catch {
      // storage full أو غير متاح
    }
  }, [messages, conversationId]);

  const checkConnection = async () => {
    const connected = await ragService.checkConnection();
    setOllamaConnected(connected);
    setUseOllama(connected);
  };

  // ─── FIX 5: بدء محادثة جديدة ────────────────────────────
  const handleNewChat = useCallback(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    if (abortRef.current) abortRef.current.abort();
    setIsTyping(false);
    setMessages([WELCOME_MESSAGE]);
    setConversationId(null);
    setInputText("");
    setRatingSent(false);
    setConversationRating(null);
    setShowRatingModal(false);
    localStorage.removeItem(SESSION_KEY);
    inputRef.current?.focus();
  }, []);

  // ─── FIX 4: RAG مع timeout ───────────────────────────────
  const handleSendWithRAG = async (userText: string) => {
    setIsTyping(true);

    // إعداد AbortController
    abortRef.current = new AbortController();

    // timeout بعد 60 ثانية
    timeoutRef.current = setTimeout(() => {
      abortRef.current?.abort();
    }, TIMEOUT_MS);

    try {
      const data = await ragService.ask(userText, conversationId);

      if (data?.conversation_id) setConversationId(data.conversation_id);

      // ── كشف الأسئلة غير المجابة ────────────────────────────
      // لو الـ AI بدأ الإجابة بـ UNCERTAIN: يعني ما عنده إجابة واثقة
      if (typeof data.answer === "string" && data.answer.trimStart().startsWith("UNCERTAIN:")) {
        try {
          await submitUnanswered(userText, data.conversation_id ?? conversationId ?? undefined);
        } catch {
          // نتجاهل الخطأ — ما نريد يأثر على تجربة المواطن
        }
      }

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          text: data.answer,
          sender: "bot",
          timestamp: new Date(),
          type: "text",
          // FIX 3: meta موجودة بس مش بنعرضها للمستخدم
          meta: {
            intent: data.intent ?? null,
            category: data.category ?? null,
            mode: data.mode ?? null,
            score: typeof data.best_score === "number" ? data.best_score : null,
          },
        },
      ]);
    } catch (error: any) {
      const isTimeout = error?.name === "AbortError" || String(error?.message).includes("abort");
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          text: isTimeout
            ? "⏱️ انتهى وقت الانتظار. يبدو أن الخادم مشغول.\n\nيرجى المحاولة مرة أخرى أو التواصل على: 📞 02-2282882"
            : `⚠️ صار خطأ بالاتصال مع الخادم.\n\nتفاصيل: ${String(error?.message || error)}`,
          sender: "bot",
          timestamp: new Date(),
          type: "error",
        },
      ]);
      setUseOllama(false);
      setOllamaConnected(false);
    } finally {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      setIsTyping(false);
    }
  };


  const handleSend = () => {
    if (!inputText.trim() || isTyping) return;

    const userMessage: Message = {
      id: Date.now(),
      text: inputText,
      sender: "user",
      timestamp: new Date(),
      type: "text",
    };

    setMessages((prev) => [...prev, userMessage]);
    const msg = inputText;
    setInputText("");

    if (useOllama && ollamaConnected) {
      handleSendWithRAG(msg);
    } else {
      // الخادم غير متصل — أعطِ رسالة واضحة بدل الـ fallback القديمة
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          text: "⚠️ الخادم غير متصل حالياً.\n\nللمساعدة الفورية:\n📞 02-2282882\n🚨 الطوارئ: 100",
          sender: "bot",
          timestamp: new Date(),
          type: "text",
        },
      ]);
    }
  };

  const handleConversationRating = async (rating: number, feedback: string) => {
    if (!conversationId) return;
    try {
      await submitConversationRating(conversationId, rating, feedback);
      setConversationRating({ rating, feedback });
      setRatingSent(true);
      setShowRatingModal(false);
    } catch (e) {
      console.error("conversation rating error", e);
    }
  };

  // FIX 9: بتظهر الأسئلة السريعة دايماً إذا ما في رد من البوت غير رسالة الترحيب
  const botMessagesCount = messages.filter((m) => m.sender === "bot").length;
  const showQuickQuestions = botMessagesCount <= 1 && !isTyping;

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-blue-50 to-green-50" dir="rtl">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-green-600 text-white p-4 shadow-lg">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 bg-white rounded-full flex items-center justify-center shadow">
                <Bot className="w-7 h-7 text-blue-600" />
              </div>
              <div>
                <h1 className="text-xl font-bold">نظام الدعم الذكي</h1>
                <p className="text-blue-100 text-sm">كهرباء الخليل</p>
                {conversationId && (
                  <p className="text-xs text-blue-200 mt-0.5">جلسة #{conversationId}</p>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2">
              {/* FIX 6: حالة الاتصال */}
              <div className="flex items-center gap-2 bg-white/20 px-3 py-1.5 rounded-lg text-sm">
                <div className={`w-2.5 h-2.5 rounded-full ${ollamaConnected ? "bg-green-400 animate-pulse" : "bg-gray-300"}`} />
                <span>{ollamaConnected ? "متصل" : "الوضع الأساسي"}</span>
              </div>

              {/* FIX 5: زر محادثة جديدة */}
              <button
                onClick={handleNewChat}
                title="محادثة جديدة"
                className="flex items-center gap-1.5 bg-white/20 hover:bg-white/30 px-3 py-1.5 rounded-lg transition-colors text-sm font-semibold"
              >
                <PlusCircle className="w-4 h-4" />
                <span className="hidden sm:inline">جديد</span>
              </button>

              <button
                onClick={() => setShowSettings(true)}
                className="p-2 bg-white/20 hover:bg-white/30 rounded-lg transition-colors"
                title="الإعدادات"
              >
                <Settings className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="max-w-4xl mx-auto space-y-4">
          {messages.map((m) => (
            <div key={m.id} className={`flex gap-3 ${m.sender === "user" ? "justify-end" : "justify-start"}`}>
              {m.sender === "bot" && (
                <div className="w-9 h-9 bg-blue-600 rounded-full flex items-center justify-center flex-shrink-0 mt-1">
                  <Bot className="w-5 h-5 text-white" />
                </div>
              )}

              <div className={`max-w-[72%] ${m.sender === "user" ? "order-1" : ""}`}>
                <div
                  className={`rounded-2xl p-4 ${
                    m.sender === "user"
                      ? "bg-blue-600 text-white"
                      : m.type === "error"
                      ? "bg-red-50 text-red-800 border border-red-200"
                      : "bg-white text-gray-800 shadow-md"
                  }`}
                >
                  <p className="whitespace-pre-line leading-relaxed text-sm">{m.text}</p>

                  {m.links?.length ? (
                    <div className="mt-3 space-y-2">
                      {m.links.map((link, idx) => (
                        <a
                          key={idx}
                          href={link.url}
                          className="block bg-blue-50 hover:bg-blue-100 text-blue-600 px-4 py-2 rounded-lg text-center font-semibold transition-colors text-sm"
                        >
                          {link.text} ←
                        </a>
                      ))}
                    </div>
                  ) : null}

                  {/* FIX 7: زر Copy — بس للبوت */}
                  {m.sender === "bot" && m.type !== "error" && (
                    <CopyButton text={m.text} />
                  )}

                  {/* FIX 3: meta مخفية تماماً — لا يراها المستخدم */}
                </div>

                <p className="text-xs text-gray-400 mt-1 px-2">
                  {m.timestamp.toLocaleTimeString("ar-PS", { hour: "2-digit", minute: "2-digit" })}
                </p>
              </div>

              {m.sender === "user" && (
                <div className="w-9 h-9 bg-green-600 rounded-full flex items-center justify-center flex-shrink-0 mt-1">
                  <User className="w-5 h-5 text-white" />
                </div>
              )}
            </div>
          ))}

          {/* FIX 4: Typing indicator */}
          {isTyping && (
            <div className="flex gap-3 items-center">
              <div className="w-9 h-9 bg-blue-600 rounded-full flex items-center justify-center flex-shrink-0">
                <Bot className="w-5 h-5 text-white" />
              </div>
              <div className="bg-white rounded-2xl px-5 py-4 shadow-md flex items-center gap-3">
                <div className="flex gap-1">
                  <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
                <span className="text-xs text-gray-400">جاري الكتابة...</span>
                <button
                  onClick={() => {
                    abortRef.current?.abort();
                    if (timeoutRef.current) clearTimeout(timeoutRef.current);
                    setIsTyping(false);
                  }}
                  className="text-xs text-red-400 hover:text-red-600 underline mr-2"
                >
                  إلغاء
                </button>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* FIX 9: Quick Questions — بتظهر دايماً لو البوت ما رد بعد */}
      {showQuickQuestions && (
        <div className="px-4 pb-2">
          <div className="max-w-4xl mx-auto">
            <p className="text-xs text-gray-500 mb-2 font-semibold">أسئلة شائعة:</p>
            <div className="flex flex-wrap gap-2">
              {quickQuestions.map((q, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setInputText(q);
                    inputRef.current?.focus();
                  }}
                  className="bg-white hover:bg-blue-50 text-blue-600 border border-blue-100 px-3 py-1.5 rounded-full text-sm font-medium shadow-sm transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="bg-white border-t border-gray-200 p-4">
        <div className="max-w-4xl mx-auto">
          {conversationId && messages.length > 3 && !conversationRating && (
            <div className="mb-3 text-center">
              <button
                onClick={() => setShowRatingModal(true)}
                className="inline-flex items-center gap-2 px-5 py-1.5 bg-gradient-to-r from-yellow-400 to-orange-400 hover:from-yellow-500 hover:to-orange-500 text-white rounded-full font-semibold shadow-lg transition-all transform hover:scale-105 text-sm"
              >
                <MessageSquare className="w-4 h-4" />
                قيّم تجربتك
              </button>
            </div>
          )}

          {conversationRating && (
            <div className="mb-3 bg-gradient-to-r from-green-50 to-blue-50 border border-green-200 rounded-lg p-3 text-center">
              <p className="text-green-700 font-semibold text-sm">✨ شكراً لتقييمك! نقدر ملاحظاتك لتحسين خدماتنا</p>
            </div>
          )}

          <div className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder="اكتب استفسارك هنا..."
              disabled={isTyping}
              className="flex-1 border border-gray-300 rounded-full px-5 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 text-right text-sm disabled:bg-gray-50 disabled:text-gray-400"
            />
            <button
              onClick={handleSend}
              disabled={!inputText.trim() || isTyping}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white px-5 py-3 rounded-full transition-colors flex items-center gap-2 font-semibold text-sm"
            >
              إرسال
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {showSettings && <OllamaSettings onClose={() => setShowSettings(false)} onSave={checkConnection} />}
      {showRatingModal && (
        <RatingModal onClose={() => setShowRatingModal(false)} onRate={handleConversationRating} disabled={ratingSent} />
      )}
    </div>
  );
}