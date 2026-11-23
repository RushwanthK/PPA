import React, { useEffect, useId, useRef } from 'react';
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

  // Unique per modal instance, so two open modals never share a title id
  // (a shared id makes screen readers announce the wrong title).
  const titleId = useId();

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
        aria-labelledby={title ? titleId : undefined}
        tabIndex="-1"
      >
        {title && (
          <div className="modal-header">
            <h2 id={titleId}>{title}</h2>

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