// src/pages/bank.js
import React, { useState, useEffect, useMemo } from 'react';

import {
  getBanks,
  createBank,
  updateBank,
  deleteBank,
  addBankTransaction,
  getBankTransactions,
  exportUserTransactionsExcel,
  exportUserTransactionsPdf
} from '../services/api';
import { useAuth } from '../AuthContext';

import Button from '../components/ui/Button';
import SearchBar from '../components/ui/SearchBar';
import DataTable from '../components/ui/DataTable';

import EntityFormDialog from '../components/dialogs/EntityFormDialog';
import TransactionFormDialog from '../components/dialogs/TransactionFormDialog';
import TransactionTableDialog from '../components/dialogs/TransactionTableDialog';

import DeleteConfirmationDialog from '../components/Deleteconfirmationdialog';

import './bank.css';

export default function Bank() {
  const { user } = useAuth();
  const [banks, setBanks] = useState([]);
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
  const [formData, setFormData] = useState({ id: '', name: '' });
  const [transactionData, setTransactionData] = useState({
    bankId: '',
    amount: '',
    type: 'income',
    description: '',
    category: ''
  });
  const [selectedBankId, setSelectedBankId] = useState(null);
  const [showTransactions, setShowTransactions] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [showTransactionForm, setShowTransactionForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // Delete-confirmation dialog state, kept separate from the general
  // `loading` flag (same pattern as the Users page) so the rest of the
  // page isn't disabled just because the delete dialog is open.
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletingBankId, setDeletingBankId] = useState(null);
  const [isDeletingBank, setIsDeletingBank] = useState(false);
  const [deleteDialogError, setDeleteDialogError] = useState(null);
  const [isDownloadingBankBackup, setIsDownloadingBankBackup] = useState(false);
  const [bankBackupDownloaded, setBankBackupDownloaded] = useState(false);

  // UI state for search & sorting
  const [searchText, setSearchText] = useState('');
  const [sortBy, setSortBy] = useState('name'); // default sort
  const [sortDir, setSortDir] = useState('asc');

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        const banksResponse = await getBanks();
        const arr = Array.isArray(banksResponse?.data) ? banksResponse.data : (Array.isArray(banksResponse) ? banksResponse : []);
        setBanks(arr);
      } catch (err) {
        console.error('Error fetching data:', err);
        setError(err.message || 'Failed to fetch data');
        setBanks([]);
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

  // Transaction history is server-paginated and server-filtered. Only the
  // current page is kept in React state.
  useEffect(() => {
    if (!showTransactions || !selectedBankId) {
      return undefined;
    }

    let cancelled = false;

    const fetchTransactions = async () => {
      try {
        setTransactionsLoading(true);
        setError(null);

        const response = await getBankTransactions(
          selectedBankId,
          {
            page: transactionPage,
            page_size: transactionPageSize,
            search: transactionSearch,
            type: transactionType,
          }
        );

        if (cancelled) return;

        setTransactions(Array.isArray(response?.transactions) ? response.transactions : []);
        setTransactionTotal(Number(response?.total) || 0);
        setTransactionTotalPages(Number(response?.total_pages) || 0);

        // The API can move a request back to the last valid page after a
        // filter reduces the result set. Keep the UI state in sync.
        if (response?.page && response.page !== transactionPage) {
          setTransactionPage(response.page);
        }
      } catch (err) {
        if (cancelled) return;

        console.error('Error fetching transactions:', err);
        setError(err.message || 'Failed to fetch transactions');
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
    selectedBankId,
    transactionPage,
    transactionPageSize,
    transactionSearch,
    transactionType,
    transactionRefreshKey,
  ]);

  // ---------- helpers ----------
  const safeNumber = (v) => {
    const n = Number(v);
    return Number.isNaN(n) ? 0 : n;
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleTransactionChange = (e) => {
    const { name, value } = e.target;
    setTransactionData(prev => ({ ...prev, [name]: value }));
  };

  // ---------- API actions ----------
  const handleSubmit = async (e) => {
    e.preventDefault();

    try {
      setError(null);
      setSuccess(null);
      setLoading(true);

      const name = formData.name.trim();

      if (!name) {
        throw new Error('Please enter a bank name');
      }

      if (formData.id) {
        const response = await updateBank(formData.id, { name });

        const updatedBank = response?.bank;

        if (!updatedBank) {
          throw new Error('Bank was updated, but no bank data was returned');
        }

        setBanks(prevBanks =>
          prevBanks.map(bank =>
            String(bank.id) === String(updatedBank.id)
              ? updatedBank
              : bank
          )
        );

        setSuccess('Bank updated successfully!');
      } else {
        const response = await createBank({ name });

        const createdBank = response?.bank;

        if (!createdBank) {
          throw new Error('Bank was created, but no bank data was returned');
        }

        setBanks(prevBanks => [
          ...prevBanks,
          createdBank
        ]);

        setSuccess('Bank created successfully!');
      }

      resetForm();
    } catch (err) {
      console.error('Error saving bank:', err);
      setError(err.message || 'Failed to save bank');
    } finally {
      setLoading(false);
    }
  };

  const handleTransactionSubmit = async (e) => {
    e.preventDefault();

    try {
      setError(null);
      setSuccess(null);
      setLoading(true);

      if (
        !transactionData.amount ||
        isNaN(transactionData.amount)
      ) {
        throw new Error('Please enter a valid amount');
      }

      const amount = parseFloat(transactionData.amount);

      if (amount <= 0) {
        throw new Error('Amount must be greater than 0');
      }

      const response = await addBankTransaction(
        transactionData.bankId,
        {
          amount,
          type: transactionData.type,
          description: transactionData.description,
          category: transactionData.category
        }
      );

      const newBalance = response?.balance;
      const createdTransaction = response?.transaction;

      if (newBalance === undefined || !createdTransaction) {
        throw new Error(
          'Transaction was added, but the server did not return the updated transaction data'
        );
      }

      setBanks(prevBanks =>
        prevBanks.map(bank =>
          String(bank.id) === String(transactionData.bankId)
            ? {
                ...bank,
                balance: newBalance
              }
            : bank
        )
      );

      // The transaction table is server-paginated, so do not mutate a partial
      // client-side page manually. Refresh page 1 to include the newest row.
      if (
        selectedBankId &&
        String(selectedBankId) === String(transactionData.bankId)
      ) {
        setTransactionPage(1);
        setTransactionRefreshKey(prev => prev + 1);
      }

      setSuccess('Transaction added successfully!');

      setTransactionData({
        bankId: '',
        amount: '',
        type: 'income',
        description: '',
        category: ''
      });

      setShowTransactionForm(false);
    } catch (err) {
      console.error('Error adding transaction:', err);
      setError(
        err.message ||
        'Failed to add transaction'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteBank = (bankId) => {
    if (isDeletingBank || isDownloadingBankBackup) return;

    const bank = banks.find(
      b => String(b.id) === String(bankId)
    );

    const currentBalance = safeNumber(bank?.balance);

    // General page errors should not be used for delete-dialog errors.
    setError(null);
    setSuccess(null);

    // Show the balance validation directly inside the delete dialog.
    setDeleteDialogError(
      Math.abs(currentBalance) > 0.000001
        ? `Cannot delete "${bank?.name || 'this bank'}" because its current balance is Rs. ${currentBalance.toFixed(2)}. Please bring the balance to zero and try again.`
        : null
    );

    setDeletingBankId(bankId);
    setBankBackupDownloaded(false);
    setShowDeleteModal(true);
  };

  const closeDeleteModal = () => {
    if (isDeletingBank || isDownloadingBankBackup) return;

    setShowDeleteModal(false);
    setDeletingBankId(null);
    setDeleteDialogError(null);
    setBankBackupDownloaded(false);
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


  const handleDownloadBankBackupExcel = async () => {
    if (
      !deletingBankId ||
      isDownloadingBankBackup ||
      isDeletingBank
    ) {
      return;
    }

    try {
      setIsDownloadingBankBackup(true);
      setDeleteDialogError(null);

      const userId = user?.id;

      if (!userId) {
        throw new Error(
          'Unable to determine the current user account for backup export.'
        );
      }

      const response = await exportUserTransactionsExcel(
        userId,
        ['banks']
      );

      const filename =
        `bank_transactions_backup_${new Date()
          .toISOString()
          .slice(0, 10)}.xlsx`;

      downloadBlob(response.data, filename);

      setBankBackupDownloaded(true);
    } catch (err) {
      console.error(
        'Failed to download bank Excel backup:',
        err
      );

      setDeleteDialogError(
        err.message ||
        'Unable to download the Excel transaction backup. Your bank account has not been deleted.'
      );
    } finally {
      setIsDownloadingBankBackup(false);
    }
  };

  const handleDownloadBankBackupPdf = async () => {
    if (
      !deletingBankId ||
      isDownloadingBankBackup ||
      isDeletingBank
    ) {
      return;
    }

    try {
      setIsDownloadingBankBackup(true);
      setDeleteDialogError(null);

      const userId = user?.id;

      if (!userId) {
        throw new Error(
          'Unable to determine the current user account for backup export.'
        );
      }

      const response = await exportUserTransactionsPdf(
        userId,
        ['banks']
      );

      const filename =
        `bank_transactions_backup_${new Date()
          .toISOString()
          .slice(0, 10)}.pdf`;

      downloadBlob(response.data, filename);

      setBankBackupDownloaded(true);
    } catch (err) {
      console.error(
        'Failed to download bank PDF backup:',
        err
      );

      setDeleteDialogError(
        err.message ||
        'Unable to download the PDF transaction backup. Your bank account has not been deleted.'
      );
    } finally {
      setIsDownloadingBankBackup(false);
    }
  };

  const handleConfirmDeleteBank = async () => {
    if (
      !deletingBankId ||
      isDeletingBank ||
      isDownloadingBankBackup
    ) {
      return;
    }

    const bank = banks.find(
      b => String(b.id) === String(deletingBankId)
    );

    const currentBalance = safeNumber(bank?.balance);

    // Prevent the request from even being sent when the balance
    // is non-zero. The error stays inside the dialog.
    if (Math.abs(currentBalance) > 0.000001) {
      setDeleteDialogError(
        `Cannot delete "${bank?.name || 'this bank'}" because its current balance is Rs. ${currentBalance.toFixed(2)}. Please bring the balance to zero and try again.`
      );

      return;
    }

    try {
      setIsDeletingBank(true);

      // Delete-specific errors belong to the dialog.
      setDeleteDialogError(null);

      // Make sure an old page-level error does not appear behind
      // the delete modal.
      setError(null);
      setSuccess(null);

      await deleteBank(deletingBankId);

      setBanks(prevBanks =>
        prevBanks.filter(
          bank =>
            String(bank.id) !== String(deletingBankId)
        )
      );

      setShowDeleteModal(false);
      setDeletingBankId(null);
      setBankBackupDownloaded(false);
      setDeleteDialogError(null);

      setSuccess('Bank deleted successfully!');
    } catch (err) {
      console.error('Error deleting bank:', err);

      const errorMessage =
        err.message ||
        'Failed to delete bank';

      // Your api.js converts the Axios error into a normal Error,
      // so err.message is the reliable value here.
      if (
        errorMessage
          .toLowerCase()
          .includes('linked savings accounts')
      ) {
        setDeleteDialogError(
          'Cannot delete bank because it has linked savings accounts. Please remove all linked savings accounts first.'
        );
      } else {
        setDeleteDialogError(errorMessage);
      }
    } finally {
      setIsDeletingBank(false);
    }
  };

  const handleEdit = (bank) => {
    setFormData({ id: bank.id, name: bank.name });
    setShowForm(true);
  };

  const handleAddTransaction = (bankId) => {
    setTransactionData(prev => ({ ...prev, bankId: bankId.toString() }));
    setShowTransactionForm(true);
  };

  const handleViewTransactions = (bankId) => {
    setError(null);
    setSelectedBankId(bankId);
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

  const handleTransactionSearchChange = (e) => {
    setTransactionSearchInput(e.target.value);
    setTransactionPage(1);
  };

  const handleTransactionTypeChange = (e) => {
    setTransactionType(e.target.value);
    setTransactionPage(1);
  };

  const handleTransactionPageChange = (page) => {
    if (page < 1 || (transactionTotalPages > 0 && page > transactionTotalPages)) {
      return;
    }
    setTransactionPage(page);
  };

  const handleTransactionPageSizeChange = (e) => {
    setTransactionPageSize(Number(e.target.value));
    setTransactionPage(1);
  };

  const resetForm = () => {
    setFormData({ id: '', name: '' });
    setShowForm(false);
  };

  // ---------- Sorting & Filtering ----------
  const handleSortClick = (column) => {
    if (sortBy === column) {
      setSortDir(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(column);
      setSortDir('asc');
    }
  };

  const visibleBanks = useMemo(() => {
    const text = (searchText || '').trim().toLowerCase();
    const filtered = (banks || []).filter(b => {
      if (!text) return true;
      return (b.name || '').toLowerCase().includes(text);
    });

    const sorted = filtered.sort((a, b) => {
      let va = a[sortBy];
      let vb = b[sortBy];

      // numeric column handling
      if (sortBy === 'balance') {
        va = safeNumber(va);
        vb = safeNumber(vb);
      } else {
        va = (va || '').toString().toLowerCase();
        vb = (vb || '').toString().toLowerCase();
      }

      if (va < vb) return sortDir === 'asc' ? -1 : 1;
      if (va > vb) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });

    return sorted;
  }, [banks, searchText, sortBy, sortDir]);

  // Totals (sum of balance for the currently visible list)
  const totals = useMemo(() => {
    return visibleBanks.reduce((acc, b) => {
      acc.balance += safeNumber(b.balance);
      return acc;
    }, { balance: 0 });
  }, [visibleBanks]);

  const bankPendingDeletion = banks.find(b => b.id === deletingBankId) || null;

  // ---------- Render ----------
  if (loading && banks.length === 0) return <div className="loading">Loading banks...</div>;

  return (
    <div className="bank-container">
      <h1>Banks</h1>

      {error && (
        <div className="bank-error-with-close">
          <span>{error}</span>
          <button type="button" className="error-dismiss" onClick={() => setError(null)} aria-label="Dismiss error">&times;</button>
        </div>
      )}

      {success && (
        <div className="success-message">
          <strong>Success:</strong> {success}
          <button type="button" onClick={() => setSuccess(null)} className="close-success">×</button>
        </div>
      )}

      <div className="bank-toolbar">
        <Button
          type="button"
          variant="primary"
          onClick={() => setShowForm(true)}
          disabled={loading}
        >
          {loading ? 'Processing...' : 'Add Bank'}
        </Button>

        <div className="bank-toolbar-search">
          <SearchBar
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="Search by name..."
            ariaLabel="Search banks by name"
            disabled={loading}
          />
        </div>
      </div>

      {/* Bank Form Modal */}
      <EntityFormDialog
        open={showForm}
        mode={formData.id ? 'edit' : 'create'}
        title={formData.id ? 'Edit Bank' : 'Add Bank'}
        onClose={resetForm}
        onSubmit={handleSubmit}
        submitting={loading}
        submitLabel={formData.id ? 'Update' : 'Save'}
      >
        <div className="form-group">
          <label htmlFor="name">
            Bank Name:
          </label>

          <input
            type="text"
            id="name"
            name="name"
            placeholder="Bank Name"
            value={formData.name}
            onChange={handleInputChange}
            required
            disabled={loading}
          />
        </div>
      </EntityFormDialog>

      {/* Transaction Form Modal */}
      <TransactionFormDialog
        open={showTransactionForm}
        title={
          <>
            Add Transaction -{' '}
            <span className="accent-text">
              {
                banks.find(
                  b =>
                    String(b.id) ===
                    String(transactionData.bankId)
                )?.name || 'Bank'
              }
            </span>
          </>
        }
        onClose={() => setShowTransactionForm(false)}
        onSubmit={handleTransactionSubmit}
        submitting={loading}
        submitLabel="Submit"
      >
        <div className="form-group">
          <label htmlFor="type">
            Transaction Type:
          </label>

          <select
            id="type"
            name="type"
            value={transactionData.type}
            onChange={handleTransactionChange}
            required
            disabled={loading}
          >
            <option value="income">Income</option>
            <option value="expense">Expense</option>
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="amount">
            Amount:
          </label>

          <input
            type="number"
            id="amount"
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
          <label htmlFor="description">
            Description:
          </label>

          <input
            type="text"
            id="description"
            name="description"
            placeholder="Description"
            value={transactionData.description}
            onChange={handleTransactionChange}
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="category">
            Category:
          </label>

          <input
            type="text"
            id="category"
            name="category"
            placeholder="Category"
            value={transactionData.category}
            onChange={handleTransactionChange}
            disabled={loading}
          />
        </div>
      </TransactionFormDialog>

      {/* Transactions Modal */}
      <TransactionTableDialog
        open={showTransactions}
        title={
          <>
            Transactions for{' '}
            {
              banks.find(
                b => b.id === selectedBankId
              )?.name || 'Bank'
            }
          </>
        }
        transactions={transactions}
        loading={transactionsLoading}
        onClose={() => setShowTransactions(false)}
        searchText={transactionSearchInput}
        onSearchChange={handleTransactionSearchChange}
        transactionType={transactionType}
        onTransactionTypeChange={handleTransactionTypeChange}
        page={transactionPage}
        totalPages={transactionTotalPages}
        totalTransactions={transactionTotal}
        pageSize={transactionPageSize}
        onPageChange={handleTransactionPageChange}
        onPageSizeChange={handleTransactionPageSizeChange}
        onAddTransaction={() =>
          handleAddTransaction(selectedBankId)
        }
        addTransactionDisabled={loading}
        columns={[
          {
            key: 'date',
            label: 'Date',
          },
          {
            key: 'transaction_type',
            label: 'Type',
            render: tx => (
              <span
                className={
                  tx.transaction_type === 'income'
                    ? 'income'
                    : 'expense'
                }
              >
                {tx.transaction_type}
              </span>
            ),
          },
          {
            key: 'amount',
            label: 'Amount',
            render: tx =>
              `Rs. ${parseFloat(tx.amount || 0).toFixed(2)}`,
          },
          {
            key: 'description',
            label: 'Description',
            render: tx =>
              tx.description || '-',
          },
          {
            key: 'category',
            label: 'Category',
            render: tx =>
              tx.category || '-',
          },
          {
            key: 'bank_balance_after',
            label: 'Balance After',
            render: tx =>
              `Rs. ${
                parseFloat(
                  tx.bank_balance_after || 0
                ).toFixed(2)
              }`,
          },
        ]}
      />

      {/* Banks Table */}
      <div className="bank-table-section">
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
              render: bank =>
                `Rs. ${safeNumber(bank.balance).toFixed(2)}`,
            },
          ]}
          data={visibleBanks}
          rowKey="id"
          loading={loading && banks.length === 0}
          emptyMessage="No banks found"
          sortBy={sortBy}
          sortDirection={sortDir}
          onSort={handleSortClick}
          renderActions={bank => (
            <>
              <Button
                type="button"
                variant="secondary"
                onClick={() => handleEdit(bank)}
                disabled={loading}
              >
                Edit
              </Button>

              <Button
                type="button"
                variant="primary"
                onClick={() =>
                  handleAddTransaction(bank.id)
                }
                disabled={loading}
              >
                Add Transaction
              </Button>

              <Button
                type="button"
                variant="secondary"
                onClick={() =>
                  handleViewTransactions(bank.id)
                }
                disabled={loading}
              >
                View Transactions
              </Button>

              <Button
                type="button"
                variant="danger"
                onClick={() =>
                  handleDeleteBank(bank.id)
                }
                disabled={
                  loading || isDeletingBank
                }
              >
                Delete
              </Button>
            </>
          )}
          renderFooter={() => (
            <tr className="totals-row">
              <td>
                Totals
              </td>

              <td>
                Rs. {totals.balance.toFixed(2)}
              </td>

              <td />
            </tr>
          )}
        />
      </div>

      {deletingBankId && (
        <DeleteConfirmationDialog
          isOpen={showDeleteModal}
          onClose={closeDeleteModal}
          onConfirm={handleConfirmDeleteBank}

          title="Delete Bank Account"

          headline={`Delete "${bankPendingDeletion?.name || 'this bank'}"?`}

          description={
            `Current balance: Rs. ${
              safeNumber(bankPendingDeletion?.balance).toFixed(2)
            }`
          }

          detailLines={[
            'This action cannot be undone.',
            'A bank account can only be deleted once its balance is zero and it has no linked savings accounts.',
            'You may download a backup of all bank transaction history before deleting this bank.'
          ]}

          isDeleting={isDeletingBank}

          confirmLabel="Delete Bank"
          confirmWithoutBackupLabel="Delete Without Backup"

          cancelLabel="Cancel"

          /* ---------------- BACKUP ---------------- */

          showBackupSection={true}

          backupSectionTitle="Backup Bank Transactions"

          onDownloadExcel={handleDownloadBankBackupExcel}
          onDownloadPdf={handleDownloadBankBackupPdf}

          isDownloading={isDownloadingBankBackup}

          backupDownloaded={bankBackupDownloaded}

          backupConfirmedMessage={
            'Bank transaction backup downloaded successfully.'
          }

          excelDownloadLabel="Download Excel"
          pdfDownloadLabel="Download PDF"

          /* ---------------- ERROR ---------------- */

          dialogError={deleteDialogError}
          onDismissDialogError={() =>
            setDeleteDialogError(null)
          }
        />
      )}
    </div>
  );
}