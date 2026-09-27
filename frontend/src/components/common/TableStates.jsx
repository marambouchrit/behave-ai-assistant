// Lignes de chargement (squelettes) : une largeur par colonne.
export function SkeletonRows({ widths, rows = 5, cellClassName = "px-4 py-4" }) {
  return Array.from({ length: rows }).map((_, row) => (
    <tr key={row} className="border-b border-gray-100">
      {widths.map((width, col) => (
        <td key={col} className={cellClassName}>
          <div className="h-3 bg-gray-100 rounded animate-pulse" style={{ width }} />
        </td>
      ))}
    </tr>
  ));
}

export function EmptyTableRow({ colSpan, icon, title, subtitle }) {
  return (
    <tr>
      <td colSpan={colSpan}>
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <div className="w-12 h-12 bg-behave-soft rounded-xl flex items-center justify-center mb-3">
            {icon}
          </div>
          <p className="text-sm font-medium text-gray-700">{title}</p>
          <p className="text-xs text-gray-400 mt-1">{subtitle}</p>
        </div>
      </td>
    </tr>
  );
}
