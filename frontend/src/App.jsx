import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { useAuth } from "./context/useAuth";
import Login from "./pages/Login";
import Register from "./pages/Register";
import AdminDashboard from "./pages/AdminDashboard";
import AdminHistory from "./pages/AdminHistory";
import AdminChat from "./pages/AdminChat";
import ChatLayout from "./components/ChatLayout";

// Ces gardes ne font que de la navigation : les droits sont vérifiés par le
// backend sur chaque route de l'API.
function SessionGate({ children }) {
  const { isChecking } = useAuth();
  if (isChecking) {
    return (
      <div className="min-h-screen flex items-center justify-center text-sm text-gray-400">
        Chargement...
      </div>
    );
  }
  return children;
}

function PublicRoute({ children }) {
  const { isAuthenticated, isAdmin } = useAuth();
  if (!isAuthenticated) return children;
  return <Navigate to={isAdmin ? "/admin/dashboard" : "/"} replace />;
}

function ProtectedUserRoute({ children }) {
  const { isAuthenticated, isAdmin } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (isAdmin) return <Navigate to="/admin/dashboard" replace />;
  return children;
}

function ProtectedAdminRoute({ children }) {
  const { isAuthenticated, isAdmin } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (!isAdmin) return <Navigate to="/" replace />;
  return children;
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <SessionGate>
          <Routes>
            <Route path="/login"    element={<PublicRoute><Login /></PublicRoute>} />
            <Route path="/register" element={<PublicRoute><Register /></PublicRoute>} />

            <Route path="/" element={<ProtectedUserRoute><ChatLayout /></ProtectedUserRoute>} />

            <Route path="/admin/chat"      element={<ProtectedAdminRoute><AdminChat /></ProtectedAdminRoute>} />
            <Route path="/admin/dashboard" element={<ProtectedAdminRoute><AdminDashboard /></ProtectedAdminRoute>} />
            <Route path="/admin/history"   element={<ProtectedAdminRoute><AdminHistory /></ProtectedAdminRoute>} />

            <Route path="*" element={<Navigate to="/login" replace />} />
          </Routes>
        </SessionGate>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
