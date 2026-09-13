import React from 'react';

import './Deleteconfirmationdialog.css';

/**
 * Generic delete-confirmation dialog.
 *
 * This component is intentionally "dumb" — it doesn't know anything about
 * users, banks, savings, etc. Each page keeps its own state and handlers
 * (what counts as a warning, what the export call looks like) and just
 * passes them in as props. That's what makes it reusable across pages
 * while still rendering the exact same warning/backup UI everywhere.
 *
 * Minimal usage (no backup step):
 *   <DeleteConfirmationDialog
 *     isOpen={showDeleteModal}
 *     title="Delete Bank Account"
 *     headline="Please review before continuing."
 *     description="This bank account can currently be deleted."
 *     onConfirm={handleConfirmDelete}
 *     onClose={closeDeleteModal}
 *     isDeleting={isDeleting}
 *     confirmLabel="Delete Bank Account"
 *   />
 *
 * Full usage (with an optional categorized backup/export step) — see
 * pages/users.js for a worked example.
 */
const DeleteConfirmationDialog = ({
  isOpen,
  onClose,
  onConfirm,

  title = 'Confirm Deletion',
  headline,
  description,
  // Extra paragraphs shown under `description`. Each entry can be a plain
  // string or a JSX node (e.g. to bold a count), rendered in order.
  detailLines = [],

  isDeleting = false,
  confirmLabel = 'Delete',
  // Used instead of `confirmLabel` while a backup section is shown and no
  // backup has been downloaded yet. Falls back to `confirmLabel` when not
  // provided, so pages without a backup step don't need to set this.
  confirmWithoutBackupLabel,
  deletingLabel = 'Deleting...',
  cancelLabel = 'Cancel',

  // ---- Optional backup/export section ----
  showBackupSection = false,
  backupSectionTitle = 'Optional Backup',
  // Array of { key, label } describing the categories that can be
  // included in the backup. Pass a single entry (or omit entirely) for
  // pages where category selection doesn't make sense.
  categories = [],
  selectedCategories = {},
  onToggleCategory,
  onSelectAllCategories,
  onClearAllCategories,
  onDownloadExcel,
  onDownloadPdf,
  isDownloading = false,
  backupDownloaded = false,
  backupConfirmedMessage = 'A backup has been downloaded to your device.',
  categorySelectionWarning = 'Select at least one category to enable download.',
  // Error that belongs specifically to this delete dialog.
  // This prevents delete/backup errors from appearing behind the modal
  // in the page-level error area.
  dialogError,
  onDismissDialogError,

  // Allows pages such as Bank to use different wording for the
  // download buttons without changing the existing Users behavior.
  excelDownloadLabel = 'Download Excel',
  pdfDownloadLabel = 'Download PDF'
}) => {
  if (!isOpen) {
    return null;
  }

  const isBusy = isDeleting || isDownloading;

  const handleBackdropClick = () => {
    if (onClose) {
      onClose();
    }
  };

  const selectedCategoryKeys = categories
    .filter(category => !!selectedCategories[category.key])
    .map(category => category.key);

  // Only meaningful when categories are actually being offered — a backup
  // section without any categories (e.g. a single fixed export) is never
  // blocked by this.
  const categorySelectionEmpty = categories.length > 0 && selectedCategoryKeys.length === 0;

  const showCategoryShortcuts = categories.length > 1 && onSelectAllCategories && onClearAllCategories;

  let confirmText = confirmLabel;

  if (isDeleting) {
    confirmText = deletingLabel;
  } else if (showBackupSection && !backupDownloaded) {
    confirmText = confirmWithoutBackupLabel || confirmLabel;
  }

  return (
    <div className="dcd-backdrop" onClick={handleBackdropClick}>
      <div className="dcd-modal" onClick={(e) => e.stopPropagation()}>

        {dialogError && (
          <div className="dcd-dialog-error" role="alert">
            <span className="dcd-dialog-error-message">
              {dialogError}
            </span>

            {onDismissDialogError && (
              <button
                type="button"
                className="dcd-dialog-error-dismiss"
                onClick={onDismissDialogError}
                aria-label="Dismiss error"
              >
                &times;
              </button>
            )}
          </div>
        )}

        <h3>{title}</h3>

        {(headline || description || detailLines.length > 0) && (
          <div className="dcd-warning">
            {headline && <strong>{headline}</strong>}
            {description && <p>{description}</p>}
            {detailLines.map((line, index) => (
              <p key={index}>{line}</p>
            ))}
          </div>
        )}

        {showBackupSection && (
          <div className="dcd-backup-options">
            <h4>{backupSectionTitle}</h4>

            {categories.length > 0 && (
              <>
                <div className="dcd-category-header">
                  <span className="dcd-category-label">Include categories</span>
                  {showCategoryShortcuts && (
                    <div className="dcd-category-shortcuts">
                      <button
                        type="button"
                        className="dcd-category-shortcut-btn"
                        onClick={onSelectAllCategories}
                        disabled={isBusy}
                      >
                        Select all
                      </button>
                      <button
                        type="button"
                        className="dcd-category-shortcut-btn"
                        onClick={onClearAllCategories}
                        disabled={isBusy}
                      >
                        Clear
                      </button>
                    </div>
                  )}
                </div>

                <div className="dcd-category-list">
                  {categories.map(category => (
                    <label className="dcd-category-option" key={category.key}>
                      <input
                        type="checkbox"
                        checked={!!selectedCategories[category.key]}
                        onChange={() => onToggleCategory && onToggleCategory(category.key)}
                        disabled={isBusy}
                      />
                      <span>{category.label}</span>
                    </label>
                  ))}
                </div>
              </>
            )}

            <div className="dcd-backup-buttons">
              {onDownloadExcel && (
                <button
                  type="button"
                  className="dcd-backup-btn"
                  onClick={onDownloadExcel}
                  disabled={isBusy || categorySelectionEmpty}
                >
                  {isDownloading ? 'Preparing...' : excelDownloadLabel}
                </button>
              )}
              {onDownloadPdf && (
                <button
                  type="button"
                  className="dcd-backup-btn"
                  onClick={onDownloadPdf}
                  disabled={isBusy || categorySelectionEmpty}
                >
                  {isDownloading ? 'Preparing...' : pdfDownloadLabel}
                </button>
              )}
            </div>

            {categorySelectionEmpty && (
              <p className="dcd-category-warning">{categorySelectionWarning}</p>
            )}

            {backupDownloaded && (
              <p className="dcd-backup-confirmed">{backupConfirmedMessage}</p>
            )}
          </div>
        )}

        <div className="dcd-modal-actions">
          <button
            type="button"
            className="dcd-confirm-btn"
            onClick={onConfirm}
            disabled={isBusy}
          >
            {confirmText}
          </button>
          <button
            type="button"
            className="dcd-cancel-btn"
            onClick={onClose}
            disabled={isBusy}
          >
            {cancelLabel}
          </button>
        </div>
      </div>
    </div>
  );
};

export default DeleteConfirmationDialog;