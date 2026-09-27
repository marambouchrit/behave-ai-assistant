import { useState, useEffect, useRef } from "react";
import Header        from "./Header";
import MessageBubble from "./MessageBubble";
import InputBar      from "./InputBar";
import Suggestions   from "./Suggestions";
import { sendMessage, fetchChatTurns, fetchModules, resetChat, checkHealth } from "../services/api";

// Message d'accueil : la liste des modules vient de l'index documentaire
// (GET /modules), jamais d'une liste écrite en dur.
const _welcomeMessage = (modules) => ({
  role: "assistant",
  content:
    "Bonjour ! Je suis **BeHave Assistant**.\n\n"
    + "Je réponds à vos questions sur la suite BeHave en me basant sur la documentation officielle Siryos"
    + (modules.length ? ` :\n\n${modules.map((m) => `- ${m}`).join("\n")}` : ".")
    + "\n\nComment puis-je vous aider ?",
});

const NO_ACTIVE_CHAT_MESSAGE = {
  role: "assistant",
  content: "Aucune conversation active. Créez ou sélectionnez un chat avant d'envoyer un message.",
};

const LOAD_ERROR_MESSAGE = {
  role: "assistant",
  content: "Impossible de charger l'historique de cette conversation.",
};

const _turnsToMessages = (turns) =>
  turns.flatMap((turn) => [
    { role: "user", content: turn.question },
    {
      role:    "assistant",
      content: turn.answer,
      module:  turn.module,
      sources: turn.sources,
    },
  ]);

/**
 * ChatWindow
 *
 * @param {number}   chatId         Identifiant du chat actif. Peut être null/undefined
 *                                  tant qu'aucun chat n'a été créé ou sélectionné —
 *                                  dans ce cas l'envoi de message est bloqué.
 * @param {function} onMessageSent  Callback appelé après chaque réponse reçue.
 *                                  Utilisé par ChatLayout pour rafraîchir la
 *                                  sidebar (auto-renommage du chat).
 */
function ChatWindow({ chatId, onMessageSent }) {
  const hasActiveChat = chatId != null;

  const [messages,  setMessages]  = useState([]);
  const [modules,   setModules]   = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isOnline,  setIsOnline]  = useState(true);
  const messagesEndRef = useRef(null);

  // Recharge les messages depuis la base quand le chat actif change.
  // `cancelled` ignore une réponse arrivée après un changement de chat.
  useEffect(() => {
    setMessages([]);
    if (!hasActiveChat) return;

    let cancelled = false;
    fetchChatTurns(chatId)
      .then((turns) => {
        if (!cancelled) setMessages(_turnsToMessages(turns));
      })
      .catch(() => {
        if (!cancelled) setMessages([LOAD_ERROR_MESSAGE]);
      });

    return () => { cancelled = true; };
  }, [chatId, hasActiveChat]);

  useEffect(() => { checkHealth().then(setIsOnline); }, []);

  // Sans modules (erreur réseau), l'accueil reste générique.
  useEffect(() => { fetchModules().then(setModules).catch(() => {}); }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSend = async (question) => {
    if (!hasActiveChat) {
      setMessages((prev) => [...prev, NO_ACTIVE_CHAT_MESSAGE]);
      return;
    }

    if (!question?.trim()) return;

    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setIsLoading(true);

    try {
      const result = await sendMessage(question, chatId);
      setMessages((prev) => [
        ...prev,
        {
          role:    "assistant",
          content: result.content,
          module:  result.module,
          sources: result.sources,
        },
      ]);
      setIsOnline(true);

      onMessageSent?.();

    } catch (err) {
      // Message affichable : panne réseau, ou erreur métier de l'API (429/503…).
      setMessages((prev) => [...prev, { role: "assistant", content: err.message }]);
      setIsOnline(!err.isNetworkError);
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = async () => {
    if (!hasActiveChat) return;
    try {
      await resetChat(chatId);
      setMessages([]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: "assistant", content: err.message }]);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-behave-chat">
      <Header onReset={handleReset} isOnline={isOnline} />

      <Suggestions onSelect={handleSend} isLoading={isLoading} />

      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-2">
        <MessageBubble message={_welcomeMessage(modules)} />
        {messages.map((msg, index) => (
          <MessageBubble key={index} message={msg} />
        ))}
        {isLoading && (
          <div className="flex items-center gap-2 text-gray-400 text-sm px-2">
            <div className="flex gap-1">
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="w-2 h-2 bg-behave-cyan rounded-full animate-bounce"
                  style={{ animationDelay: `${i * 0.15}s` }}
                />
              ))}
            </div>
            BeHave réfléchit...
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <InputBar onSend={handleSend} isLoading={isLoading} />
    </div>
  );
}

export default ChatWindow;