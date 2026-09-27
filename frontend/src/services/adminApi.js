import { request, uploadWithProgress } from "./http";

export function fetchDocuments() {
  return request("/admin/documents");
}

// metadata : { module, title } optionnels, enregistrés dans le manifeste.
export function uploadDocument(file, onProgress, metadata = {}) {
  const formData = new FormData();
  formData.append("file", file);
  if (metadata.module?.trim()) formData.append("module", metadata.module.trim());
  if (metadata.title?.trim())  formData.append("title",  metadata.title.trim());

  return uploadWithProgress("/admin/upload", formData, onProgress);
}

export function deleteDocument(filename) {
  return request(`/admin/documents/${encodeURIComponent(filename)}`, { method: "DELETE" });
}

export function fetchHistory(skip = 0, limit = 20) {
  return request(`/admin/history?skip=${skip}&limit=${limit}`);
}
