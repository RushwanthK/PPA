import React, { useEffect, useMemo, useState } from 'react';

import {
  getAssets,
  createAssetTransaction,
  createAsset,
  getAssetTransactions,
  deleteAsset,
  updateAsset,
  exportUserTransactionsExcel,
  exportUserTransactionsPdf,
} from '../services/api';
import { useAuth } from '../AuthContext';

import Button from '../components/ui/Button';
import SearchBar from '../components/ui/SearchBar';
import DataTable from '../components/ui/DataTable';

import EntityFormDialog from '../components/dialogs/EntityFormDialog';
import TransactionFormDialog from '../components/dialogs/TransactionFormDialog';
import TransactionTableDialog from '../components/dialogs/TransactionTableDialog';

import DeleteConfirmationDialog from '../components/Deleteconfirmationdialog';

import './Assets.css';

const ASSET_CATEGORIES = [
  'Provident Fund',
  'Mutual Funds',
  'Stocks',
  'ETF',
  'FD',
  'Other',
];

export default function Assets() {
  const { user } = useAuth();

  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [formError, setFormError] = useState(null);
  const [transactionFormError, setTransactionFormError] = useState(null);
  const [transactionTableError, setTransactionTableError] = useState(null);

  const [formData, setFormData] = useState({
    id: '',
    name: '',
    platform: '',
    category: '',
  });
  const [transactionData, setTransactionData] = useState({
    assetId: '',
    type: 'deposit',
    amount: '',
    description: '',
    category: '',
  });

  const [selectedAssetId, setSelectedAssetId] = useState(null);
  const [showTransactions, setShowTransactions] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [showTransactionForm, setShowTransactionForm] = useState(false);

  // Server-side transaction pagination/filter state.
  const [transactions, setTransactions] = useState([]);
  const [transactionPage, setTransactionPage] = useState(1);
  const [transactionPageSize, setTransactionPageSize] = useState(25);
  const [transactionSearchInput, setTransactionSearchInput] = useState('');
  const [transactionSearch, setTransactionSearch] = useState('');
  const [transactionType, setTransactionType] = useState('');
  const [transactionTotal, setTransactionTotal] = useState(0);
  const [transactionTotalPages, setTransactionTotalPages] = useState(0);
  const [transactionsLoading, setTransactionsLoading] = useState(false);
  const [transactionRefreshKey, setTransactionRefreshKey] = useState(0);

  // Delete-confirmation dialog state remains page-specific.
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletingAssetId, setDeletingAssetId] = useState(null);
  const [isDeletingAsset, setIsDeletingAsset] = useState(false);
  const [deleteDialogError, setDeleteDialogError] = useState(null);
  const [isDownloadingAssetBackup, setIsDownloadingAssetBackup] = useState(false);
  const [assetBackupDownloaded, setAssetBackupDownloaded] = useState(false);

  // Main-table search and sort remain local because the asset list itself is
  // deliberately unpaginated.
  const [searchText, setSearchText] = useState('');
  const [sortBy, setSortBy] = useState('name');
  const [sortDir, setSortDir] = useState('asc');

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await getAssets();
        const data = Array.isArray(response?.data)
          ? response.data
          : (Array.isArray(response) ? response : []);

        setAssets(data);
      } catch (err) {
        console.error('Error fetching assets:', err);
        setError(err.message || 'Failed to fetch assets');
        setAssets([]);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  // Debounce transaction search so typing does not issue one request per keystroke.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setTransactionSearch(transactionSearchInput.trim());
    }, 300);

    return () => window.clearTimeout(timer);
  }, [transactionSearchInput]);

  // Fetch only the requested transaction page from the backend.
  useEffect(() => {
    if (!showTransactions || !selectedAssetId) {
      return undefined;
    }

    let cancelled = false;

    const fetchTransactions = async () => {
      try {
        setTransactionsLoading(true);
        setTransactionTableError(null);

        const response = await getAssetTransactions(selectedAssetId, {
          page: transactionPage,
          page_size: transactionPageSize,
          search: transactionSearch,
          type: transactionType,
        });

        if (cancelled) return;

        setTransactions(
          Array.isArray(response?.transactions)
            ? response.transactions
            : []
        );
        setTransactionTotal(Number(response?.total) || 0);
        setTransactionTotalPages(Number(response?.total_pages) || 0);

        if (response?.page && response.page !== transactionPage) {
          setTransactionPage(response.page);
        }
      } catch (err) {
        if (cancelled) return;

        console.error('Error fetching asset transactions:', err);
        setTransactionTableError(
          err.message || 'Failed to fetch asset transactions'
        );
        setTransactions([]);
        setTransactionTotal(0);
        setTransactionTotalPages(0);
      } finally {
        if (!cancelled) {
          setTransactionsLoading(false);
        }
      }
    };

    fetchTransactions();

    return () => {
      cancelled = true;
    };
  }, [
    showTransactions,
    selectedAssetId,
    transactionPage,
    transactionPageSize,
    transactionSearch,
    transactionType,
    transactionRefreshKey,
  ]);

  const safeNumber = (value) => {
    const number = Number(value);
    return Number.isNaN(number) ? 0 : number;
  };

  const handleInputChange = (event) => {
    const { name, value } = event.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleTransactionChange = (event) => {
    const { name, value } = event.target;
    setTransactionData(prev => ({ ...prev, [name]: value }));
  };

  const resetForm = () => {
    setFormData({
      id: '',
      name: '',
      platform: '',
      category: '',
    });
    setFormError(null);
    setShowForm(false);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    try {
      setFormError(null);
      setLoading(true);

      const name = formData.name.trim();
      if (!name) {
        throw new Error('Please enter an asset name');
      }

      if (!formData.category) {
        throw new Error('Please select an asset category');
      }

      if (formData.id) {
        const response = await updateAsset(formData.id, {
          name,
          platform: formData.platform,
          category: formData.category,
        });

        const updatedAsset = response?.asset;
        if (!updatedAsset) {
          throw new Error(
            'Asset was updated, but no asset data was returned'
          );
        }

        setAssets(prevAssets =>
          prevAssets.map(asset =>
            String(asset.id) === String(updatedAsset.id)
              ? updatedAsset
              : asset
          )
        );
      } else {
        const response = await createAsset({
          name,
          platform: formData.platform,
          category: formData.category,
        });

        const createdAsset = response?.asset;
        if (!createdAsset) {
          throw new Error(
            'Asset was created, but no asset data was returned'
          );
        }

        setAssets(prevAssets => [...prevAssets, createdAsset]);
      }

      resetForm();
    } catch (err) {
      console.error('Error saving asset:', err);
      setFormError(
        err.response?.data?.error || err.message || 'Failed to save asset'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleAddTransaction = (assetId) => {
    setTransactionFormError(null);
    setTransactionData(prev => ({
      ...prev,
      assetId: String(assetId),
    }));
    setShowTransactionForm(true);
  };

  const handleTransactionSubmit = async (event) => {
    event.preventDefault();

    try {
      setTransactionFormError(null);
      setLoading(true);

      if (!transactionData.assetId) {
        throw new Error('Asset not selected for transaction');
      }

      if (!transactionData.amount || isNaN(transactionData.amount)) {
        throw new Error('Please enter a valid amount');
      }

      const amount = parseFloat(transactionData.amount);
      if (amount <= 0) {
        throw new Error('Amount must be greater than 0');
      }

      const response = await createAssetTransaction(
        transactionData.assetId,
        {
          amount,
          type: transactionData.type,
          description: transactionData.description,
          category: transactionData.category,
        }
      );

      const newBalance = response?.balance;
      if (newBalance === undefined) {
        throw new Error(
          'Transaction was added, but the server did not return the updated asset balance'
        );
      }

      setAssets(prevAssets =>
        prevAssets.map(asset =>
          String(asset.id) === String(transactionData.assetId)
            ? { ...asset, balance: newBalance }
            : asset
        )
      );

      if (
        selectedAssetId &&
        String(selectedAssetId) === String(transactionData.assetId)
      ) {
        setTransactionPage(1);
        setTransactionRefreshKey(prev => prev + 1);
      }

      setTransactionData({
        assetId: '',
        type: 'deposit',
        amount: '',
        description: '',
        category: '',
      });
      setShowTransactionForm(false);
    } catch (err) {
      console.error('Error adding asset transaction:', err);
      setTransactionFormError(
        err.response?.data?.error || err.message || 'Failed to add transaction'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleViewTransactions = (assetId) => {
    setTransactionTableError(null);
    setSelectedAssetId(assetId);
    setTransactionPage(1);
    setTransactionPageSize(25);
    setTransactionSearchInput('');
    setTransactionSearch('');
    setTransactionType('');
    setTransactionTotal(0);
    setTransactionTotalPages(0);
    setTransactions([]);
    setShowTransactions(true);
  };

  const handleTransactionSearchChange = (event) => {
    setTransactionSearchInput(event.target.value);
    setTransactionPage(1);
  };

  const handleTransactionTypeChange = (event) => {
    setTransactionType(event.target.value);
    setTransactionPage(1);
  };

  const handleTransactionPageChange = (page) => {
    if (
      page < 1 ||
      (transactionTotalPages > 0 && page > transactionTotalPages)
    ) {
      return;
    }

    setTransactionPage(page);
  };

  const handleTransactionPageSizeChange = (event) => {
    setTransactionPageSize(Number(event.target.value));
    setTransactionPage(1);
  };

  const handleDeleteAsset = (assetId) => {
    if (isDeletingAsset || isDownloadingAssetBackup) {
      return;
    }

    const asset = assets.find(
      item => String(item.id) === String(assetId)
    );

    setError(null);

    if (!asset) {
      setDeletingAssetId(assetId);
      setDeleteDialogError('Asset not found in state.');
      setAssetBackupDownloaded(false);
      setShowDeleteModal(true);
      return;
    }

    const balance = safeNumber(asset.balance);

    setDeleteDialogError(
      balance !== 0
        ? `Asset "${asset.name}" cannot be deleted because its current balance is Rs. ${balance.toFixed(2)}. Please bring the balance to zero and try again.`
        : null
    );

    setDeletingAssetId(assetId);
    setAssetBackupDownloaded(false);
    setShowDeleteModal(true);
  };

  const closeDeleteModal = () => {
    if (isDeletingAsset || isDownloadingAssetBackup) {
      return;
    }

    setShowDeleteModal(false);
    setDeletingAssetId(null);
    setDeleteDialogError(null);
    setAssetBackupDownloaded(false);
  };

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

  const handleDownloadAssetBackupExcel = async () => {
    if (!deletingAssetId || isDeletingAsset || isDownloadingAssetBackup) {
      return;
    }

    try {
      setIsDownloadingAssetBackup(true);
      setDeleteDialogError(null);

      if (!user?.id) {
        throw new Error(
          'Unable to determine the current user account for backup export.'
        );
      }

      const response = await exportUserTransactionsExcel(
        user.id,
        ['assets']
      );

      const filename =
        `asset_transactions_backup_${new Date()
          .toISOString()
          .slice(0, 10)}.xlsx`;

      downloadBlob(response.data, filename);
      setAssetBackupDownloaded(true);
    } catch (err) {
      console.error('Failed to download asset Excel backup:', err);
      setDeleteDialogError(
        err.message ||
        'Unable to download the Excel asset transaction backup. Your asset has not been deleted.'
      );
    } finally {
      setIsDownloadingAssetBackup(false);
    }
  };

  const handleDownloadAssetBackupPdf = async () => {
    if (!deletingAssetId || isDeletingAsset || isDownloadingAssetBackup) {
      return;
    }

    try {
      setIsDownloadingAssetBackup(true);
      setDeleteDialogError(null);

      if (!user?.id) {
        throw new Error(
          'Unable to determine the current user account for backup export.'
        );
      }

      const response = await exportUserTransactionsPdf(
        user.id,
        ['assets']
      );

      const filename =
        `asset_transactions_backup_${new Date()
          .toISOString()
          .slice(0, 10)}.pdf`;

      downloadBlob(response.data, filename);
      setAssetBackupDownloaded(true);
    } catch (err) {
      console.error('Failed to download asset PDF backup:', err);
      setDeleteDialogError(
        err.message ||
        'Unable to download the PDF asset transaction backup. Your asset has not been deleted.'
      );
    } finally {
      setIsDownloadingAssetBackup(false);
    }
  };

  const handleConfirmDeleteAsset = async () => {
    if (!deletingAssetId || isDeletingAsset || isDownloadingAssetBackup) {
      return;
    }

    const asset = assets.find(
      item => String(item.id) === String(deletingAssetId)
    );

    if (!asset) {
      setDeleteDialogError('Asset not found in state.');
      return;
    }

    const balance = safeNumber(asset.balance);

    if (balance !== 0) {
      setDeleteDialogError(
        `Asset "${asset.name}" cannot be deleted because its current balance is Rs. ${balance.toFixed(2)}. Please bring the balance to zero and try again.`
      );
      return;
    }

    try {
      setIsDeletingAsset(true);
      setDeleteDialogError(null);
      setError(null);

      await deleteAsset(deletingAssetId);

      setAssets(prevAssets =>
        prevAssets.filter(
          item => String(item.id) !== String(deletingAssetId)
        )
      );

      if (String(selectedAssetId) === String(deletingAssetId)) {
        setSelectedAssetId(null);
        setTransactions([]);
        setShowTransactions(false);
      }

      setShowDeleteModal(false);
      setDeletingAssetId(null);
      setDeleteDialogError(null);
      setAssetBackupDownloaded(false);
    } catch (err) {
      console.error('Failed to delete asset:', err);
      setDeleteDialogError(
        err.message || `Failed to delete asset "${asset.name}".`
      );
    } finally {
      setIsDeletingAsset(false);
    }
  };

  const handleSortClick = (column) => {
    if (sortBy === column) {
      setSortDir(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(column);
      setSortDir('asc');
    }
  };

  const visibleAssets = useMemo(() => {
    const text = (searchText || '').trim().toLowerCase();

    const filtered = (assets || []).filter(asset => {
      if (!text) return true;
      return (asset.name || '').toLowerCase().includes(text);
    });

    const sorted = [...filtered].sort((a, b) => {
      let va;
      let vb;

      if (sortBy === 'balance') {
        va = safeNumber(a.balance);
        vb = safeNumber(b.balance);
      } else if (sortBy === 'platform') {
        va = (a.platform || '').toString().toLowerCase();
        vb = (b.platform || '').toString().toLowerCase();
      } else if (sortBy === 'category') {
        va = (a.category || '').toString().toLowerCase();
        vb = (b.category || '').toString().toLowerCase();
      } else {
        va = (a.name || '').toString().toLowerCase();
        vb = (b.name || '').toString().toLowerCase();
      }

      if (va < vb) return sortDir === 'asc' ? -1 : 1;
      if (va > vb) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });

    return sorted;
  }, [assets, searchText, sortBy, sortDir]);

  const totals = useMemo(() => {
    return visibleAssets.reduce(
      (accumulator, asset) => {
        accumulator.balance += safeNumber(asset.balance);
        return accumulator;
      },
      { balance: 0 }
    );
  }, [visibleAssets]);

  const assetPendingDeletion =
    assets.find(asset => String(asset.id) === String(deletingAssetId)) || null;

  const selectedAsset =
    assets.find(asset => String(asset.id) === String(selectedAssetId)) || null;

  if (loading && assets.length === 0) {
    return <div className="loading">Loading assets...</div>;
  }

  return (
    <div className="assets-container">
      <h1>Assets</h1>

      {error && (
        <div className="assets-error-with-close" role="alert">
          <span>{error}</span>
          <button
            type="button"
            className="error-dismiss"
            onClick={() => setError(null)}
            aria-label="Dismiss error"
          >
            &times;
          </button>
        </div>
      )}

      <div className="assets-toolbar">
        <Button
          type="button"
          variant="primary"
          onClick={() => {
            setFormError(null);
            setShowForm(true);
          }}
          disabled={loading}
        >
          {loading ? 'Processing...' : 'Add Asset'}
        </Button>

        <div className="assets-toolbar-search">
          <SearchBar
            value={searchText}
            onChange={event => setSearchText(event.target.value)}
            placeholder="Search by name..."
            ariaLabel="Search assets by name"
            disabled={loading}
          />
        </div>
      </div>

      <EntityFormDialog
        open={showForm}
        mode={formData.id ? 'edit' : 'create'}
        title={formData.id ? 'Edit Asset' : 'Add Asset'}
        onClose={resetForm}
        onSubmit={handleSubmit}
        submitting={loading}
        submitLabel={formData.id ? 'Update' : 'Save'}
        error={formError}
        onDismissError={() => setFormError(null)}
      >
        <div className="form-group">
          <label htmlFor="asset-name">Asset Name:</label>
          <input
            type="text"
            id="asset-name"
            name="name"
            placeholder="Asset Name"
            value={formData.name}
            onChange={handleInputChange}
            required
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="asset-platform">Platform:</label>
          <input
            type="text"
            id="asset-platform"
            name="platform"
            placeholder="Platform (Optional)"
            value={formData.platform}
            onChange={handleInputChange}
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="asset-category">Category:</label>
          <select
            id="asset-category"
            name="category"
            value={formData.category}
            onChange={handleInputChange}
            required
            disabled={loading}
          >
            <option value="" disabled>
              Select Category
            </option>
            {ASSET_CATEGORIES.map(category => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </select>
        </div>
      </EntityFormDialog>

      <TransactionFormDialog
        open={showTransactionForm}
        title={
          <>
            Add Transaction -{' '}
            <span className="accent-text">
              {assets.find(
                asset =>
                  String(asset.id) === String(transactionData.assetId)
              )?.name || 'Asset'}
            </span>
          </>
        }
        onClose={() => {
          setShowTransactionForm(false);
          setTransactionFormError(null);
        }}
        onSubmit={handleTransactionSubmit}
        submitting={loading}
        submitLabel="Submit"
        error={transactionFormError}
        onDismissError={() => setTransactionFormError(null)}
      >
        <div className="form-group">
          <label htmlFor="asset-transaction-type">Transaction Type:</label>
          <select
            id="asset-transaction-type"
            name="type"
            value={transactionData.type}
            onChange={handleTransactionChange}
            required
            disabled={loading}
          >
            <option value="deposit">Deposit</option>
            <option value="withdraw">Withdraw</option>
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="asset-transaction-amount">Amount:</label>
          <input
            type="number"
            id="asset-transaction-amount"
            name="amount"
            step="0.01"
            min="0.01"
            placeholder="Amount"
            value={transactionData.amount}
            onChange={handleTransactionChange}
            required
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="asset-transaction-description">Description:</label>
          <input
            type="text"
            id="asset-transaction-description"
            name="description"
            placeholder="Description (Optional)"
            value={transactionData.description}
            onChange={handleTransactionChange}
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="asset-transaction-category">Category:</label>
          <input
            type="text"
            id="asset-transaction-category"
            name="category"
            placeholder="Category (Optional)"
            value={transactionData.category}
            onChange={handleTransactionChange}
            disabled={loading}
          />
        </div>
      </TransactionFormDialog>

      <div className="assets-table-section">
        <DataTable
          columns={[
            {
              key: 'name',
              label: 'Name',
              sortable: true,
            },
            {
              key: 'balance',
              label: 'Balance',
              sortable: true,
              render: asset =>
                `Rs. ${safeNumber(asset.balance).toFixed(2)}`,
            },
            {
              key: 'platform',
              label: 'Platform',
              sortable: true,
              render: asset => asset.platform || 'N/A',
            },
            {
              key: 'category',
              label: 'Category',
              sortable: true,
              render: asset => asset.category || 'N/A',
            },
          ]}
          data={visibleAssets}
          rowKey="id"
          loading={loading && assets.length === 0}
          emptyMessage="No assets found"
          sortBy={sortBy}
          sortDirection={sortDir}
          onSort={handleSortClick}
          renderActions={asset => (
            <>
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setFormData({
                    id: asset.id,
                    name: asset.name,
                    platform: asset.platform || '',
                    category: asset.category || '',
                  });
                  setShowForm(true);
                }}
                disabled={loading}
              >
                Edit
              </Button>

              <Button
                type="button"
                variant="primary"
                onClick={() => handleAddTransaction(asset.id)}
                disabled={loading}
              >
                Add Transaction
              </Button>

              <Button
                type="button"
                variant="secondary"
                onClick={() => handleViewTransactions(asset.id)}
                disabled={loading}
              >
                View Transactions
              </Button>

              <Button
                type="button"
                variant="danger"
                onClick={() => handleDeleteAsset(asset.id)}
                disabled={loading || isDeletingAsset}
              >
                Delete
              </Button>
            </>
          )}
          renderFooter={() => (
            <tr className="totals-row">
              <td>Totals</td>
              <td>Rs. {totals.balance.toFixed(2)}</td>
              <td />
              <td />
              <td />
            </tr>
          )}
        />
      </div>

      <TransactionTableDialog
        open={showTransactions}
        title={
          <>
            Transactions for{' '}
            <span className="accent-text">
              {selectedAsset?.name || 'Asset'}
            </span>
          </>
        }
        transactions={transactions}
        loading={transactionsLoading}
        onClose={() => {
          setShowTransactions(false);
          setTransactionTableError(null);
        }}
        searchText={transactionSearchInput}
        onSearchChange={handleTransactionSearchChange}
        transactionType={transactionType}
        onTransactionTypeChange={handleTransactionTypeChange}
        transactionTypeOptions={[
          { value: 'deposit', label: 'Deposit' },
          { value: 'withdraw', label: 'Withdraw' },
        ]}
        page={transactionPage}
        totalPages={transactionTotalPages}
        totalTransactions={transactionTotal}
        pageSize={transactionPageSize}
        onPageChange={handleTransactionPageChange}
        onPageSizeChange={handleTransactionPageSizeChange}
        onAddTransaction={() => handleAddTransaction(selectedAssetId)}
        addTransactionDisabled={loading}
        error={transactionTableError}
        onDismissError={() => setTransactionTableError(null)}
        columns={[
          {
            key: 'date',
            label: 'Date',
          },
          {
            key: 'transaction_type',
            label: 'Type',
            render: transaction => (
              <span className={`transaction-${transaction.transaction_type}`}>
                {transaction.transaction_type}
              </span>
            ),
          },
          {
            key: 'amount',
            label: 'Amount',
            render: transaction =>
              `Rs. ${safeNumber(transaction.amount).toFixed(2)}`,
          },
          {
            key: 'description',
            label: 'Description',
            render: transaction => transaction.description || '-',
          },
        ]}
        emptyMessage="No transactions found."
      />

      {deletingAssetId && (
        <DeleteConfirmationDialog
          isOpen={showDeleteModal}
          onClose={closeDeleteModal}
          onConfirm={handleConfirmDeleteAsset}
          title="Delete Asset"
          headline={`Delete "${assetPendingDeletion?.name || 'this asset'}"?`}
          description={`Current balance: Rs. ${safeNumber(
            assetPendingDeletion?.balance
          ).toFixed(2)}`}
          detailLines={[
            'This action cannot be undone.',
            'An asset can only be deleted when its balance is zero.',
            'You may download a backup of the asset transaction history before deleting this asset.',
          ]}
          isDeleting={isDeletingAsset}
          confirmLabel="Delete Asset"
          confirmWithoutBackupLabel="Delete Without Backup"
          cancelLabel="Cancel"
          showBackupSection={true}
          backupSectionTitle="Backup Asset Transactions"
          onDownloadExcel={handleDownloadAssetBackupExcel}
          onDownloadPdf={handleDownloadAssetBackupPdf}
          isDownloading={isDownloadingAssetBackup}
          backupDownloaded={assetBackupDownloaded}
          backupConfirmedMessage="Asset transaction backup downloaded successfully."
          excelDownloadLabel="Download Excel"
          pdfDownloadLabel="Download PDF"
          dialogError={deleteDialogError}
          onDismissDialogError={() => setDeleteDialogError(null)}
        />
      )}
    </div>
  );
}
