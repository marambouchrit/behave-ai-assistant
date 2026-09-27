import { useState, useRef, useCallback } from 'react';
import { FiSend } from 'react-icons/fi';
import VoiceRecorder from './VoiceRecorder';

// Doit rester aligné sur ChatRequest.question (max_length) côté backend.
const MAX_INPUT_LENGTH = 2000;

/**
 * InputBar
 *
 * Barre de saisie du chatbot.
 * Intègre VoiceRecorder (dictée vocale).
 *
 * @param {function} onSend      Appelé avec la question (string) à envoyer.
 * @param {boolean}  isLoading   Désactive les contrôles pendant la réponse de l'IA.
 */
const InputBar = ({ onSend, isLoading = false }) => {
  const [inputValue, setInputValue] = useState('');

  const textareaRef = useRef(null);

  const handleTranscript = useCallback((transcribedText) => {
    setInputValue((prev) => {
      const separator = prev.trim() ? ' ' : '';
      return prev + separator + transcribedText;
    });
    textareaRef.current?.focus();
  }, []);

  const handleSend = useCallback(() => {
    const trimmed = inputValue.trim();
    if (!trimmed || isLoading) return;

    onSend(trimmed);
    setInputValue('');
  }, [inputValue, isLoading, onSend]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  const handleChange = useCallback((e) => {
    const value = e.target.value;
    if (value.length > MAX_INPUT_LENGTH) return;

    setInputValue(value);

    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
    }
  }, []);

  const canSend = inputValue.trim().length > 0 && !isLoading;

  return (
    <div className="border-t border-gray-200 bg-white px-4 py-3">
      <div
        className={[
          'flex items-end gap-2 rounded-xl border transition-colors duration-150',
          'bg-gray-50 px-3 py-2 mt-1',
          isLoading
            ? 'border-gray-200'
            : 'border-gray-300 focus-within:border-behave-cyan',
        ].join(' ')}
      >
        <div className="flex-shrink-0 mb-0.5">
          <VoiceRecorder
            onTranscript={handleTranscript}
            disabled={isLoading}
          />
        </div>

        <textarea
          ref={textareaRef}
          value={inputValue}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          placeholder="Posez une question sur BeHave…"
          rows={1}
          maxLength={MAX_INPUT_LENGTH}
          aria-label="Message à envoyer"
          className={[
            'flex-1 resize-none bg-transparent text-sm text-gray-800',
            'placeholder-gray-400 outline-none leading-relaxed',
            'min-h-[36px] max-h-[160px]',
            isLoading ? 'cursor-not-allowed opacity-60' : '',
          ].join(' ')}
          style={{ overflowY: 'auto' }}
        />

        <button
          type="button"
          onClick={handleSend}
          disabled={!canSend}
          aria-label="Envoyer le message"
          title={canSend ? 'Envoyer' : 'Écrivez ou dictez une question'}
          className={[
            'flex-shrink-0 mb-0.5 flex items-center justify-center',
            'w-9 h-9 rounded-full transition-all duration-200',
            canSend
              ? 'bg-behave-navy hover:bg-behave-cyan cursor-pointer'
              : 'bg-gray-200 cursor-not-allowed',
          ].join(' ')}
        >
          <FiSend
            size={16}
            color={canSend ? '#FFFFFF' : '#9CA3AF'}
            aria-hidden="true"
          />
        </button>
      </div>

      {inputValue.length > MAX_INPUT_LENGTH * 0.8 && (
        <p
          className={[
            'text-right text-xs mt-1 pr-1',
            inputValue.length >= MAX_INPUT_LENGTH
              ? 'text-red-500'
              : 'text-gray-400',
          ].join(' ')}
          aria-live="polite"
        >
          {inputValue.length} / {MAX_INPUT_LENGTH}
        </p>
      )}
    </div>
  );
};

export default InputBar;
