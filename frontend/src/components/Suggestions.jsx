// Exemples de questions couverts par la documentation indexée.
const SUGGESTIONS = [
  "Comment créer un client dans BeHave Master Data ?",
  "Quels modèles de prévision propose BeHave Predictive ?",
  "Comment analyser les violations SoD dans le rapport Power BI ?",
  "Comment extraire les tables SAP pour BeHave ?",
];

function Suggestions({ onSelect, isLoading }) {
  return (
    <div className="px-4 pt-3 pb-2 flex-shrink-0">
      <p className="text-xs text-[#6B7A99] font-medium uppercase tracking-wide mb-2">
        Suggestions
      </p>
      <div className="flex gap-2 flex-wrap">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => !isLoading && onSelect(s)}
            disabled={isLoading}
            className="bg-white border border-[#B8C8E0] rounded-full px-3 py-1.5 text-xs text-behave-navy hover:bg-behave-soft hover:border-behave-cyan transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

export default Suggestions;