import React from 'react';
import Modal from '../ui/Modal';
import Button from '../ui/Button';

function TransactionFormDialog({
  open,
  title = 'Add Transaction',
  onClose,
  onSubmit,
  submitting = false,
  children,
  submitLabel = 'Add Transaction',
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