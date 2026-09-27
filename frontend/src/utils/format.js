export function formatDate(isoDate, { withTime = false } = {}) {
  if (!isoDate || isoDate === "N/A") return "—";
  return new Date(isoDate).toLocaleString("fr-FR", {
    day:   "2-digit",
    month: "short",
    year:  "numeric",
    ...(withTime && { hour: "2-digit", minute: "2-digit" }),
  });
}

// « Titre — p. 12 » ou « Titre — Section » ; titre absent → nom du fichier.
export function formatSource(source) {
  const name     = source.title || source.document;
  const location = source.page ? `p. ${source.page}` : source.section;
  return location ? `${name} — ${location}` : name;
}

export function formatFileSize(sizeKb) {
  return sizeKb > 1024 ? `${(sizeKb / 1024).toFixed(1)} MB` : `${sizeKb} KB`;
}
