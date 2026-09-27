import { useCallback } from 'react';
import { FiMic, FiMicOff } from 'react-icons/fi';
import useVoiceRecognition from '../hooks/useVoiceRecognition';

const BEHAVE_CYAN = '#29B6E8';

const _PulseRing = () => (
  <span
    className="absolute inset-0 rounded-full animate-ping"
    style={{ backgroundColor: BEHAVE_CYAN, opacity: 0.3 }}
    aria-hidden="true"
  />
);

const _ErrorTooltip = ({ message, onDismiss }) => (
  <div
    role="alert"
    className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2
               bg-red-600 text-white text-xs rounded-lg px-3 py-2
               whitespace-nowrap shadow-md z-10"
  >
    {message}
    <button
      onClick={onDismiss}
      className="ml-2 font-bold hover:opacity-70 transition-opacity"
      aria-label="Fermer l'erreur"
    >
      ✕
    </button>
    <span
      className="absolute top-full left-1/2 -translate-x-1/2
                 border-4 border-transparent border-t-red-600"
      aria-hidden="true"
    />
  </div>
);

/**
 * VoiceRecorder
 *
 * Bouton microphone consommant useVoiceRecognition.
 * Affiche 4 états visuels : idle / listening / error / unsupported.
 *
 * @param {function} onTranscript   Reçoit le texte final transcrit.
 * @param {boolean}  disabled       Désactiver pendant l'envoi d'un message.
 */
const VoiceRecorder = ({ onTranscript, disabled = false }) => {
  const {
    isListening,
    isSupported,
    error,
    startListening,
    stopListening,
    clearError,
  } = useVoiceRecognition(onTranscript);

  const isDisabled = disabled || !isSupported;

  const _getAriaLabel = () => {
    if (!isSupported)  return 'Reconnaissance vocale non supportée par ce navigateur';
    if (error)         return `Erreur microphone : ${error}`;
    if (isListening)   return 'Arrêter l\'enregistrement';
    return 'Démarrer la reconnaissance vocale';
  };

  const _getTitle = () => {
    if (!isSupported) return 'Votre navigateur ne supporte pas la reconnaissance vocale';
    if (error)        return error;
    if (isListening)  return 'Cliquer pour arrêter';
    return 'Parler pour dicter un message';
  };

  

  const _getIconColor = () => {
    if (!isSupported || isDisabled) return '#9CA3AF';
    if (error)                      return '#EF4444'; 
    if (isListening)                return BEHAVE_CYAN;
    return '#6B7280'; 
  };

  const _renderIcon = () => {
    const color = _getIconColor();
    const size  = 18;

    if (!isSupported || error) {
      return <FiMicOff size={size} color={color} aria-hidden="true" />;
    }
    return <FiMic size={size} color={color} aria-hidden="true" />;
  };

  const handleClick = useCallback(() => {
    if (isDisabled) return;

    if (error) {
      clearError();
      return;
    }

    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  }, [isDisabled, error, isListening, clearError, stopListening, startListening]);

  return (
    <div className="relative flex items-center justify-center">

      {error && (
        <_ErrorTooltip message={error} onDismiss={clearError} />
      )}

      <button
        type="button"
        onClick={handleClick}
        disabled={isDisabled}
        aria-label={_getAriaLabel()}
        title={_getTitle()}
        className={[
          'relative flex items-center justify-center',
          'w-9 h-9 rounded-full transition-all duration-200',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2',
          isListening
            ? 'bg-blue-50'                   
            : 'hover:bg-gray-100',           
          isDisabled
            ? 'cursor-not-allowed opacity-40'
            : 'cursor-pointer',
        ].join(' ')}
        style={
          isListening
            ? { focusVisibleRingColor: BEHAVE_CYAN }
            : {}
        }
      >
       
        {isListening && <_PulseRing />}

        
        {isListening && (
          <span
            className="absolute inset-0 rounded-full border-2"
            style={{ borderColor: BEHAVE_CYAN }}
            aria-hidden="true"
          />
        )}

        {_renderIcon()}
      </button>
    </div>
  );
};

export default VoiceRecorder;