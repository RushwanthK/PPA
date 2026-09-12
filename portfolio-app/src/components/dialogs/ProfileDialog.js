import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../AuthContext';
import {
  updateUser,
  deleteUser,
  canDeleteUser,
  exportUserTransactionsExcel,
  exportUserTransactionsPdf,
} from '../../services/api';
import Button from '../ui/Button';
import Modal from '../ui/Modal';
import DeleteConfirmationDialog from '../Deleteconfirmationdialog';

import './ProfileDialog.css';

const EMPTY_FORM = {
  id: '',
  name: '',
  dob: '',
  place: '',
  password: '',
  confirmPassword: '',
};

const EXPORT_CATEGORY_OPTIONS = [
  { key: 'banks', label: 'Banks' },
  { key: 'savings', label: 'Savings' },
  { key: 'assets', label: 'Assets' },
  { key: 'credit_cards', label: 'Credit Cards' },
];

const getAllCategories = () =>
  EXPORT_CATEGORY_OPTIONS.reduce((selection, category) => {
    selection[category.key] = true;
    return selection;
  }, {});

const formatDob = dob => {
  if (!dob) {
    return '—';
  }

  const date = new Date(`${dob.slice(0, 10)}T00:00:00`);

  if (Number.isNaN(date.getTime())) {
    return dob;
  }

  return date.toLocaleDateString();
};

