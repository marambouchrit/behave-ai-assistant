function DeleteConfirmModal({ filename, onConfirm, onCancel }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.4)" }}
      onClick={onCancel}
    >
      <div
        className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="w-12 h-12 bg-red-50 rounded-xl flex items-center justify-center mx-auto mb-4">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/>
            <path d="M10 11v6M14 11v6"/>
            <path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2"/>
          </svg>
        </div>

        <h3 className="text-base font-semibold text-gray-900 text-center mb-1">
          Supprimer ce document ?
        </h3>

        <p className="text-sm text-gray-500 text-center mb-1">
          Vous êtes sur le point de supprimer
        </p>
        <p className="text-sm font-medium text-gray-800 text-center bg-gray-50 rounded-lg px-3 py-2 mb-4 truncate">
          {filename}
        </p>

        <div className="flex items-start gap-2 bg-red-50 border border-red-100 rounded-lg px-3 py-2.5 mb-5">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="flex-shrink-0 mt-0.5">
            <circle cx="8" cy="8" r="7" stroke="#ef4444" strokeWidth="1.5"/>
            <path d="M8 5v4M8 11v.5" stroke="#ef4444" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <p className="text-xs text-red-600">
            Le document sera retiré de la base de connaissances et le chatbot ne pourra plus y accéder. Cette action est irréversible.
          </p>
        </div>

        <div className="flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 px-4 py-2.5 text-sm font-medium text-gray-700
                       bg-white border border-gray-200 rounded-lg
                       hover:bg-gray-50 transition-colors"
          >
            Annuler
          </button>
          <button
            onClick={onConfirm}
            className="flex-1 px-4 py-2.5 text-sm font-medium text-white
                       bg-red-500 rounded-lg hover:bg-red-600 transition-colors"
          >
            Supprimer
          </button>
        </div>
      </div>
    </div>
  );
}

export default DeleteConfirmModal;