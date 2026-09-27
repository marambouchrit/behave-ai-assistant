import { request } from "./http";

export const DEFAULT_CHAT_TITLE = "Nouvelle conversation";

export async function sendMessage(question, chatId) {
  const data = await request("/chat", {
    method: "POST",
    json:   { question, chat_id: chatId },
  });
  return {
    content: data.answer,
    module:  data.module,
    sources: data.sources,
  };
}

// Modules BeHave présents dans l'index documentaire.
export async function fetchModules() {
  const data = await request("/modules");
  return data.modules;
}

export async function checkHealth() {
  try {
    const data = await request("/health", { auth: false });
    return data.status === "ok";
  } catch {
    return false;
  }
}

export function fetchChats() {
  return request("/chats");
}

export function createChat(title = DEFAULT_CHAT_TITLE) {
  return request("/chats", { method: "POST", json: { title } });
}

export function renameChat(chatId, newTitle) {
  return request(`/chats/${chatId}`, { method: "PATCH", json: { title: newTitle } });
}

export function deleteChat(chatId) {
  return request(`/chats/${chatId}`, { method: "DELETE" });
}

// Échanges visibles d'un chat, du plus ancien au plus récent.
export async function fetchChatTurns(chatId) {
  const data = await request(`/chats/${chatId}/messages`);
  return data.turns;
}

// Soft reset : masque les échanges du chat (conservés côté admin).
export function resetChat(chatId) {
  return request(`/chats/${chatId}/messages`, { method: "DELETE" });
}