function ProfileDialog({ open, onClose }) {
  const { user, setUser, logout } = useAuth();
  const navigate = useNavigate();

  const [isEditing, setIsEditing] = useState(false);
  const [updatedUser, setUpdatedUser] = useState(EMPTY_FORM);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [profileError, setProfileError] = useState('');

  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteInfo, setDeleteInfo] = useState(null);
  const [deletingUserId, setDeletingUserId] = useState(null);
  const [deleteError, setDeleteError] = useState('');
  const [isDownloadingBackup, setIsDownloadingBackup] = useState(false);
  const [backupDownloaded, setBackupDownloaded] = useState(false);
  const [selectedCategories, setSelectedCategories] = useState(getAllCategories);


  useEffect(() => {
    if (!open) {
      return;
    }

    setProfileError('');
    setDeleteError('');
    setShowDeleteModal(false);
    setDeleteInfo(null);
    setDeletingUserId(null);
    setBackupDownloaded(false);
    setSelectedCategories(getAllCategories());
  }, [open, user?.id]);

  useEffect(() => {
    if (!open || !isEditing || !user) {
      return;
    }

    setUpdatedUser({
      id: user.id,
      name: user.name || '',
      dob: (user.dob || '').slice(0, 10),
      place: user.place || '',
      password: '',
      confirmPassword: '',
    });
  }, [open, isEditing, user]);

  const closeDeleteModal = useCallback(() => {
    if (isDeleting || isDownloadingBackup) {
      return;
    }

    setShowDeleteModal(false);
    setDeleteInfo(null);
    setDeletingUserId(null);
    setDeleteError('');
    setBackupDownloaded(false);
    setSelectedCategories(getAllCategories());
  }, [isDeleting, isDownloadingBackup]);

  const closeProfile = useCallback(() => {
    if (isSaving || isDeleting || isDownloadingBackup) {
      return;
    }

    if (showDeleteModal) {
      closeDeleteModal();
      return;
    }

    setIsEditing(false);
    setProfileError('');
    onClose?.();
  }, [
    closeDeleteModal,
    isDeleting,
    isDownloadingBackup,
    isSaving,
    onClose,
    showDeleteModal,
  ]);

  const handleFieldChange = useCallback(event => {
    const { name, value } = event.target;
    setUpdatedUser(prev => ({ ...prev, [name]: value }));
    setProfileError('');
  }, []);

  const handleEditClick = useCallback(() => {
    if (!user) {
      return;
    }

    setUpdatedUser({
      id: user.id,
      name: user.name || '',
      dob: (user.dob || '').slice(0, 10),
      place: user.place || '',
      password: '',
      confirmPassword: '',
    });
    setProfileError('');
    setIsEditing(true);
  }, [user]);

  const handleCancelEdit = useCallback(() => {
    if (isSaving) {
      return;
    }

    setIsEditing(false);
    setProfileError('');
  }, [isSaving]);

  const handleLogout = useCallback(() => {
    if (isSaving || isDeleting || isDownloadingBackup) {
      return;
    }

    logout();
    onClose?.();
    navigate('/', { replace: true });
  }, [isDeleting, isDownloadingBackup, isSaving, logout, navigate, onClose]);

  const handleUpdateUser = useCallback(
    async event => {
      event.preventDefault();

      if (!user || isSaving) {
        return;
      }

      if (
        updatedUser.password &&
        updatedUser.password !== updatedUser.confirmPassword
      ) {
        setProfileError('Passwords do not match.');
        return;
      }

      try {
        setIsSaving(true);
        setProfileError('');

        const updatePayload = {
          name: updatedUser.name,
          dob: updatedUser.dob,
          place: updatedUser.place,
        };

        if (updatedUser.password) {
          updatePayload.password = updatedUser.password;
        }

        const response = await updateUser(user.id, updatePayload);

        setUser(response.data);
        setIsEditing(false);
      } catch (error) {
        console.error('Failed to update user:', error);

        setProfileError(
          error.response?.data?.error ||
            error.response?.data?.message ||
            'Failed to update your profile. Please try again.'
        );
      } finally {
        setIsSaving(false);
      }
    },
    [isSaving, setUser, updatedUser, user]
  );

  const handleDeleteClick = useCallback(async () => {
    if (!user || isDeleting) {
      return;
    }

    try {
      setIsDeleting(true);
      setProfileError('');
      setDeleteError('');

      const response = await canDeleteUser(user.id);
      const deletionData = response.data;

      if (!deletionData.can_delete) {
        const details = deletionData.details || {};
        const reasons = [];

        if (details.has_bank_balances) reasons.push('bank accounts');
        if (details.has_asset_balances) reasons.push('assets');
        if (details.has_saving_balances) reasons.push('savings');
        if (details.has_credit_balances) reasons.push('credit cards');

        setProfileError(
          deletionData.message ||
            `Cannot delete your account. Please clear balances from ${reasons.join(
              ', '
            )} and try again.`
        );
        return;
      }

      setDeleteInfo(deletionData);
      setDeletingUserId(user.id);
      setBackupDownloaded(false);
      setSelectedCategories(getAllCategories());
      setShowDeleteModal(true);
    } catch (error) {
      console.error('Failed to check user deletion:', error);

      setProfileError(
        error.response?.data?.error ||
          error.response?.data?.message ||
          'Unable to check whether your account can be deleted.'
      );
    } finally {
      setIsDeleting(false);
    }
  }, [isDeleting, user]);

  const getSelectedCategoryKeys = useCallback(
    () =>
      EXPORT_CATEGORY_OPTIONS.filter(
        category => selectedCategories[category.key]
      ).map(category => category.key),
    [selectedCategories]
  );

  const toggleCategory = useCallback(key => {
    setSelectedCategories(prev => ({
      ...prev,
      [key]: !prev[key],
    }));
    setBackupDownloaded(false);
  }, []);

  const selectAllCategories = useCallback(() => {
    setSelectedCategories(getAllCategories());
    setBackupDownloaded(false);
  }, []);

  const clearAllCategories = useCallback(() => {
    setSelectedCategories(
      EXPORT_CATEGORY_OPTIONS.reduce((selection, category) => {
        selection[category.key] = false;
        return selection;
      }, {})
    );
    setBackupDownloaded(false);
  }, []);

  const downloadBlob = useCallback((blob, filename) => {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');

    link.href = url;
    link.download = filename;

    document.body.appendChild(link);
    link.click();
    link.remove();

    window.URL.revokeObjectURL(url);
  }, []);

  const handleDownloadExcel = useCallback(async () => {
    if (!deleteInfo || !deletingUserId) {
      return;
    }

    const categories = getSelectedCategoryKeys();

    if (categories.length === 0) {
      setDeleteError('Select at least one category to include in the backup.');
      return;
    }

    try {
      setIsDownloadingBackup(true);
      setDeleteError('');

      const response = await exportUserTransactionsExcel(
        deletingUserId,
        categories
      );

      const filename = `ppa_transaction_backup_${new Date()
        .toISOString()
        .slice(0, 10)}.xlsx`;

      downloadBlob(response.data, filename);
      setBackupDownloaded(true);
    } catch (error) {
      console.error('Failed to download Excel backup:', error);
      setDeleteError(
        'Unable to download the Excel backup. Your transaction data has not been deleted.'
      );
    } finally {
      setIsDownloadingBackup(false);
    }
  }, [deleteInfo, deletingUserId, downloadBlob, getSelectedCategoryKeys]);

  const handleDownloadPdf = useCallback(async () => {
    if (!deleteInfo || !deletingUserId) {
      return;
    }

    const categories = getSelectedCategoryKeys();

    if (categories.length === 0) {
      setDeleteError('Select at least one category to include in the backup.');
      return;
    }

    try {
      setIsDownloadingBackup(true);
      setDeleteError('');

      const response = await exportUserTransactionsPdf(
        deletingUserId,
        categories
      );

      const filename = `ppa_transaction_backup_${new Date()
        .toISOString()
        .slice(0, 10)}.pdf`;

      downloadBlob(response.data, filename);
      setBackupDownloaded(true);
    } catch (error) {
      console.error('Failed to download PDF backup:', error);
      setDeleteError(
        'Unable to download the PDF backup. Your transaction data has not been deleted.'
      );
    } finally {
      setIsDownloadingBackup(false);
    }
  }, [deleteInfo, deletingUserId, downloadBlob, getSelectedCategoryKeys]);

  const handleConfirmDelete = useCallback(async () => {
    if (!deleteInfo || !deletingUserId || isDeleting) {
      return;
    }

    try {
      setIsDeleting(true);
      setDeleteError('');

      const response = await deleteUser(deletingUserId);

      setShowDeleteModal(false);
      setDeleteInfo(null);
      setDeletingUserId(null);
      setBackupDownloaded(false);
      setSelectedCategories(getAllCategories());

      logout();
      onClose?.();
      navigate('/', { replace: true });

      console.info(response.data?.message || 'User deleted successfully.');
    } catch (error) {
      console.error('Failed to delete user:', error);

      setDeleteError(
        error.response?.data?.error ||
          error.response?.data?.message ||
          'Failed to delete your account. Please try again.'
      );
    } finally {
      setIsDeleting(false);
    }
  }, [
    deleteInfo,
    deletingUserId,
    isDeleting,
    logout,
    navigate,
    onClose,
  ]);

  if (!open || !user) {
    return null;
  }

  const profileContent = (
    <div className="profile-dialog-content">
      <div className="profile-avatar" aria-hidden="true">
        {(user.name || '?').trim().charAt(0).toUpperCase()}
      </div>

      <div className="profile-details" aria-label="Profile details">
        <div className="profile-detail-row">
          <span className="profile-detail-label">Name</span>
          <span className="profile-detail-value">{user.name || '—'}</span>
        </div>

        <div className="profile-detail-row">
          <span className="profile-detail-label">Date of Birth</span>
          <span className="profile-detail-value">{formatDob(user.dob)}</span>
        </div>

        <div className="profile-detail-row">
          <span className="profile-detail-label">Age</span>
          <span className="profile-detail-value">{user.age ?? '—'}</span>
        </div>

        <div className="profile-detail-row">
          <span className="profile-detail-label">Place</span>
          <span className="profile-detail-value">{user.place || '—'}</span>
        </div>
      </div>

      {profileError && (
        <div className="profile-message profile-message-error" role="alert">
          {profileError}
        </div>
      )}
    </div>
  );

  const editContent = (
    <div className="profile-edit-content">
      {profileError && (
        <div className="profile-message profile-message-error" role="alert">
          {profileError}
        </div>
      )}

      <form className="profile-edit-form" onSubmit={handleUpdateUser}>
        <label className="profile-field">
          <span>Name</span>
          <input
            type="text"
            name="name"
            value={updatedUser.name}
            onChange={handleFieldChange}
            required
            disabled={isSaving}
            autoComplete="name"
          />
        </label>

        <label className="profile-field">
          <span>Date of Birth</span>
          <input
            type="date"
            name="dob"
            value={updatedUser.dob}
            onChange={handleFieldChange}
            required
            disabled={isSaving}
            max={new Date().toISOString().split('T')[0]}
          />
        </label>

        <label className="profile-field">
          <span>Place</span>
          <input
            type="text"
            name="place"
            value={updatedUser.place}
            onChange={handleFieldChange}
            required
            disabled={isSaving}
            autoComplete="address-level2"
          />
        </label>

        <label className="profile-field">
          <span>New Password</span>
          <input
            type="password"
            name="password"
            value={updatedUser.password}
            onChange={handleFieldChange}
            disabled={isSaving}
            autoComplete="new-password"
            placeholder="Leave blank to keep current password"
          />
        </label>

        <label className="profile-field">
          <span>Confirm Password</span>
          <input
            type="password"
            name="confirmPassword"
            value={updatedUser.confirmPassword}
            onChange={handleFieldChange}
            disabled={isSaving}
            autoComplete="new-password"
            placeholder="Repeat new password"
          />
        </label>

        <div className="profile-delete-section">
          <div>
            <h3>Danger Zone</h3>
            <p>
              Permanently delete your account and its transaction history.
            </p>
          </div>

          <Button
            type="button"
            variant="danger"
            onClick={handleDeleteClick}
            disabled={isSaving || isDeleting || isDownloadingBackup}
          >
            {isDeleting ? 'Checking…' : 'Delete Account'}
          </Button>
        </div>

        <div className="profile-edit-actions">
          <Button
            type="button"
            variant="secondary"
            onClick={handleCancelEdit}
            disabled={isSaving}
          >
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={isSaving}>
            {isSaving ? 'Saving…' : 'Save Changes'}
          </Button>
        </div>
      </form>
    </div>
  );

  return (
    <>
      <Modal
        open={open && !isEditing && !showDeleteModal}
        title="Profile"
        onClose={closeProfile}
        overlayClassName="profile-drawer-overlay"
        className="profile-drawer"
        closeOnOverlayClick={!isSaving && !isDeleting && !isDownloadingBackup}
        footer={
          <>
            <Button
              type="button"
              variant="primary"
              onClick={handleEditClick}
              disabled={isSaving || isDeleting || isDownloadingBackup}
            >
              Edit
            </Button>
            <Button
              type="button"
              variant="danger"
              onClick={handleLogout}
              disabled={isSaving || isDeleting || isDownloadingBackup}
            >
              Logout
            </Button>
          </>
        }
      >
        {profileContent}
      </Modal>

      <Modal
        open={open && isEditing && !showDeleteModal}
        title="Edit Profile"
        onClose={handleCancelEdit}
        className="profile-edit-modal"
        closeOnOverlayClick={!isSaving && !isDeleting && !isDownloadingBackup}
      >
        {editContent}
      </Modal>

      {deleteInfo && (
        <DeleteConfirmationDialog
          isOpen={showDeleteModal}
          onClose={closeDeleteModal}
          onConfirm={handleConfirmDelete}
          title="Delete Account"
          headline="Please review before continuing."
          description="Your account can currently be deleted because all required balances have been cleared."
          detailLines={
            deleteInfo.has_transaction_history
              ? [
                  <>
                    You have <strong>{deleteInfo.transaction_count}</strong>{' '}
                    transaction records in your account history.
                  </>,
                  'Deleting your account will permanently delete this transaction history.',
                  'You may optionally download a backup before deleting your account.',
                ]
              : ['No transaction history was found.']
          }
          isDeleting={isDeleting}
          confirmLabel="Delete Account"
          confirmWithoutBackupLabel="Delete Without Backup"
          showBackupSection={deleteInfo.has_transaction_history}
          backupSectionTitle="Optional Backup"
          categories={EXPORT_CATEGORY_OPTIONS}
          selectedCategories={selectedCategories}
          onToggleCategory={toggleCategory}
          onSelectAllCategories={selectAllCategories}
          onClearAllCategories={clearAllCategories}
          onDownloadExcel={handleDownloadExcel}
          onDownloadPdf={handleDownloadPdf}
          isDownloading={isDownloadingBackup}
          backupDownloaded={backupDownloaded}
          dialogError={deleteError}
          onDismissDialogError={() => setDeleteError('')}
        />
      )}
    </>
  );
}

export default ProfileDialog;
