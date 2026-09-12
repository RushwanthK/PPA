import React, { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import './Modal.css';

function Modal({
  open,
  title,
  children,
  onClose,
  closeOnOverlayClick = true,
  closeOnEscape = true,
  className = '',
  overlayClassName = '',
  footer = null,
}) {
  const contentRef = useRef(null);

  useEffect(() => {
    if (!open || !closeOnEscape) {
      return undefined;
    }

    const handleKeyDown = event => {
      if (event.key === 'Escape') {
        onClose?.();
      }
    };

    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open, closeOnEscape, onClose]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const previousActiveElement = document.activeElement;

    contentRef.current?.focus();

    return () => {
      if (
        previousActiveElement &&
        typeof previousActiveElement.focus === 'function'
      ) {
        previousActiveElement.focus();
      }
    };
  }, [open]);

  if (!open) {
    return null;
  }

  const handleOverlayClick = event => {
    if (
      closeOnOverlayClick &&
      event.target === event.currentTarget
    ) {
      onClose?.();
    }
  };

  return createPortal(
    <div
      className={`modal ${overlayClassName}`.trim()}
      role="presentation"
      onMouseDown={handleOverlayClick}
    >
      <div
        ref={contentRef}
        className={`modal-content ${className}`.trim()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? 'modal-title' : undefined}
        tabIndex="-1"
      >
        {title && (
          <div className="modal-header">
            <h2 id="modal-title">{title}</h2>

            <button
              type="button"
              className="modal-close-button"
              onClick={onClose}
              aria-label="Close dialog"
            >
              ×
            </button>
          </div>
        )}

        <div className="modal-body">
          {children}
        </div>

        {footer && (
          <div className="modal-footer">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}

export default Modal;