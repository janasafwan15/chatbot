import { apiFetch } from "./http";

export const RatingsAPI = {
  summary: (days: number, token: string) =>
    apiFetch(`/stats/stars-overview?days=${days}`, { token }),

  daily: (days: number, token: string) =>
    apiFetch(`/stats/stars-weekly?days=${days}`, { token }),

  recent: (limit: number, days: number, token: string) =>
    apiFetch(`/stats/recent-feedback?limit=${limit}&days=${days}`, { token }),
};