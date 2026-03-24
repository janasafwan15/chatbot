import { apiFetch } from "./http";

export async function submitConversationRating(
  conversation_id: number,
  stars: number,
  comment?: string
) {
  return apiFetch("/conversation-rating", {
    method: "POST",
    body: {
      conversation_id,
      stars,
      comment: comment?.trim() || null,
    },
  });
}
