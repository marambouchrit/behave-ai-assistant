import { useState, useRef, useEffect, useCallback } from 'react';

const RECOGNITION_LANG = 'fr-FR';

const ERROR_MESSAGES = {
  'not-allowed':    'Accès au microphone refusé. Vérifiez les permissions du navigateur.',
  'no-speech':      'Aucune parole détectée. Réessayez.',
  'audio-capture':  'Microphone introuvable ou inaccessible.',
  'network':        'Erreur réseau lors de la reconnaissance vocale.',
  'aborted':        null, 
};

const DEFAULT_ERROR = 'Erreur de reconnaissance vocale. Réessayez.';

const _getSpeechRecognitionConstructor = () =>
  window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;

const _isBrowserSupported = () => _getSpeechRecognitionConstructor() !== null;

const useVoiceRecognition = (onTranscript) => {
  const [isListening, setIsListening]   = useState(false);
  const [transcript,  setTranscript]    = useState('');
  const [error,       setError]         = useState(null);

  
  const recognitionRef = useRef(null);
  const isSupported    = _isBrowserSupported();

  useEffect(() => {
    if (!isSupported) return;

    const SpeechRecognition = _getSpeechRecognitionConstructor();
    const recognition = new SpeechRecognition();

    recognition.lang            = RECOGNITION_LANG;
    recognition.continuous      = false;  
    recognition.interimResults  = true;  

  

    recognition.onstart = () => {
      setIsListening(true);
      setTranscript('');
      setError(null);
    };

    recognition.onresult = (event) => {
      let interimText  = '';
      let finalText    = '';

      for (const result of event.results) {
        if (result.isFinal) {
          finalText += result[0].transcript;
        } else {
          interimText += result[0].transcript;
        }
      }

      
      setTranscript(interimText || finalText);

      if (finalText) {
        onTranscript(finalText.trim());
      }
    };

    recognition.onerror = (event) => {
      const message = ERROR_MESSAGES[event.error] ?? DEFAULT_ERROR;

     
      if (message !== null) {
        setError(message);
      }

      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;

    
    return () => {
      recognition.abort();
      recognitionRef.current = null;
    };
  }, [isSupported, onTranscript]);

  const startListening = useCallback(() => {
    if (!isSupported || !recognitionRef.current || isListening) return;

    setError(null);
    setTranscript('');

    try {
      recognitionRef.current.start();
    } catch {
      setError(DEFAULT_ERROR);
    }
  }, [isSupported, isListening]);

  const stopListening = useCallback(() => {
    if (!recognitionRef.current || !isListening) return;
    
    recognitionRef.current.stop();
  }, [isListening]);

  const clearError = useCallback(() => setError(null), []);

  return {
    isListening,
    isSupported,
    transcript,
    error,
    startListening,
    stopListening,
    clearError,
  };
};

export default useVoiceRecognition;