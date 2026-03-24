import { apiFetch } from "./http";

export async function sendFeedback(data: {
  conversation_id?: number;
  message_id?: number;
  is_positive: boolean;
}) {
  return apiFetch("/feedback", { method: "POST", body: data });
}
