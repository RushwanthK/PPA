import React from 'react';
import Modal from '../ui/Modal';
import Button from '../ui/Button';

function EntityFormDialog({
  open,
  mode = 'create',
  title,
  onClose,
  onSubmit,
  submitting = false,
  children,
  submitLabel,
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