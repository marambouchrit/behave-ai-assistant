import { FiRefreshCw } from "react-icons/fi";
import { BsCircleFill } from "react-icons/bs";
import Logo from "./common/Logo";

function Header({ onReset, isOnline }) {
  return (
    <div className="bg-behave-navy px-5 py-4 flex items-center justify-between flex-shrink-0">
      <div className="flex items-center gap-3">
        <Logo size={28} />
        <span className="text-white text-base font-semibold">BeHave Assistant</span>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <BsCircleFill className={`text-xs ${isOnline ? "text-green-400" : "text-red-400"}`} />
          <span className="text-white/75 text-xs">
            {isOnline ? "En ligne" : "Hors ligne"}
          </span>
        </div>

        <button
          onClick={onReset}
          title="Masque les échanges de cette conversation"
          className="flex items-center gap-1.5 text-white/70 hover:text-white text-xs px-2 py-1 rounded hover:bg-white/10 transition-colors"
        >
          <FiRefreshCw size={13} />
          Réinitialiser
        </button>
      </div>
    </div>
  );
}

export default Header;
