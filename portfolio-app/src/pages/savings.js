import React, { useEffect, useMemo, useState } from 'react';

import {
  getSavings,
  createSaving,
  updateSaving,
  deleteSaving,
  addSavingTransaction,
  getSavingTransactions,
  getBanksByUser,
  getBankBalance,
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

import './savings.css';

export default function Savings() {
  const { user } = useAuth();

  const [savings, setSavings] = useState([]);
  const [banks, setBanks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [formError, setFormError] = useState(null);
  const [transactionFormError, setTransactionFormError] = useState(null);
  const [transactionTableError, setTransactionTableError] = useState(null);

  const [formData, setFormData] = useState({
    id: '',
    name: '',
    bankId: '',
  });

  const [transactionData, setTransactionData] = useState({
    savingId: '',
    type: 'deposit',
    amount: '',
    description: '',
    category: '',
  });

  const [bankBalanceInfo, setBankBalanceInfo] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [showTransactionForm, setShowTransactionForm] = useState(false);

  // Server-paginated transaction history state.
  const [selectedSavingId, setSelectedSavingId] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [showTransactions, setShowTransactions] = useState(false);
  const [transactionPage, setTransactionPage] = useState(1);
  const [transactionPageSize, setTransactionPageSize] = useState(25);
  const [transactionSearchInput, setTransactionSearchInput] = useState('');
  const [transactionSearch, setTransactionSearch] = useState('');
  const [transactionType, setTransactionType] = useState('');
  const [transactionTotal, setTransactionTotal] = useState(0);
  const [transactionTotalPages, setTransactionTotalPages] = useState(0);
  const [transactionsLoading, setTransactionsLoading] = useState(false);
  const [transactionRefreshKey, setTransactionRefreshKey] = useState(0);

  // Delete-confirmation dialog state.
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletingSavingId, setDeletingSavingId] = useState(null);
  const [isDeletingSaving, setIsDeletingSaving] = useState(false);
  const [deleteDialogError, setDeleteDialogError] = useState(null);
  const [isDownloadingSavingBackup, setIsDownloadingSavingBackup] = useState(false);
  const [savingBackupDownloaded, setSavingBackupDownloaded] = useState(false);

  // Main-table search & sorting.
  const [searchText, setSearchText] = useState('');
  const [sortBy, setSortBy] = useState('name');
  const [sortDir, setSortDir] = useState('asc');

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);

        const [savingsResponse, banksResponse] = await Promise.all([
          getSavings(),
          getBanksByUser(),
        ]);

        setSavings(Array.isArray(savingsResponse) ? savingsResponse : []);
        setBanks(Array.isArray(banksResponse) ? banksResponse : []);
      } catch (err) {
        console.error('Error fetching savings data:', err);
        setError(err.message || 'Failed to fetch savings data');
        setSavings([]);
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

  // Fetch only the currently visible transaction page from the server.
  useEffect(() => {
    if (!showTransactions || !selectedSavingId) {
      return undefined;
    }

    let cancelled = false;

    const fetchTransactions = async () => {
      try {
        setTransactionsLoading(true);
        setTransactionTableError(null);

        const response = await getSavingTransactions(
          selectedSavingId,
          {
            page: transactionPage,
            page_size: transactionPageSize,
            search: transactionSearch,
            type: transactionType,
          }
        );

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

        console.error('Error fetching saving transactions:', err);
        setTransactionTableError(
          err.message || 'Failed to fetch saving transactions'
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
    selectedSavingId,
    transactionPage,
    transactionPageSize,
    transactionSearch,
    transactionType,
    transactionRefreshKey,
  ]);

  const safeNumber = value => {
    const number = Number(value);
    return Number.isNaN(number) ? 0 : number;
  };

  const getBankName = bankId => (
    banks.find(bank => String(bank.id) === String(bankId))?.name || 'N/A'
  );

  const resetForm = () => {
    setFormData({
      id: '',
      name: '',
      bankId: '',
    });
    setFormError(null);
    setShowForm(false);
  };

  const handleInputChange = event => {
    const { name, value } = event.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleTransactionChange = event => {
    const { name, value } = event.target;
    setTransactionData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async event => {
    event.preventDefault();

    try {
      setFormError(null);
      setLoading(true);

      const name = formData.name.trim();
      if (!name) {
        throw new Error('Please enter a savings account name');
      }

      const bankId = Number(formData.bankId);
      if (!Number.isInteger(bankId) || bankId <= 0) {
        throw new Error('Please select a bank');
      }

      if (formData.id) {
        const originalSaving = savings.find(
          saving => String(saving.id) === String(formData.id)
        );

        if (!originalSaving) {
          throw new Error('Saving account not found in state');
        }

        if (
          bankId !== Number(originalSaving.bank_id) &&
          safeNumber(originalSaving.balance) > 0
        ) {
          const confirmMessage =
            `This saving account has a balance of Rs. ${safeNumber(
              originalSaving.balance
            ).toFixed(2)}. Changing the linked bank will transfer this amount between banks. Continue?`;

          if (!window.confirm(confirmMessage)) {
            return;
          }
        }

        const response = await updateSaving(formData.id, {
          name,
          bank_id: bankId,
        });

        const updatedSaving = response?.saving;
        if (!updatedSaving) {
          throw new Error(
            'Saving account was updated, but no saving data was returned'
          );
        }

        setSavings(prevSavings =>
          prevSavings.map(saving =>
            String(saving.id) === String(updatedSaving.id)
              ? {
                  ...saving,
                  ...updatedSaving,
                  bank_name: getBankName(updatedSaving.bank_id),
                }
              : saving
          )
        );
      } else {
        const response = await createSaving({
          name,
          bank_id: bankId,
        });

        const createdSaving = response?.saving;
        if (!createdSaving) {
          throw new Error(
            'Saving account was created, but no saving data was returned'
          );
        }

        setSavings(prevSavings => [
          ...prevSavings,
          {
            ...createdSaving,
            bank_name: getBankName(createdSaving.bank_id),
          },
        ]);
      }

      resetForm();
    } catch (err) {
      console.error('Error saving savings account:', err);
      setFormError(err.message || 'Failed to save savings account');
    } finally {
      setLoading(false);
    }
  };

  const handleAddTransaction = async saving => {
    setTransactionFormError(null);
    setTransactionData(prev => ({
      ...prev,
      savingId: String(saving.id),
    }));
    setBankBalanceInfo(null);
    setShowTransactionForm(true);

    if (!saving.bank_id) {
      return;
    }

    try {
      const balanceData = await getBankBalance(saving.bank_id);
      setBankBalanceInfo({
        bankName: getBankName(saving.bank_id),
        balance: balanceData?.balance ?? null,
      });
    } catch (err) {
      console.error('Error fetching bank balance:', err);
      setBankBalanceInfo({
        bankName: getBankName(saving.bank_id),
        balance: null,
        error: err.message || 'Could not fetch balance',
      });
    }
  };

  const handleTransactionSubmit = async event => {
    event.preventDefault();

    try {
      setTransactionFormError(null);
      setLoading(true);

      if (!transactionData.savingId) {
        throw new Error('Saving account not selected for transaction');
      }

      if (!transactionData.amount || Number.isNaN(Number(transactionData.amount))) {
        throw new Error('Please enter a valid amount');
      }

      const amount = parseFloat(transactionData.amount);
      if (amount <= 0) {
        throw new Error('Amount must be greater than 0');
      }

      const response = await addSavingTransaction(
        transactionData.savingId,
        {
          amount,
          type: transactionData.type,
          description: transactionData.description,
          category: transactionData.category,
        }
      );

      const newBalance = response?.saving_balance;
      if (newBalance === undefined) {
        throw new Error(
          'Transaction was added, but the server did not return the updated savings balance'
        );
      }

      setSavings(prevSavings =>
        prevSavings.map(saving =>
          String(saving.id) === String(transactionData.savingId)
            ? { ...saving, balance: newBalance }
            : saving
        )
      );

      if (
        selectedSavingId &&
        String(selectedSavingId) === String(transactionData.savingId)
      ) {
        setTransactionPage(1);
        setTransactionRefreshKey(prev => prev + 1);
      }

      setTransactionData({
        savingId: '',
        type: 'deposit',
        amount: '',
        description: '',
        category: '',
      });
      setBankBalanceInfo(null);
      setShowTransactionForm(false);
    } catch (err) {
      console.error('Error adding saving transaction:', err);
      setTransactionFormError(
        err.message || 'Failed to add saving transaction'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleViewTransactions = savingId => {
    setTransactionTableError(null);
    setSelectedSavingId(savingId);
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

  const handleTransactionSearchChange = event => {
    setTransactionSearchInput(event.target.value);
    setTransactionPage(1);
  };

  const handleTransactionTypeChange = event => {
    setTransactionType(event.target.value);
    setTransactionPage(1);
  };

  const handleTransactionPageChange = page => {
    if (
      page < 1 ||
      (transactionTotalPages > 0 && page > transactionTotalPages)
    ) {
      return;
    }

    setTransactionPage(page);
  };

  const handleTransactionPageSizeChange = event => {
    setTransactionPageSize(Number(event.target.value));
    setTransactionPage(1);
  };

  const handleDeleteSaving = savingId => {
    if (isDeletingSaving || isDownloadingSavingBackup) {
      return;
    }

    const saving = savings.find(
      item => String(item.id) === String(savingId)
    );

    setError(null);

    if (!saving) {
      setDeletingSavingId(savingId);
      setDeleteDialogError('Saving account not found in state.');
      setSavingBackupDownloaded(false);
      setShowDeleteModal(true);
      return;
    }

    const balance = safeNumber(saving.balance);

    setDeleteDialogError(
      balance !== 0
        ? `Saving account "${saving.name}" cannot be deleted because its current balance is Rs. ${balance.toFixed(2)}. Please bring the balance to zero and try again.`
        : null
    );

    setDeletingSavingId(savingId);
    setSavingBackupDownloaded(false);
    setShowDeleteModal(true);
  };

  const closeDeleteModal = () => {
    if (isDeletingSaving || isDownloadingSavingBackup) {
      return;
    }

    setShowDeleteModal(false);
    setDeletingSavingId(null);
    setDeleteDialogError(null);
    setSavingBackupDownloaded(false);
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

  const handleDownloadSavingBackupExcel = async () => {
    if (!deletingSavingId || isDeletingSaving || isDownloadingSavingBackup) {
      return;
    }

    try {
      setIsDownloadingSavingBackup(true);
      setDeleteDialogError(null);

      if (!user?.id) {
        throw new Error(
          'Unable to determine the current user account for backup export.'
        );
      }

      const response = await exportUserTransactionsExcel(
        user.id,
        ['savings']
      );

      const filename =
        `savings_transactions_backup_${new Date()
          .toISOString()
          .slice(0, 10)}.xlsx`;

      downloadBlob(response.data, filename);
      setSavingBackupDownloaded(true);
    } catch (err) {
      console.error('Failed to download savings Excel backup:', err);
      setDeleteDialogError(
        err.message ||
        'Unable to download the Excel savings transaction backup. Your savings account has not been deleted.'
      );
    } finally {
      setIsDownloadingSavingBackup(false);
    }
  };

  const handleDownloadSavingBackupPdf = async () => {
    if (!deletingSavingId || isDeletingSaving || isDownloadingSavingBackup) {
      return;
    }

    try {
      setIsDownloadingSavingBackup(true);
      setDeleteDialogError(null);

      if (!user?.id) {
        throw new Error(
          'Unable to determine the current user account for backup export.'
        );
      }

      const response = await exportUserTransactionsPdf(
        user.id,
        ['savings']
      );

      const filename =
        `savings_transactions_backup_${new Date()
          .toISOString()
          .slice(0, 10)}.pdf`;

      downloadBlob(response.data, filename);
      setSavingBackupDownloaded(true);
    } catch (err) {
      console.error('Failed to download savings PDF backup:', err);
      setDeleteDialogError(
        err.message ||
        'Unable to download the PDF savings transaction backup. Your savings account has not been deleted.'
      );
    } finally {
      setIsDownloadingSavingBackup(false);
    }
  };

  const handleConfirmDeleteSaving = async () => {
    if (!deletingSavingId || isDeletingSaving || isDownloadingSavingBackup) {
      return;
    }

    const saving = savings.find(
      item => String(item.id) === String(deletingSavingId)
    );

    if (!saving) {
      setDeleteDialogError('Saving account not found in state.');
      return;
    }

    const balance = safeNumber(saving.balance);

    if (balance !== 0) {
      setDeleteDialogError(
        `Saving account "${saving.name}" cannot be deleted because its current balance is Rs. ${balance.toFixed(2)}. Please bring the balance to zero and try again.`
      );
      return;
    }

    try {
      setIsDeletingSaving(true);
      setDeleteDialogError(null);
      setError(null);

      await deleteSaving(deletingSavingId);

      setSavings(prevSavings =>
        prevSavings.filter(
          item => String(item.id) !== String(deletingSavingId)
        )
      );

      if (String(selectedSavingId) === String(deletingSavingId)) {
        setSelectedSavingId(null);
        setShowTransactions(false);
        setTransactions([]);
        setTransactionTotal(0);
        setTransactionTotalPages(0);
      }

      setShowDeleteModal(false);
      setDeletingSavingId(null);
      setSavingBackupDownloaded(false);
      setDeleteDialogError(null);
    } catch (err) {
      console.error('Failed to delete savings account:', err);
      setDeleteDialogError(
        err.message ||
        `Failed to delete savings account "${saving.name}".`
      );
    } finally {
      setIsDeletingSaving(false);
    }
  };

  const handleSortClick = column => {
    if (sortBy === column) {
      setSortDir(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(column);
      setSortDir('asc');
    }
  };

  const visibleSavings = useMemo(() => {
    const text = (searchText || '').trim().toLowerCase();

    const getBankNameForSort = bankId => (
      banks.find(bank => String(bank.id) === String(bankId))?.name || 'N/A'
    );

    const filtered = (savings || []).filter(saving => {
      if (!text) return true;
      return (saving.name || '').toLowerCase().includes(text);
    });

    return [...filtered].sort((a, b) => {
      let valueA;
      let valueB;

      if (sortBy === 'balance') {
        valueA = safeNumber(a.balance);
        valueB = safeNumber(b.balance);
      } else if (sortBy === 'bank') {
        valueA = getBankNameForSort(a.bank_id).toLowerCase();
        valueB = getBankNameForSort(b.bank_id).toLowerCase();
      } else {
        valueA = (a.name || '').toLowerCase();
        valueB = (b.name || '').toLowerCase();
      }

      if (valueA < valueB) return sortDir === 'asc' ? -1 : 1;
      if (valueA > valueB) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
  }, [savings, searchText, sortBy, sortDir, banks]);

  const totals = useMemo(
    () =>
      visibleSavings.reduce(
        (total, saving) => total + safeNumber(saving.balance),
        0
      ),
    [visibleSavings]
  );

  const selectedSaving = savings.find(
    saving => String(saving.id) === String(selectedSavingId)
  );
  const savingPendingDeletion = savings.find(
    saving => String(saving.id) === String(deletingSavingId)
  );

  if (loading && savings.length === 0) {
    return <div className="savings-loading">Loading savings accounts...</div>;
  }

  return (
    <div className="savings-container">
      <h1>Savings Accounts</h1>

      {error && (
        <div className="savings-error-with-close">
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

      <div className="savings-toolbar">
        <Button
          type="button"
          variant="primary"
          onClick={() => {
            setFormError(null);
            setShowForm(true);
          }}
          disabled={loading}
        >
          {loading ? 'Processing...' : 'Add Savings'}
        </Button>

        <div className="savings-toolbar-search">
          <SearchBar
            value={searchText}
            onChange={event => setSearchText(event.target.value)}
            placeholder="Search by account name..."
            ariaLabel="Search savings accounts by name"
            disabled={loading}
          />
        </div>
      </div>

      <EntityFormDialog
        open={showForm}
        mode={formData.id ? 'edit' : 'create'}
        title={formData.id ? 'Edit Savings Account' : 'Add Savings Account'}
        onClose={resetForm}
        onSubmit={handleSubmit}
        submitting={loading}
        submitLabel={formData.id ? 'Update' : 'Save'}
        error={formError}
        onDismissError={() => setFormError(null)}
      >
        {formData.id && (() => {
          const originalSaving = savings.find(
            saving => String(saving.id) === String(formData.id)
          );
          const isChangingBank =
            originalSaving &&
            Number(formData.bankId) !== Number(originalSaving.bank_id);

          if (!isChangingBank || safeNumber(originalSaving?.balance) <= 0) {
            return null;
          }

          return (
            <div className="bank-change-warning">
              <p>
                <strong>Warning:</strong> This account has a balance of Rs.{' '}
                {safeNumber(originalSaving.balance).toFixed(2)}. Changing the
                linked bank will transfer this amount between banks.
              </p>
            </div>
          );
        })()}

        <div className="form-group">
          <label htmlFor="savings-name">Account Name:</label>
          <input
            id="savings-name"
            name="name"
            type="text"
            placeholder="Account name"
            value={formData.name}
            onChange={handleInputChange}
            required
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="savings-bank">Bank:</label>
          <select
            id="savings-bank"
            name="bankId"
            value={formData.bankId}
            onChange={handleInputChange}
            required
            disabled={loading}
          >
            <option value="" disabled>
              Select Bank
            </option>
            {banks.map(bank => (
              <option key={bank.id} value={bank.id}>
                {bank.name}
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
              {savings.find(
                saving =>
                  String(saving.id) === String(transactionData.savingId)
              )?.name || 'Savings Account'}
            </span>
          </>
        }
        onClose={() => {
          if (loading) return;
          setShowTransactionForm(false);
          setTransactionFormError(null);
          setBankBalanceInfo(null);
        }}
        onSubmit={handleTransactionSubmit}
        submitting={loading}
        submitLabel="Submit"
        error={transactionFormError}
        onDismissError={() => setTransactionFormError(null)}
      >
        {bankBalanceInfo && (
          <div className="bank-balance-display">
            <p>
              <strong>{bankBalanceInfo.bankName}</strong> Balance:{' '}
              {bankBalanceInfo.balance !== null ? (
                <span className="balance-amount">
                  Rs. {safeNumber(bankBalanceInfo.balance).toFixed(2)}
                </span>
              ) : (
                <span className="balance-error">
                  {bankBalanceInfo.error || 'N/A'}
                </span>
              )}
            </p>
            {transactionData.type === 'withdrawal' &&
              bankBalanceInfo.balance !== null && (
                <p className="balance-warning">
                  Note: Withdrawals will add the amount back to this bank account.
                </p>
              )}
            {transactionData.type === 'deposit' &&
              bankBalanceInfo.balance !== null && (
                <p className="balance-warning">
                  Note: Deposits will deduct the amount from this bank account.
                </p>
              )}
          </div>
        )}

        <div className="form-group">
          <label htmlFor="saving-transaction-type">Transaction Type:</label>
          <select
            id="saving-transaction-type"
            name="type"
            value={transactionData.type}
            onChange={handleTransactionChange}
            required
            disabled={loading}
          >
            <option value="deposit">Deposit</option>
            <option value="withdrawal">Withdrawal</option>
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="saving-transaction-amount">Amount:</label>
          <input
            id="saving-transaction-amount"
            name="amount"
            type="number"
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
          <label htmlFor="saving-transaction-description">
            Description:
          </label>
          <input
            id="saving-transaction-description"
            name="description"
            type="text"
            placeholder="Description"
            value={transactionData.description}
            onChange={handleTransactionChange}
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="saving-transaction-category">Category:</label>
          <input
            id="saving-transaction-category"
            name="category"
            type="text"
            placeholder="Category"
            value={transactionData.category}
            onChange={handleTransactionChange}
            disabled={loading}
          />
        </div>
      </TransactionFormDialog>

      <TransactionTableDialog
        open={showTransactions}
        title={
          <>
            Transactions for{' '}
            <span className="accent-text">
              {selectedSaving?.name || 'Savings Account'}
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
          { value: 'withdrawal', label: 'Withdrawal' },
        ]}
        page={transactionPage}
        totalPages={transactionTotalPages}
        totalTransactions={transactionTotal}
        pageSize={transactionPageSize}
        onPageChange={handleTransactionPageChange}
        onPageSizeChange={handleTransactionPageSizeChange}
        onAddTransaction={() => {
          if (selectedSaving) {
            handleAddTransaction(selectedSaving);
          }
        }}
        addTransactionDisabled={loading || !selectedSaving}
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
              <span
                className={`transaction-${transaction.transaction_type}`}
              >
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
          {
            key: 'category',
            label: 'Category',
            render: transaction => transaction.category || '-',
          },
          {
            key: 'saving_balance_after',
            label: 'Balance After',
            render: transaction =>
              `Rs. ${safeNumber(
                transaction.saving_balance_after
              ).toFixed(2)}`,
          },
        ]}
        emptyMessage="No transactions found."
      />

      <div className="savings-table-section">
        <DataTable
          columns={[
            {
              key: 'name',
              label: 'Account Name',
              sortable: true,
            },
            {
              key: 'balance',
              label: 'Balance',
              sortable: true,
              render: saving =>
                `Rs. ${safeNumber(saving.balance).toFixed(2)}`,
            },
            {
              key: 'bank',
              label: 'Bank',
              sortable: true,
              render: saving => getBankName(saving.bank_id),
            },
          ]}
          data={visibleSavings}
          rowKey="id"
          loading={loading && savings.length === 0}
          emptyMessage="No savings accounts found"
          sortBy={sortBy}
          sortDirection={sortDir}
          onSort={handleSortClick}
          renderActions={saving => (
            <>
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setFormData({
                    id: saving.id,
                    name: saving.name,
                    bankId: String(saving.bank_id),
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
                onClick={() => handleAddTransaction(saving)}
                disabled={loading}
              >
                Add Transaction
              </Button>

              <Button
                type="button"
                variant="secondary"
                onClick={() => handleViewTransactions(saving.id)}
                disabled={loading}
              >
                View Transactions
              </Button>

              <Button
                type="button"
                variant="danger"
                onClick={() => handleDeleteSaving(saving.id)}
                disabled={loading || isDeletingSaving}
              >
                Delete
              </Button>
            </>
          )}
          renderFooter={() => (
            <tr className="totals-row">
              <td>Totals</td>
              <td>Rs. {totals.toFixed(2)}</td>
              <td />
              <td />
            </tr>
          )}
        />
      </div>

      {deletingSavingId && (
        <DeleteConfirmationDialog
          isOpen={showDeleteModal}
          onClose={closeDeleteModal}
          onConfirm={handleConfirmDeleteSaving}
          title="Delete Savings Account"
          headline={`Delete "${
            savingPendingDeletion?.name || 'this savings account'
          }"?`}
          description={`Current balance: Rs. ${safeNumber(
            savingPendingDeletion?.balance
          ).toFixed(2)}`}
          detailLines={[
            'This action cannot be undone.',
            'A savings account can only be deleted when its balance is zero.',
            'You may download a backup of the savings transaction history before deleting the account.',
          ]}
          isDeleting={isDeletingSaving}
          confirmLabel="Delete Savings Account"
          confirmWithoutBackupLabel="Delete Without Backup"
          cancelLabel="Cancel"
          showBackupSection
          backupSectionTitle="Backup Savings Transactions"
          onDownloadExcel={handleDownloadSavingBackupExcel}
          onDownloadPdf={handleDownloadSavingBackupPdf}
          isDownloading={isDownloadingSavingBackup}
          backupDownloaded={savingBackupDownloaded}
          backupConfirmedMessage="Savings transaction backup downloaded successfully."
          excelDownloadLabel="Download Excel"
          pdfDownloadLabel="Download PDF"
          dialogError={deleteDialogError}
          onDismissDialogError={() => setDeleteDialogError(null)}
        />
      )}
    </div>
  );
}
