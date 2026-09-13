import React from 'react';
import Modal from '../ui/Modal';
import Button from '../ui/Button';
import './FormDialog.css';

function EntityFormDialog({
  open,
  mode = 'create',
  title,
  onClose,
  onSubmit,
  submitting = false,
  children,
  submitLabel,
  error = null,
  onDismissError,
}) {
  const resolvedTitle =
    title ||
    (mode === 'edit'
      ? 'Update'
      : 'Create');

  const resolvedSubmitLabel =
    submitLabel ||
    (mode === 'edit'
      ? 'Update'
      : 'Create');

  return (
    <Modal
      open={open}
      title={resolvedTitle}
      onClose={onClose}
      closeOnOverlayClick={!submitting}
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
            {submitting ? 'Saving...' : resolvedSubmitLabel}
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

export default EntityFormDialog;