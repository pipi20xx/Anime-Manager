/**
 * Subscription API — RSS 订阅接口
 */
import { api } from './client'

export const subscriptionApi = {
  // --- Feeds ---
  getFeeds: () => api.get<any>('/api/feeds'),
  saveFeed: (body: any) => api.post<any>('/api/feeds', body),
  deleteFeed: (id: number) => api.delete<any>(`/api/feeds/${id}`),
  getFeedItems: (id: number) => api.get<any>(`/api/feeds/${id}/items`),
  resetFeedHistory: (id: number) => api.post<any>(`/api/feeds/${id}/reset`),
  syncJackettFeeds: () => api.post<any>('/api/feeds/sync-jackett'),

  // --- Rules ---
  getRules: () => api.get<any>('/api/rules'),
  saveRule: (body: any) => api.post<any>('/api/rules', body),
  deleteRule: (id: number) => api.delete<any>(`/api/rules/${id}`),
  getRuleHistory: (ruleId: number) => api.get<any>(`/api/rules/${ruleId}/history`),
  getAllRuleHistory: () => api.get<any>('/api/rules/history/all'),

  // --- Actions ---
  runNow: () => api.post<any>('/api/rss/run'),
  retryRecognition: () => api.post<any>('/api/rss/recognition/retry'),
  clearRecognitionCache: () => api.post<any>('/api/rss/recognition/clear'),
  getDownloadHistory: () => api.get<any>('/api/rss/history'),
  saveDownloadHistory: (body: any) => api.post<any>('/api/rss/history', body),
  deleteDownloadHistory: (guid: string) => api.delete<any>(`/api/rss/history/${guid}`),
  previewRule: (body: any) => api.post<any>('/api/rss/preview', body),

  // --- Detect Tasks ---
  getDetectTasks: () => api.get<any>('/api/detect/tasks'),
  saveDetectTask: (body: any) => api.post<any>('/api/detect/tasks', body),
  previewDetect: (body: any) => api.post<any>('/api/detect/preview', body),
  detectAndSubscribe: (body: any) => api.post<any>('/api/detect/subscribe', body),
  deleteDetectTask: (taskId: string) => api.delete<any>(`/api/detect/tasks/${taskId}`),
  runDetectTask: (taskId: string) => api.post<any>(`/api/detect/tasks/${taskId}/run`),

  // --- Subscriptions ---
  getSubscriptions: () => api.get<any>('/api/subscriptions'),
  saveSubscription: (body: any) => api.post<any>('/api/subscriptions', body),
  deleteSubscription: (id: number) => api.delete<any>(`/api/subscriptions/${id}`),
  clearAllSubscriptions: () => api.delete<any>('/api/subscriptions/clear_all'),
  getSubscriptionEpisodes: (subId: number) => api.get<any>(`/api/subscriptions/${subId}/episodes`),
  clearSubscriptionEpisodes: (subId: number) => api.delete<any>(`/api/subscriptions/${subId}/episodes`),
  fillSubscription: (subId: number) => api.post<any>(`/api/subscriptions/${subId}/fill`),
  jackettFill: (subId: number, indexer?: string) => api.post<any>(`/api/subscriptions/${subId}/fill`, { indexer }),

  // --- Subscription Templates ---
  getTemplates: () => api.get<any>('/api/subscriptions/templates'),
  saveTemplate: (body: any) => api.post<any>('/api/subscriptions/templates', body),
  deleteTemplate: (id: number) => api.delete<any>(`/api/subscriptions/templates/${id}`),

  // --- TMDB Blocklist ---
  getTmdbBlocklist: () => api.get<any>('/api/tmdb-blocklist'),
  addTmdbBlocklistItem: (body: any) => api.post<any>('/api/tmdb-blocklist', body),
  removeTmdbBlocklistItem: (id: number) => api.delete<any>(`/api/tmdb-blocklist/${id}`),
}
