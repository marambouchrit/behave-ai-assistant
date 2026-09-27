const VARIANTS = {
  error: {
    box:  "bg-red-50 border-red-200",
    text: "text-red-600",
    icon: (
      <>
        <circle cx="8" cy="8" r="7" stroke="#ef4444" strokeWidth="1.5" />
        <path d="M8 5v4M8 11v.5" stroke="#ef4444" strokeWidth="1.5" strokeLinecap="round" />
      </>
    ),
  },
  success: {
    box:  "bg-green-50 border-green-200",
    text: "text-green-700",
    icon: (
      <>
        <circle cx="8" cy="8" r="7" stroke="#16a34a" strokeWidth="1.5" />
        <polyline points="5 8 7 10 11 6" stroke="#16a34a" strokeWidth="1.5" strokeLinecap="round" />
      </>
    ),
  },
};

function Alert({ variant = "error", children, onDismiss }) {
  const style = VARIANTS[variant];
  return (
    <div
      role={variant === "error" ? "alert" : "status"}
      className={`flex items-center gap-2 border rounded-lg px-3 py-2.5 ${style.box}`}
    >
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="flex-shrink-0">
        {style.icon}
      </svg>
      <p className={`text-sm flex-1 ${style.text}`}>{children}</p>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className={`text-xs font-bold hover:opacity-70 ${style.text}`}
          aria-label="Fermer"
        >
          ✕
        </button>
      )}
    </div>
  );
}

export default Alert;
