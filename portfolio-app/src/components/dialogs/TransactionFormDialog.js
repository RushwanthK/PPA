import React from 'react';
import Modal from '../ui/Modal';
import Button from '../ui/Button';
import './FormDialog.css';

function TransactionFormDialog({
  open,
  title = 'Add Transaction',
  onClose,
  onSubmit,
  submitting = false,
  children,
  submitLabel = 'Add Transaction',
  error = null,
  onDismissError,
}) {
  return (
    <Modal
      open={open}
      title={title}
      onClose={onClose}
      closeOnOverlayClick={!submitting}
      className="transaction-form-modal"
    >
      <form onSubmit={onSubmit}>
        <div className="form-body">
          {error && (
            <div className="form-dialog-error" role="alert">
              <span>{error}</span>

              {onDismissError && (
                <button
                  type="button"
                  className="form-dialog-error-dismiss"
                  onClick={onDismissError}
                  aria-label="Dismiss error"
                >
                  ×
                </button>
              )}
            </div>
          )}

          {children}
        </div>

        <div className="form-actions">
          <Button
            type="submit"
            variant="primary"
            disabled={submitting}
          >
            {submitting ? 'Processing...' : submitLabel}
          </Button>

          <Button
            type="button"
            variant="secondary"
            onClick={onClose}
            disabled={submitting}
          >
            Cancel
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export default TransactionFormDialog;