import { createContext, useContext } from "react";

export const AuthContext = createContext(null);

// { user, isAuthenticated, isAdmin, isChecking, login, logout } — voir AuthProvider.
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth doit être utilisé dans un <AuthProvider>.");
  return context;
}
