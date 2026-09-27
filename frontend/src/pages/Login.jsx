import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../context/useAuth";
import Alert from "../components/common/Alert";
import Logo from "../components/common/Logo";

function Login() {
  const { login }   = useAuth();
  const justSignedUp = useLocation().state?.registered === true;

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState("");
  const [isLoading, setIsLoading] = useState(false);

  // Une fois connecté, PublicRoute redirige selon le rôle.
  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      await login(username, password);
    } catch (err) {
      setError(err.message);
      setIsLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-behave-page flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 bg-behave-navy rounded-xl flex items-center justify-center mb-3">
            <Logo size={22} fillOpacity={0.6} />
          </div>
          <h1 className="text-xl font-semibold text-behave-navy">BeHave Assistant</h1>
          <p className="text-sm text-gray-500 mt-1">Connectez-vous pour continuer</p>
        </div>

        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">

            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-gray-700" htmlFor="username">
                Nom d'utilisateur
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Votre username"
                required
                autoComplete="username"
                className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-lg
                           focus:outline-none focus:ring-2 focus:ring-behave-cyan focus:border-transparent
                           placeholder:text-gray-300 transition-all"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-gray-700" htmlFor="password">
                Mot de passe
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                autoComplete="current-password"
                className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-lg
                           focus:outline-none focus:ring-2 focus:ring-behave-cyan focus:border-transparent
                           placeholder:text-gray-300 transition-all"
              />
            </div>

            {justSignedUp && !error && (
              <Alert variant="success">Compte créé. Vous pouvez vous connecter.</Alert>
            )}
            {error && <Alert>{error}</Alert>}

            <button
              type="submit"
              disabled={isLoading || !username || !password}
              className="w-full bg-behave-navy text-white text-sm font-medium py-2.5 rounded-lg
                         hover:bg-behave-navy-dark transition-colors
                         disabled:opacity-50 disabled:cursor-not-allowed
                         flex items-center justify-center gap-2"
            >
              {isLoading ? (
                <>
                  <svg className="animate-spin" width="14" height="14" viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="12" r="10" stroke="white" strokeWidth="3" strokeOpacity="0.3"/>
                    <path d="M12 2 A10 10 0 0 1 22 12" stroke="white" strokeWidth="3" strokeLinecap="round"/>
                  </svg>
                  Connexion...
                </>
              ) : "Se connecter"}
            </button>

          </form>

          <p className="text-center text-sm text-gray-500 mt-4">
            Pas encore de compte ?{" "}
            <Link to="/register" className="text-behave-navy font-medium hover:underline">
              S'inscrire
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}

export default Login;