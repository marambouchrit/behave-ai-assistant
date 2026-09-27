import { useState, useEffect, useCallback } from "react";
import AdminSidebar from "../components/admin/AdminSidebar";
import Alert from "../components/common/Alert";
import Markdown from "../components/common/Markdown";
import { EmptyTableRow, SkeletonRows } from "../components/common/TableStates";
import { fetchHistory } from "../services/adminApi";
import { formatDate, formatSource } from "../utils/format";

const PAGE_SIZE = 20;

const CHAT_ICON = (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-behave-navy">
    <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
  </svg>
);

function AdminHistory() {
  const [conversations, setConversations] = useState([]);
  const [total, setTotal]                 = useState(0);
  const [skip, setSkip]                   = useState(0);
  const [isLoading, setIsLoading]         = useState(true);
  const [error, setError]                 = useState("");
  const [expanded, setExpanded]           = useState(null);

  const totalPages  = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(skip / PAGE_SIZE) + 1;

  const loadHistory = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const data = await fetchHistory(skip, PAGE_SIZE);
      setConversations(data.conversations);
      setTotal(data.total);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, [skip]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  function handlePrev() {
    setSkip((prev) => Math.max(0, prev - PAGE_SIZE));
  }

  function handleNext() {
    setSkip((prev) => prev + PAGE_SIZE);
  }

  function toggleExpand(id) {
    setExpanded((prev) => (prev === id ? null : id));
  }

  return (
    <div className="min-h-screen bg-behave-page flex">

      <AdminSidebar activePage="history" />

      <main className="flex-1 flex flex-col min-w-0">

        <header className="bg-white border-b-4 border-behave-cyan px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-lg font-semibold text-gray-900">Historique des conversations</h1>
              <p className="text-xs text-gray-400 mt-1">Toutes les conversations — users et admin</p>
            </div>
            <div className="bg-[#eef2ff] rounded-xl px-6 py-3 text-center">
              <div className="text-2xl font-bold text-behave-navy">{total}</div>
              <div className="text-xs text-behave-navy/70 uppercase tracking-wide">échanges</div>
            </div>
          </div>
        </header>

        <div className="flex-1 p-6 flex flex-col gap-4 overflow-auto">

          {error && <Alert>{error}</Alert>}

          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full table-fixed">
              <colgroup>
                <col style={{ width: "10%" }} />
                <col style={{ width: "25%" }} />
                <col style={{ width: "30%" }} />
                <col style={{ width: "15%" }} />
                <col style={{ width: "20%" }} />
              </colgroup>

              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  {["User", "Question", "Réponse", "Module", "Date"].map((label) => (
                    <th
                      key={label}
                      className="px-4 py-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide"
                    >
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody>
                {isLoading ? (
                  <SkeletonRows widths={[60, 200, 300, 200, 100]} rows={8} />
                ) : conversations.length === 0 ? (
                  <EmptyTableRow
                    colSpan={5}
                    icon={CHAT_ICON}
                    title="Aucune conversation enregistrée"
                    subtitle="Les conversations apparaîtront ici après les premières questions"
                  />
                ) : (
                  conversations.map((conv, index) => {
                    const isExpanded = expanded === conv.id;
                    return (
                      <tr
                        key={conv.id}
                        onClick={() => toggleExpand(conv.id)}
                        className={`border-b border-gray-100 cursor-pointer transition-colors
                          ${index % 2 === 1 ? "bg-[#fafbfc]" : "bg-white"}
                          ${isExpanded ? "bg-[#eef2ff]" : "hover:bg-gray-50"}`}
                      >
                        <td className="px-4 py-4">
                          <div className="flex items-center gap-2">
                            <div className="w-6 h-6 rounded-full bg-behave-cyan flex items-center justify-center text-white text-xs font-semibold flex-shrink-0">
                              {conv.username.charAt(0).toUpperCase()}
                            </div>
                            <span className="text-xs font-medium text-gray-700 truncate">
                              {conv.username}
                            </span>
                          </div>
                        </td>

                        <td className="px-4 py-4">
                          <p className={`text-sm text-gray-800 ${isExpanded ? "" : "truncate"}`}>
                            {conv.question}
                          </p>
                        </td>

                        <td className="px-4 py-4">
                          <div className={`text-sm text-gray-600 ${isExpanded ? "" : "line-clamp-2"}`}>
                            <Markdown>{conv.answer}</Markdown>
                          </div>
                          {isExpanded && conv.sources.length > 0 && (
                            <p className="mt-2 text-xs text-gray-400">
                              Sources : {conv.sources.map(formatSource).join(" · ")}
                            </p>
                          )}
                        </td>

                        <td className="px-4 py-4">
                          {conv.module && (
                            <span className="text-xs bg-[#eef2ff] text-behave-navy px-2 py-1 rounded-full font-medium">
                              {conv.module}
                            </span>
                          )}
                        </td>

                        <td className="px-4 py-4 text-xs text-gray-400">
                          {formatDate(conv.created_at, { withTime: true })}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between px-1">
              <span className="text-xs text-gray-500">
                Page {currentPage} sur {totalPages} — {total} échanges au total
              </span>
              <div className="flex gap-2">
                <button
                  onClick={handlePrev}
                  disabled={skip === 0}
                  className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-white border border-gray-200
                             rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  ← Précédent
                </button>
                <button
                  onClick={handleNext}
                  disabled={skip + PAGE_SIZE >= total}
                  className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-white border border-gray-200
                             rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Suivant →
                </button>
              </div>
            </div>
          )}

        </div>
      </main>
    </div>
  );
}

export default AdminHistory;