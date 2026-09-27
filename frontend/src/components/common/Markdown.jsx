import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Rendu des réponses du LLM. Le HTML brut éventuel n'est pas interprété
// (comportement par défaut de react-markdown) : aucun risque d'injection.
const COMPONENTS = {
  p:          ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
  ul:         ({ children }) => <ul className="list-disc pl-5 mb-2 last:mb-0 space-y-0.5">{children}</ul>,
  ol:         ({ children }) => <ol className="list-decimal pl-5 mb-2 last:mb-0 space-y-0.5">{children}</ol>,
  strong:     ({ children }) => <strong className="font-semibold">{children}</strong>,
  h1:         ({ children }) => <p className="font-semibold mb-1">{children}</p>,
  h2:         ({ children }) => <p className="font-semibold mb-1">{children}</p>,
  h3:         ({ children }) => <p className="font-semibold mb-1">{children}</p>,
  a:          ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-behave-navy underline">
      {children}
    </a>
  ),
  code:       ({ children }) => <code className="bg-gray-100 rounded px-1 py-0.5 text-xs">{children}</code>,
  pre:        ({ children }) => <pre className="bg-gray-100 rounded p-2 mb-2 overflow-x-auto text-xs">{children}</pre>,
  blockquote: ({ children }) => <blockquote className="border-l-2 border-gray-300 pl-3 text-gray-600">{children}</blockquote>,
  table:      ({ children }) => (
    <div className="overflow-x-auto mb-2">
      <table className="text-xs border-collapse">{children}</table>
    </div>
  ),
  th:         ({ children }) => <th className="border border-gray-200 px-2 py-1 bg-gray-50 text-left">{children}</th>,
  td:         ({ children }) => <td className="border border-gray-200 px-2 py-1">{children}</td>,
};

function Markdown({ children }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
      {children}
    </ReactMarkdown>
  );
}

export default Markdown;
