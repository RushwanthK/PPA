import React, { useState, useEffect } from 'react';
import {
  getUsers,
  updateUser,
  deleteUser,
  canDeleteUser,
  exportUserTransactionsExcel,
  exportUserTransactionsPdf
} from '../services/api';
import DeleteConfirmationDialog from '../components/Deleteconfirmationdialog';

import './users.css';

// Mirrors the backend's TRANSACTION_EXPORT_CONFIG categories (excluding
// "all", which the backend treats as shorthand for every category below).
const EXPORT_CATEGORY_OPTIONS = [
  { key: 'banks', label: 'Banks' },
  { key: 'savings', label: 'Savings' },
  { key: 'assets', label: 'Assets' },
  { key: 'credit_cards', label: 'Credit Cards' }
];

const allCategoriesSelected = () =>
  EXPORT_CATEGORY_OPTIONS.reduce((selection, category) => {
    selection[category.key] = true;
    return selection;
  }, {});

const Users = () => {
  const [users, setUsers] = useState([]);

  const [updatedUser, setUpdatedUser] = useState({
    id: '',
    name: '',
    dob: '',
    place: '',
    password: '',
    confirmPassword: ''
  });

  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [notification, setNotification] = useState({
    show: false,
    message: '',
    type: ''
  });

  const [isDeleting, setIsDeleting] = useState(false);

  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteInfo, setDeleteInfo] = useState(null);

  // Tracks exactly which user id the delete modal is currently acting on.
  // Kept separate from `users[0]` so this stays correct even if the users
  // list ever contains more than one entry in the future.
  const [deletingUserId, setDeletingUserId] = useState(null);

  const [isDownloadingBackup, setIsDownloadingBackup] = useState(false);

  // Tracks whether the user has already downloaded a backup for the
  // account currently pending deletion, purely so the confirm button
  // can reflect that back to them.
  const [backupDownloaded, setBackupDownloaded] = useState(false);

  // Which transaction categories should be included in the backup export.
  // Defaults to everything selected so existing "export everything" usage
  // keeps working without the user needing to touch anything.
  const [selectedCategories, setSelectedCategories] = useState(allCategoriesSelected());

  const showNotification = (message, type = 'success') => {
    setNotification({ show: true, message, type });

    setTimeout(() => {
      setNotification({ show: false, message: '', type: '' });
    }, 3000);
  };

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        setLoading(true);

        const response = await getUsers();
        console.log('API Response:', response);

        setUsers(response);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch users:', err);

        setError('Failed to load users. Please try again.');
        setUsers([]);

        showNotification('Failed to load users. Please try again.', 'error');
      } finally {
        setLoading(false);
      }
    };

    fetchUsers();
  }, []);

  const handleUpdateUser = async () => {
    if (updatedUser.password && updatedUser.password !== updatedUser.confirmPassword) {
      showNotification('Passwords do not match', 'error');
      return;
    }

    try {
      setLoading(true);

      const updatePayload = {
        name: updatedUser.name,
        dob: updatedUser.dob,
        place: updatedUser.place
      };

      if (updatedUser.password) {
        updatePayload.password = updatedUser.password;
      }

      const response = await updateUser(updatedUser.id, updatePayload);

      setUsers(prevUsers =>
        prevUsers.map(user =>
          user.id === updatedUser.id ? response.data : user
        )
      );

      setUpdatedUser({
        id: '',
        name: '',
        dob: '',
        place: '',
        password: '',
        confirmPassword: ''
      });

      setIsEditing(false);
      showNotification('User updated successfully!');
    } catch (err) {
      console.error('Failed to update user:', err);

      const errorMessage =
        err.response?.data?.error ||
        err.response?.data?.message ||
        'Failed to update user. Please try again.';

      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteUser = async (id) => {
    if (isDeleting) {
      return;
    }

    try {
      setIsDeleting(true);
      setError(null);

      const checkResponse = await canDeleteUser(id);
      const deletionData = checkResponse.data;

      if (!deletionData.can_delete) {
        const errorDetails = deletionData.details || {};
        const reasons = [];

        if (errorDetails.has_bank_balances) reasons.push('bank accounts');
        if (errorDetails.has_asset_balances) reasons.push('assets');
        if (errorDetails.has_saving_balances) reasons.push('savings');
        if (errorDetails.has_credit_balances) reasons.push('credit cards');

        const errorMessage =
          deletionData.message ||
          `Cannot delete user account. Please clear balances from ${reasons.join(', ')} and try again.`;

        setError(errorMessage);
        return;
      }

      setDeleteInfo(deletionData);
      setDeletingUserId(id);
      setBackupDownloaded(false);
      setSelectedCategories(allCategoriesSelected());
      setShowDeleteModal(true);
    } catch (err) {
      console.error('Failed to check user deletion:', err);

      const errorMessage =
        err.response?.data?.error ||
        err.response?.data?.message ||
        'Unable to check whether this account can be deleted.';

      setError(errorMessage);
    } finally {
      setIsDeleting(false);
    }
  };

  const closeDeleteModal = () => {
    if (isDeleting || isDownloadingBackup) {
      return;
    }

    setShowDeleteModal(false);
    setDeleteInfo(null);
    setDeletingUserId(null);
    setBackupDownloaded(false);
    setSelectedCategories(allCategoriesSelected());
  };

  const toggleCategory = (key) => {
    setSelectedCategories(prev => ({
      ...prev,
      [key]: !prev[key]
    }));

    // Selection changed, so any previously downloaded backup no longer
    // reflects what's currently checked.
    setBackupDownloaded(false);
  };

  const selectAllCategories = () => {
    setSelectedCategories(allCategoriesSelected());
    setBackupDownloaded(false);
  };

  const clearAllCategories = () => {
    setSelectedCategories(
      EXPORT_CATEGORY_OPTIONS.reduce((selection, category) => {
        selection[category.key] = false;
        return selection;
      }, {})
    );
    setBackupDownloaded(false);
  };

  const getSelectedCategoryKeys = () =>
    EXPORT_CATEGORY_OPTIONS
      .filter(category => selectedCategories[category.key])
      .map(category => category.key);

  const downloadBlob = (blob, filename) => {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');

    link.href = url;
    link.download = filename;

    document.body.appendChild(link);
    link.click();
    link.remove();

    window.URL.revokeObjectURL(url);
  };

  const handleDownloadExcel = async () => {
    if (!deleteInfo || !deletingUserId) {
      return;
    }

    const categories = getSelectedCategoryKeys();

    if (categories.length === 0) {
      setError('Select at least one category to include in the backup.');
      return;
    }

    try {
      setIsDownloadingBackup(true);
      setError(null);

      const response = await exportUserTransactionsExcel(deletingUserId, categories);

      const filename = `ppa_transaction_backup_${new Date()
        .toISOString()
        .slice(0, 10)}.xlsx`;

      downloadBlob(response.data, filename);

      setBackupDownloaded(true);
      showNotification('Transaction backup downloaded successfully.');
    } catch (err) {
      console.error('Failed to download Excel backup:', err);
      setError('Unable to download the Excel backup. Your transaction data has not been deleted.');
    } finally {
      setIsDownloadingBackup(false);
    }
  };

  const handleDownloadPdf = async () => {
    if (!deleteInfo || !deletingUserId) {
      return;
    }

    const categories = getSelectedCategoryKeys();

    if (categories.length === 0) {
      setError('Select at least one category to include in the backup.');
      return;
    }

    try {
      setIsDownloadingBackup(true);
      setError(null);

      const response = await exportUserTransactionsPdf(deletingUserId, categories);

      const filename = `ppa_transaction_backup_${new Date()
        .toISOString()
        .slice(0, 10)}.pdf`;

      downloadBlob(response.data, filename);

      setBackupDownloaded(true);
      showNotification('Transaction backup downloaded successfully.');
    } catch (err) {
      console.error('Failed to download PDF backup:', err);
      setError('Unable to download the PDF backup. Your transaction data has not been deleted.');
    } finally {
      setIsDownloadingBackup(false);
    }
  };

  const handleConfirmDelete = async () => {
    if (!deleteInfo || !deletingUserId || isDeleting) {
      return;
    }

    try {
      setIsDeleting(true);
      setError(null);

      const response = await deleteUser(deletingUserId);

      setShowDeleteModal(false);
      setDeleteInfo(null);
      setDeletingUserId(null);
      setBackupDownloaded(false);
      setSelectedCategories(allCategoriesSelected());

      setUsers([]);

      showNotification(response.data?.message || 'User deleted successfully!');

      localStorage.removeItem('token');
      window.location.href = '/';
    } catch (err) {
      console.error('Failed to delete user:', err);

      const errorMessage =
        err.response?.data?.error ||
        err.response?.data?.message ||
        'Failed to delete user. Please try again.';

      setError(errorMessage);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleEditClick = (user) => {
    const formattedDob = user.dob.split('T')[0];

    setUpdatedUser({
      id: user.id,
      name: user.name,
      dob: formattedDob,
      place: user.place,
      password: '',
      confirmPassword: ''
    });

    setIsEditing(true);
  };

  if (loading && !isEditing) {
    return (
      <div className="loading-overlay">
        <div className="loading-spinner"></div>
      </div>
    );
  }

  return (
    <div className="users-container">
      {notification.show && (
        <div className={`notification ${notification.type}`}>
          {notification.message}
        </div>
      )}

      <h2>Edit Profile</h2>

      {error && (
        <div className="error">
          <span>{error}</span>
          <button className="error-dismiss" onClick={() => setError(null)} aria-label="Dismiss error">
            &times;
          </button>
        </div>
      )}

      {loading ? (
        <div className="loading">Loading users...</div>
      ) : users && users.length > 0 ? (
        <ul className="user-list">
          {users.map(user => (
            <li key={user.id} className="user-item">
              <div className="user-main-info">
                <span className="user-name">{user.name}</span>
                <div className="user-actions">
                  <button
                    onClick={() => handleEditClick(user)}
                    disabled={loading}
                    className="edit-btn"
                  >
                    Edit
                  </button>
                  <button
                    className="delete-button"
                    onClick={() => handleDeleteUser(user.id)}
                    disabled={loading || isDeleting}
                  >
                    {isDeleting ? 'Deleting...' : 'Delete'}
                  </button>
                </div>
              </div>
              <div className="user-additional-info">
                <span>Age: {user.age}</span>
                <span>Location: {user.place}</span>
                <span>DOB: {new Date(user.dob).toLocaleDateString()}</span>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p>No users found.</p>
      )}

      {isEditing && (
        <div className="form-container">
          <h3>Update User</h3>
          <form onSubmit={(e) => {
            e.preventDefault();
            handleUpdateUser();
          }}>
            <input
              type="text"
              placeholder="Name"
              value={updatedUser.name}
              onChange={(e) => setUpdatedUser({ ...updatedUser, name: e.target.value })}
              required
              disabled={loading}
            />

            <input
              type="date"
              placeholder="Date of Birth"
              value={updatedUser.dob}
              onChange={(e) => setUpdatedUser({ ...updatedUser, dob: e.target.value })}
              required
              disabled={loading}
              max={new Date().toISOString().split('T')[0]}
            />

            <input
              type="text"
              placeholder="Place"
              value={updatedUser.place}
              onChange={(e) => setUpdatedUser({ ...updatedUser, place: e.target.value })}
              required
              disabled={loading}
            />

            <input
              type="password"
              placeholder="New Password (optional)"
              value={updatedUser.password}
              onChange={(e) => setUpdatedUser({ ...updatedUser, password: e.target.value })}
              disabled={loading}
            />

            <input
              type="password"
              placeholder="Confirm Password"
              value={updatedUser.confirmPassword}
              onChange={(e) => setUpdatedUser({ ...updatedUser, confirmPassword: e.target.value })}
              disabled={loading}
            />

            <div className="form-buttons">
              <button type="submit" className="create-btn" disabled={loading}>
                {loading ? 'Updating...' : 'Update'}
              </button>
              <button type="button" className="cancel-btn" onClick={() => setIsEditing(false)} disabled={loading}>
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

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
                    You have <strong>{deleteInfo.transaction_count}</strong> transaction records in your account history.
                  </>,
                  'Deleting your account will permanently delete this transaction history.',
                  'You may optionally download a backup before deleting your account.'
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
        />
      )}
    </div>
  );
};

export default Users;