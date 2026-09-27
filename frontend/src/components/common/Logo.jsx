// Logo BeHave. La couleur suit `currentColor` : la fixer via une classe text-*.
function Logo({ size = 22, className = "text-behave-cyan", fillOpacity = 0.4 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none" className={className} aria-hidden="true">
      <path
        d="M8 32 L20 8 L32 32"
        stroke="currentColor"
        strokeWidth="4.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M8 32 L20 21 L32 32" fill="currentColor" fillOpacity={fillOpacity} />
    </svg>
  );
}

export default Logo;
