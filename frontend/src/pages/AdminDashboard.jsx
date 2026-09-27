import { useState, useEffect, useCallback, useRef } from "react";
import { fetchDocuments, deleteDocument } from "../services/adminApi";
import AdminSidebar    from "../components/admin/AdminSidebar";
import DocumentList    from "../components/admin/DocumentList";
import DocumentUploader from "../components/admin/DocumentUploader";
import Alert           from "../components/common/Alert";

function AdminDashboard() {
  const uploadRef = useRef(null);

  const [documents, setDocuments] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError]         = useState("");

  const totalChunks = documents.reduce((sum, d) => sum + d.chunks_count, 0);
  const totalSizeMB = (documents.reduce((sum, d) => sum + d.file_size_kb, 0) / 1024).toFixed(1);

  const loadDocuments = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await fetchDocuments();
      setDocuments(data.documents);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  function handleScrollToUpload() {
    uploadRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function handleUploadSuccess() {
    loadDocuments();
  }

  async function handleDelete(filename) {
    setError("");
    try {
      await deleteDocument(filename);
      setDocuments((prev) => prev.filter((d) => d.filename !== filename));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="min-h-screen bg-behave-page flex">

      <AdminSidebar activePage="documents" />

      <main className="flex-1 flex flex-col min-w-0">

        <header className="bg-white border-b-4 border-behave-cyan px-8 py-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-lg font-semibold text-gray-900">Base de connaissances</h1>
              <p className="text-xs text-gray-400 mt-1">Pipeline RAG — BeHave Assistant</p>
            </div>
            <button
              onClick={handleScrollToUpload}
              className="flex items-center gap-2 bg-behave-navy text-white text-sm font-medium
                         px-5 py-2.5 rounded-lg hover:bg-behave-navy-dark transition-colors"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="16 16 12 12 8 16"/>
                <line x1="12" y1="12" x2="12" y2="21"/>
                <path d="M20.39 18.39A5 5 0 0018 9h-1.26A8 8 0 103 16.3"/>
              </svg>
              Ajouter un document
            </button>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="bg-[#eef2ff] rounded-xl px-6 py-4 flex flex-col items-center justify-center">
              <div className="text-xs font-medium text-behave-navy/70 mb-1 uppercase tracking-wide">Documents</div>
              <div className="text-3xl font-bold text-behave-navy">{documents.length}</div>
            </div>
            <div className="bg-[#e8f7fd] rounded-xl px-6 py-4 flex flex-col items-center justify-center">
              <div className="text-xs font-medium text-[#0369a1]/70 mb-1 uppercase tracking-wide">Chunks indexés</div>
              <div className="text-3xl font-bold text-behave-cyan">{totalChunks}</div>
            </div>
            <div className="bg-[#f0fdf4] rounded-xl px-6 py-4 flex flex-col items-center justify-center">
              <div className="text-xs font-medium text-[#166534]/70 mb-1 uppercase tracking-wide">Taille totale</div>
              <div className="text-3xl font-bold text-[#16a34a]">{totalSizeMB} MB</div>
            </div>
          </div>
        </header>

        <div className="flex-1 p-6 flex flex-col gap-5 overflow-auto">

          {error && <Alert onDismiss={() => setError("")}>{error}</Alert>}

          <section>
            <h2 className="text-sm font-medium text-gray-700 mb-3">Documents indexés</h2>
            <DocumentList
              documents={documents}
              isLoading={isLoading}
              onDelete={handleDelete}
            />
          </section>

          <section>
            <h2 className="text-sm font-medium text-gray-700 mb-3">Ajouter un document</h2>
            <div ref={uploadRef}>
              <DocumentUploader onUploadSuccess={handleUploadSuccess} />
            </div>
          </section>

        </div>
      </main>
    </div>
  );
}

export default AdminDashboard;