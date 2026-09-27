import { useState } from "react";
import DeleteConfirmModal from "./DeleteConfirmModal";
import { EmptyTableRow, SkeletonRows } from "../common/TableStates";
import { formatDate, formatFileSize } from "../../utils/format";

const DOCUMENT_ICON = (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-behave-navy">
    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
  </svg>
);

function getExtension(filename) {
  return filename.split(".").pop().toUpperCase();
}

function DocumentList({ documents, isLoading, onDelete }) {
  const [pendingDelete, setPendingDelete] = useState(null);

  function handleDeleteClick(filename) {
    setPendingDelete(filename);
  }

  function handleConfirm() {
    onDelete(pendingDelete);
    setPendingDelete(null);
  }

  function handleCancel() {
    setPendingDelete(null);
  }

  return (
    <>
      {pendingDelete && (
        <DeleteConfirmModal
          filename={pendingDelete}
          onConfirm={handleConfirm}
          onCancel={handleCancel}
        />
      )}

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full table-fixed">
          <colgroup>
            <col style={{ width: "45%" }} />
            <col style={{ width: "15%" }} />
            <col style={{ width: "18%" }} />
            <col style={{ width: "17%" }} />
            <col style={{ width: "5%" }} />
          </colgroup>

          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              {["Fichier", "Chunks", "Taille", "Date d'upload"].map((label) => (
                <th
                  key={label}
                  className="px-4 py-5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide"
                >
                  {label}
                </th>
              ))}
              <th className="px-4 py-5" />
            </tr>
          </thead>

          <tbody>
            {isLoading ? (
              <SkeletonRows widths={[200, 40, 60, 90, 28]} cellClassName="px-4 py-5" />
            ) : documents.length === 0 ? (
              <EmptyTableRow
                colSpan={5}
                icon={DOCUMENT_ICON}
                title="Aucun document indexé"
                subtitle="Uploadez un PDF, DOCX ou TXT pour commencer"
              />
            ) : (
              documents.map((doc, index) => {
                const ext        = getExtension(doc.filename);
                const isPdf      = ext === "PDF";
                const badgeColor = isPdf
                  ? "bg-red-50 text-red-700"
                  : "bg-[#eef2ff] text-behave-navy";

                return (
                  <tr
                    key={doc.filename}
                    className={`
                      border-b border-gray-100 hover:bg-gray-50 transition-colors
                      ${index === documents.length - 1 ? "border-b-0" : ""}
                      ${index % 2 === 1 ? "bg-[#fafbfc]" : "bg-white"}
                    `}
                  >
                    <td className="px-4 py-5">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded flex-shrink-0 ${badgeColor}`}>
                          {ext}
                        </span>
                        <span className="text-sm font-medium text-gray-800 truncate" title={doc.filename}>
                          {doc.filename}
                        </span>
                      </div>
                    </td>

                    <td className="px-4 py-5 text-sm font-semibold text-behave-navy">
                      {doc.chunks_count}
                    </td>

                    <td className="px-4 py-5 text-sm text-gray-600">
                      {formatFileSize(doc.file_size_kb)}
                    </td>

                    <td className="px-4 py-5 text-sm text-gray-600">
                      {formatDate(doc.uploaded_at)}
                    </td>

                    <td className="px-4 py-5">
                      <button
                        onClick={() => handleDeleteClick(doc.filename)}
                        className="w-8 h-8 flex items-center justify-center rounded-lg
                                   text-red-400 hover:text-red-600 hover:bg-red-50
                                   transition-colors"
                        aria-label={`Supprimer ${doc.filename}`}
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <polyline points="3 6 5 6 21 6"/>
                          <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/>
                          <path d="M10 11v6M14 11v6"/>
                          <path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2"/>
                        </svg>
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default DocumentList;