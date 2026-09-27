import { request } from "./http";

export function login(username, password) {
  return request("/auth/login", {
    method: "POST",
    json:   { username, password },
    auth:   false,
  });
}

export function register(username, password) {
  return request("/auth/register", {
    method: "POST",
    json:   { username, password },
    auth:   false,
  });
}

// Identité et rôle de l'utilisateur, tels que connus du backend.
export function fetchCurrentUser() {
  return request("/auth/me");
}
