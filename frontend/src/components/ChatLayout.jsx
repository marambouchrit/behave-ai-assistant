import { useState, useEffect, useCallback, useRef } from "react";
import { FiPlus, FiTrash2, FiEdit2, FiCheck, FiX, FiMessageSquare } from "react-icons/fi";
import { DEFAULT_CHAT_TITLE, fetchChats, createChat, renameChat, deleteChat } from "../services/api";
import { useAuth } from "../context/useAuth";
import ChatWindow from "./ChatWindow";
import Logo from "./common/Logo";

/**
 * Liste des chats de l'utilisateur + fenêtre du chat actif.
 *
 * @param {boolean} showAccountFooter  Affiche le nom et le bouton de déconnexion
 *                                     en bas de la liste (false quand la page
 *                                     fournit déjà sa propre navigation, ex. admin).
 */
function ChatLayout({ showAccountFooter = true }) {
  const { user, logout } = useAuth();

  const [chats,        setChats]        = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);
  const [editingId,    setEditingId]    = useState(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [isLoading,    setIsLoading]    = useState(true);
  const [error,        setError]        = useState("");

  const activeChat = chats.find((c) => c.id === activeChatId);

  const openNewChat = useCallback(async () => {
    const chat = await createChat(DEFAULT_CHAT_TITLE);
    setChats((prev) => [chat, ...prev]);
    setActiveChatId(chat.id);
  }, []);

  // Garde contre la double exécution des effets en mode StrictMode (dev), qui
  // créerait deux chats vides pour un nouvel utilisateur.
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    const init = async () => {
      try {
        const data = await fetchChats();
        setChats(data.chats);
        if (data.chats.length > 0) setActiveChatId(data.chats[0].id);
        else await openNewChat();
      } catch (err) {
        setError(err.message);
      } finally {
        setIsLoading(false);
      }
    };
    init();
  }, [openNewChat]);

  const runAction = async (action) => {
    setError("");
    try {
      await action();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleNewChat = () => runAction(openNewChat);

  // Le backend renomme un chat à sa première question : la liste n'est
  // rechargée que si le chat actif porte encore le titre par défaut.
  const handleMessageSent = useCallback(async () => {
    if (activeChat?.title !== DEFAULT_CHAT_TITLE) return;
    try {
      const data = await fetchChats();
      setChats(data.chats);
    } catch {
      // Titre non rafraîchi : sans conséquence, il le sera au prochain chargement.
    }
  }, [activeChat?.title]);

  const handleDelete = (chatId, e) => {
    e.stopPropagation();
    runAction(async () => {
      await deleteChat(chatId);
      const remaining = chats.filter((c) => c.id !== chatId);
      setChats(remaining);
      if (activeChatId !== chatId) return;
      if (remaining.length > 0) setActiveChatId(remaining[0].id);
      else await openNewChat();
    });
  };

  const handleStartRename = (chat, e) => {
    e.stopPropagation();
    setEditingId(chat.id);
    setEditingTitle(chat.title);
  };

  const handleCancelRename = () => {
    setEditingId(null);
    setEditingTitle("");
  };

  const handleConfirmRename = (chatId) => {
    const title = editingTitle.trim();
    if (!title) return;
    runAction(async () => {
      const updated = await renameChat(chatId, title);
      setChats((prev) => prev.map((c) => (c.id === chatId ? updated : c)));
    }).finally(handleCancelRename);
  };

  return (
    <div className="flex flex-1 h-screen overflow-hidden">

      <div className="w-64 flex-shrink-0 bg-behave-sidebar flex flex-col">

        <div className="px-4 py-4 border-b border-white/10">
          <div className="flex items-center gap-2 mb-4">
            <Logo size={22} />
            <span className="text-white text-sm font-semibold">BeHave Assistant</span>
          </div>

          <button
            onClick={handleNewChat}
            className="w-full flex items-center justify-center gap-2 bg-behave-cyan
                       hover:bg-behave-cyan-dark text-white text-sm font-medium py-2 px-3
                       rounded-lg transition-colors"
          >
            <FiPlus size={15} />
            {DEFAULT_CHAT_TITLE}
          </button>
        </div>

        {error && (
          <div className="mx-2 mt-2 flex items-start gap-2 rounded-lg bg-red-500/15 px-3 py-2 text-xs text-red-200">
            <span className="flex-1">{error}</span>
            <button onClick={() => setError("")} aria-label="Fermer l'erreur" className="hover:text-white">
              <FiX size={12} />
            </button>
          </div>
        )}

        <div className="flex-1 overflow-y-auto py-2">
          {isLoading ? (
            <div className="px-4 py-3 text-white/40 text-xs">Chargement...</div>
          ) : chats.length === 0 ? (
            <div className="px-4 py-3 text-white/40 text-xs">Aucune conversation</div>
          ) : (
            chats.map((chat) => (
              <div
                key={chat.id}
                onClick={() => setActiveChatId(chat.id)}
                className={[
                  "group flex items-center gap-2 px-3 py-2.5 mx-2 rounded-lg cursor-pointer",
                  "transition-colors duration-100",
                  activeChatId === chat.id
                    ? "bg-white/15 text-white"
                    : "text-white/60 hover:bg-white/8 hover:text-white/90",
                ].join(" ")}
              >
                <FiMessageSquare size={13} className="flex-shrink-0 opacity-60" />

                {editingId === chat.id ? (
                  <input
                    autoFocus
                    value={editingTitle}
                    onChange={(e) => setEditingTitle(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter")  handleConfirmRename(chat.id);
                      if (e.key === "Escape") handleCancelRename();
                    }}
                    onClick={(e) => e.stopPropagation()}
                    maxLength={200}
                    className="flex-1 bg-white/10 text-white text-xs rounded px-1.5 py-0.5
                               outline-none border border-behave-cyan min-w-0"
                  />
                ) : (
                  <span className="flex-1 text-xs truncate">{chat.title}</span>
                )}

                <div
                  className={[
                    "flex items-center gap-1 flex-shrink-0",
                    editingId === chat.id ? "flex" : "hidden group-hover:flex",
                  ].join(" ")}
                  onClick={(e) => e.stopPropagation()}
                >
                  {editingId === chat.id ? (
                    <>
                      <button
                        onClick={() => handleConfirmRename(chat.id)}
                        className="text-green-400 hover:text-green-300 p-0.5"
                        title="Confirmer"
                      >
                        <FiCheck size={12} />
                      </button>
                      <button
                        onClick={handleCancelRename}
                        className="text-red-400 hover:text-red-300 p-0.5"
                        title="Annuler"
                      >
                        <FiX size={12} />
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={(e) => handleStartRename(chat, e)}
                        className="text-white/40 hover:text-white/80 p-0.5"
                        title="Renommer"
                      >
                        <FiEdit2 size={12} />
                      </button>
                      <button
                        onClick={(e) => handleDelete(chat.id, e)}
                        className="text-white/40 hover:text-red-400 p-0.5"
                        title="Supprimer"
                      >
                        <FiTrash2 size={12} />
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        {showAccountFooter && (
          <div className="px-4 py-3 border-t border-white/10 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-full bg-behave-cyan flex items-center
                              justify-center text-white text-xs font-semibold">
                {user?.username?.charAt(0).toUpperCase() || "U"}
              </div>
              <span className="text-white/70 text-xs truncate max-w-[90px]">
                {user?.username}
              </span>
            </div>
            <button
              onClick={logout}
              className="text-white/40 hover:text-white/80 text-xs transition-colors"
              title="Se déconnecter"
            >
              Déconnexion
            </button>
          </div>
        )}
      </div>

      <div className="flex-1 min-w-0">
        {activeChatId ? (
          <ChatWindow chatId={activeChatId} onMessageSent={handleMessageSent} />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">
            Sélectionnez ou créez une conversation
          </div>
        )}
      </div>

    </div>
  );
}

export default ChatLayout;
