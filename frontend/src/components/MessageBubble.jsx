import { FiDatabase, FiFileText } from "react-icons/fi";
import { useAuth } from "../context/useAuth";
import Logo from "./common/Logo";
import Markdown from "./common/Markdown";
import { formatSource } from "../utils/format";

/**
 * MessageBubble
 *
 * Affiche un message utilisateur ou assistant.
 *
 * @param {object}   message
 * @param {string}   message.role         "user" | "assistant"
 * @param {string}   message.content      Texte du message (Markdown pour l'assistant)
 * @param {string}   message.module       Module BeHave source (optionnel, messages assistant)
 * @param {object[]} message.sources      Extraits utilisés (optionnel, messages assistant)
 *                                        [{document, title, page, section}]
 */
function MessageBubble({ message }) {
  const { user } = useAuth();
  const isUser   = message.role === "user";
  const sources  = message.sources ?? [];

  return (
    <div
      className={`flex items-end gap-2 mb-4 ${isUser ? "flex-row-reverse" : "flex-row"}`}
    >
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center
                       flex-shrink-0
                       ${isUser ? "bg-behave-cyan" : "bg-behave-navy"}`}
      >
        {isUser ? (
          <span className="text-white text-xs font-semibold">
            {user?.username?.charAt(0).toUpperCase() || "U"}
          </span>
        ) : (
          <Logo size={15} fillOpacity={0.5} />
        )}
      </div>

      <div className="max-w-[73%]">
        <div
          className={`px-4 py-2.5 text-sm leading-relaxed
          ${
            isUser
              ? "bg-behave-navy text-white rounded-2xl rounded-br-sm whitespace-pre-wrap"
              : "bg-white text-gray-800 border border-[#D0DCF0] rounded-2xl rounded-bl-sm"
          }`}
        >
          {isUser ? message.content : <Markdown>{message.content}</Markdown>}

          {!isUser && (message.module || sources.length > 0) && (
            <div className="flex gap-1.5 flex-wrap mt-3 pt-2.5 border-t border-[#E8EEF8]">
              {message.module && (
                <span
                  className="inline-flex items-center gap-1 bg-[#EAF2FC]
                                 border border-[#A8C8E8] rounded px-2 py-0.5
                                 text-xs text-[#1A4A8C]"
                >
                  <FiDatabase size={10} />
                  {message.module}
                </span>
              )}
              {sources.map((source) => {
                const label = formatSource(source);
                return (
                  <span
                    key={`${source.document}|${label}`}
                    title={source.document}
                    className="inline-flex items-center gap-1 bg-behave-page
                                   border border-[#C0CEDF] rounded px-2 py-0.5
                                   text-xs text-[#4A6080]"
                  >
                    <FiFileText size={10} />
                    {label}
                  </span>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default MessageBubble;
