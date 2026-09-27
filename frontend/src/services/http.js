import { getToken } from "./session";

export const API_BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

/**
 * Erreur d'appel API.
 * status = 0 et isNetworkError = true quand le backend est injoignable.
 */
export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.status = status;
    this.isNetworkError = status === 0;
  }
}

// Appelé sur toute réponse 401 d'une requête authentifiée (session expirée,
// compte supprimé) : AuthContext y branche la déconnexion.
let onUnauthorized = null;

export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

const NETWORK_ERROR_MESSAGE =
  "Serveur injoignable. Vérifiez que le backend FastAPI est démarré.";

// FastAPI renvoie `detail` en texte (HTTPException) ou en liste (erreur de validation).
function _errorMessage(payload, status) {
  const detail = payload?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return "Requête invalide.";
  return `Erreur API : ${status}`;
}

function _authHeaders(auth) {
  const token = auth ? getToken() : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function _handleError(status, readPayload, auth) {
  if (status === 401 && auth) onUnauthorized?.();
  const payload = await readPayload().catch(() => null);
  throw new ApiError(_errorMessage(payload, status), status);
}

/**
 * Requête JSON vers l'API.
 *
 * @param {string} path
 * @param {object} options  method, json (corps sérialisé en JSON), auth (défaut true)
 */
export async function request(path, { method = "GET", json, auth = true } = {}) {
  const headers = _authHeaders(auth);
  if (json !== undefined) headers["Content-Type"] = "application/json";

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: json !== undefined ? JSON.stringify(json) : undefined,
    });
  } catch {
    throw new ApiError(NETWORK_ERROR_MESSAGE, 0);
  }

  if (!response.ok) await _handleError(response.status, () => response.json(), auth);
  return response.status === 204 ? null : response.json();
}

/**
 * Envoi multipart avec suivi de progression (XMLHttpRequest : fetch ne
 * fournit pas la progression de l'upload).
 */
export function uploadWithProgress(path, formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(Math.round((event.loaded / event.total) * 100));
    };

    xhr.onload = () => {
      const parse = async () => JSON.parse(xhr.responseText);
      if (xhr.status >= 200 && xhr.status < 300) {
        parse().then(resolve, () => resolve(null));
      } else {
        _handleError(xhr.status, parse, true).catch(reject);
      }
    };
    xhr.onerror = () => reject(new ApiError(NETWORK_ERROR_MESSAGE, 0));

    xhr.open("POST", `${API_BASE_URL}${path}`);
    const token = getToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.send(formData);
  });
}
