import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchCurrentUser, login as loginRequest } from "../services/authApi";
import { setUnauthorizedHandler } from "../services/http";
import { clearSession, getStoredUser, getToken, saveSession, updateStoredUser } from "../services/session";
import { AuthContext } from "./useAuth";

/**
 * Session de l'utilisateur connecté.
 *
 * Le rôle stocké dans le navigateur ne sert qu'à l'affichage : au chargement,
 * il est revérifié auprès du backend (/auth/me), qui reste seul juge des
 * droits. Toute réponse 401 (session expirée, compte supprimé) déconnecte ;
 * les routes protégées redirigent alors vers /login.
 */
export function AuthProvider({ children }) {
  const [user, setUser]             = useState(() => (getToken() ? getStoredUser() : null));
  const [isChecking, setIsChecking] = useState(() => Boolean(getToken()));

  const logout = useCallback(() => {
    clearSession();
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  useEffect(() => {
    if (!getToken()) return;
    fetchCurrentUser()
      .then((me) => {
        const current = { username: me.username, role: me.role };
        updateStoredUser(current);
        setUser(current);
      })
      // Backend injoignable : on garde la session, les appels suivants le signaleront.
      .catch((err) => { if (!err.isNetworkError) logout(); })
      .finally(() => setIsChecking(false));
  }, [logout]);

  const login = useCallback(async (username, password) => {
    const data    = await loginRequest(username, password);
    const current = { username: data.username, role: data.role };
    saveSession(data.access_token, current);
    setUser(current);
    return current;
  }, []);

  const value = useMemo(() => ({
    user,
    isAuthenticated: user !== null,
    isAdmin:         user?.role === "admin",
    isChecking,
    login,
    logout,
  }), [user, isChecking, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
