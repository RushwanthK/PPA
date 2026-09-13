import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { format, isValid, parse } from 'date-fns';

import {
  getCreditCards,
  createCreditCard,
  updateCreditCard,
  deleteCreditCard,
  getCreditCardTransactions,
  addCreditCardTransaction,
  processBilling,
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
import Modal from '../components/ui/Modal';

import './creditcard.css';

const getTodayInputDate = () => format(new Date(), 'yyyy-MM-dd');

const getEmptyTransactionForm = () => ({
  cardId: '',
  amount: '',
  date: getTodayInputDate(),
  description: '',
  category: '',
  isPayment: '',
});

const safeNumber = value => {
  const number = Number(value);
  return Number.isNaN(number) ? 0 : number;
};

const formatLastPaymentDate = value => {
  if (!value) return null;

  try {
    const parsed = parse(value, 'ddMMyyyy', new Date());
    return isValid(parsed) ? format(parsed, 'MMM dd, yyyy') : value;
  } catch {
    return value;
  }
};

export default function CreditCard() {
  const { user } = useAuth();

  const [cards, setCards] = useState([]);
  const [selectedCard, setSelectedCard] = useState(null);
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

  const [formData, setFormData] = useState({
    id: '',
    name: '',
    limit: '',
    billing_cycle_start: '1',
  });

  const [transactionData, setTransactionData] = useState(getEmptyTransactionForm());

  const [showForm, setShowForm] = useState(false);
  const [showTransactionForm, setShowTransactionForm] = useState(false);
  const [showCardDetails, setShowCardDetails] = useState(false);
  const [showTransactions, setShowTransactions] = useState(false);
  const [showBillingDetails, setShowBillingDetails] = useState(false);
  const [billingDetails, setBillingDetails] = useState(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [formError, setFormError] = useState(null);
  const [transactionFormError, setTransactionFormError] = useState(null);
  const [transactionTableError, setTransactionTableError] = useState(null);
  const [billingError, setBillingError] = useState(null);

  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletingCardId, setDeletingCardId] = useState(null);
  const [isDeletingCard, setIsDeletingCard] = useState(false);
  const [deleteDialogError, setDeleteDialogError] = useState(null);
  const [isDownloadingCardBackup, setIsDownloadingCardBackup] = useState(false);
  const [cardBackupDownloaded, setCardBackupDownloaded] = useState(false);

  const [searchText, setSearchText] = useState('');
  const [sortBy, setSortBy] = useState('name');
  const [sortDir, setSortDir] = useState('asc');

  useEffect(() => {
    let cancelled = false;

    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await getCreditCards();

        if (!cancelled) {
          setCards(Array.isArray(response) ? response : []);
        }
      } catch (err) {
        if (!cancelled) {
          console.error('Error fetching credit cards:', err);
          setError(err.message || 'Failed to load credit card data');
          setCards([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchData();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setTransactionSearch(transactionSearchInput.trim());
    }, 300);

    return () => window.clearTimeout(timer);
  }, [transactionSearchInput]);

  useEffect(() => {
    if (!showTransactions || !selectedCard?.id) {
      return undefined;
    }

    let cancelled = false;

    const fetchTransactions = async () => {
      try {
        setTransactionsLoading(true);
        setTransactionTableError(null);

        const response = await getCreditCardTransactions(selectedCard.id, {
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

        if (
          response?.page &&
          Number(response.page) !== transactionPage
        ) {
          setTransactionPage(Number(response.page));
        }
      } catch (err) {
        if (cancelled) return;

        console.error('Error fetching credit card transactions:', err);
        setTransactionTableError(
          err.message || 'Failed to load transactions'
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
    selectedCard?.id,
    transactionPage,
    transactionPageSize,
    transactionSearch,
    transactionType,
    transactionRefreshKey,
  ]);

  const handleInputChange = useCallback(event => {
    const { name, value } = event.target;
    setFormData(previous => ({ ...previous, [name]: value }));
  }, []);

  const handleTransactionChange = useCallback(event => {
    const { name, value } = event.target;
    setTransactionData(previous => ({ ...previous, [name]: value }));
  }, []);

  const resetForm = useCallback(() => {
    setFormData({
      id: '',
      name: '',
      limit: '',
      billing_cycle_start: '1',
    });
    setFormError(null);
    setShowForm(false);
  }, []);

  const resetTransactionForm = useCallback(() => {
    setTransactionData(getEmptyTransactionForm());
    setTransactionFormError(null);
    setShowTransactionForm(false);
  }, []);

  const updateLocalCard = useCallback(updatedCard => {
    if (!updatedCard?.id) return;

    setCards(previousCards =>
      previousCards.map(card =>
        String(card.id) === String(updatedCard.id)
          ? { ...card, ...updatedCard }
          : card
      )
    );

    setSelectedCard(previousCard => {
      if (!previousCard || String(previousCard.id) !== String(updatedCard.id)) {
        return previousCard;
      }

      return { ...previousCard, ...updatedCard };
    });
  }, []);

  const handleSubmit = useCallback(async event => {
    event.preventDefault();

    try {
      setLoading(true);
      setFormError(null);
      setSuccess(null);

      const cardData = {
        name: formData.name,
        limit: parseFloat(formData.limit),
        billing_cycle_start: parseInt(formData.billing_cycle_start, 10),
      };

      if (formData.id) {
        const existingCard = cards.find(
          card => String(card.id) === String(formData.id)
        );
        const previousBillingCycleStart = Number(
          existingCard?.billing_cycle_start
        );
        const newBillingCycleStart = Number(cardData.billing_cycle_start);
        const billingCycleChanged =
          Number.isFinite(previousBillingCycleStart) &&
          previousBillingCycleStart !== newBillingCycleStart;

        const response = await updateCreditCard(formData.id, cardData);
        const updatedCard = response?.card;

        if (!updatedCard) {
          throw new Error(
            'Credit card was updated, but the server did not return the updated card.'
          );
        }

        updateLocalCard(updatedCard);

        // Changing the billing-cycle start day requires the full billing
        // recalculation performed by the existing Process Billing endpoint.
        // Trigger it automatically only when that field actually changed.
        if (billingCycleChanged) {
          const billingResponse = await processBilling(formData.id);

          if (!billingResponse?.card) {
            throw new Error(
              'Credit card was updated, but billing could not be recalculated automatically.'
            );
          }

          updateLocalCard(billingResponse.card);
        }

        setSuccess(
          billingCycleChanged
            ? 'Credit card updated and billing recalculated successfully.'
            : 'Credit card updated successfully.'
        );
      } else {
        const response = await createCreditCard(cardData);
        const createdCard = response?.card;

        if (!createdCard) {
          throw new Error(
            'Credit card was created, but the server did not return the created card.'
          );
        }

        setCards(previousCards => [...previousCards, createdCard]);
        setSuccess('Credit card created successfully.');
      }

      resetForm();
    } catch (err) {
      console.error('Error saving credit card:', err);
      setFormError(err.message || 'Failed to save credit card');
    } finally {
      setLoading(false);
    }
  }, [cards, formData, resetForm, updateLocalCard]);

  const handleTransactionSubmit = useCallback(async event => {
    event.preventDefault();

    if (transactionData.isPayment === '') {
      setTransactionFormError(
        'Please select whether this is a Payment or Expense.'
      );
      return;
    }

    setTransactionFormError(null);

    try {
      setLoading(true);
      setSuccess(null);

      const amount = parseFloat(transactionData.amount);
      const signedAmount = transactionData.isPayment
        ? Math.abs(amount)
        : -Math.abs(amount);

      const response = await addCreditCardTransaction(
        transactionData.cardId,
        {
          amount: signedAmount,
          date: transactionData.date,
          description: transactionData.description,
          category: transactionData.category,
          is_payment: transactionData.isPayment,
        }
      );

      if (!response?.card) {
        throw new Error(
          'Transaction was added, but the server did not return the updated credit card balances.'
        );
      }

      // The transaction endpoint returns the updated balances but (for
      // backwards compatibility) may not include the card id in that nested
      // object. Supply the known id so the local row and details dialog update
      // without an additional GET request.
      updateLocalCard({
        id: transactionData.cardId,
        ...response.card,
      });

      if (
        selectedCard?.id &&
        String(selectedCard.id) === String(transactionData.cardId)
      ) {
        setTransactionPage(1);
        setTransactionRefreshKey(previous => previous + 1);
      }

      setSuccess('Transaction added successfully.');
      resetTransactionForm();
    } catch (err) {
      console.error('Error adding credit card transaction:', err);
      setTransactionFormError(err.message || 'Failed to add transaction');
    } finally {
      setLoading(false);
    }
  }, [
    resetTransactionForm,
    selectedCard?.id,
    transactionData,
    updateLocalCard,
  ]);

  const handleProcessBilling = useCallback(async cardId => {
    try {
      setLoading(true);
      setBillingError(null);
      setSuccess(null);

      const response = await processBilling(cardId);
      const card = cards.find(item => String(item.id) === String(cardId));

      if (!response?.card) {
        throw new Error(
          'Billing was processed, but the server did not return updated card balances.'
        );
      }

      const updatedCard = card
        ? { ...card, ...response.card }
        : response.card;

      updateLocalCard(updatedCard);

      setBillingDetails({
        transactionsBilled: response.transactions_billed,
        totalAmountBilled: response.total_amount_billed,
        card: updatedCard,
      });
      setShowBillingDetails(true);
      setTransactionPage(1);
      setTransactionRefreshKey(previous => previous + 1);
      setSuccess('Billing processed successfully.');
    } catch (err) {
      console.error('Error processing billing:', err);
      setBillingError(err.message || 'Failed to process billing');
    } finally {
      setLoading(false);
    }
  }, [cards, updateLocalCard]);

  const handleAddTransaction = useCallback(cardId => {
    setTransactionData(previous => ({
      ...previous,
      cardId,
      date: getTodayInputDate(),
    }));
    setTransactionFormError(null);
    setShowCardDetails(false);
    setShowTransactions(false);
    setShowTransactionForm(true);
  }, []);

  const handleEditCard = useCallback(card => {
    setFormData({
      id: card.id,
      name: card.name,
      limit: String(card.limit ?? ''),
      billing_cycle_start: String(card.billing_cycle_start ?? 1),
    });
    setSelectedCard(card);
    setShowCardDetails(false);
    setShowForm(true);
  }, []);

  const handleViewCardDetails = useCallback(card => {
    setSelectedCard(card);
    setBillingError(null);
    setShowCardDetails(true);
    setError(null);
  }, []);

  const handleViewTransactions = useCallback(card => {
    setSelectedCard(card);
    setTransactionTableError(null);
    setTransactionPage(1);
    setTransactionSearchInput('');
    setTransactionSearch('');
    setTransactionType('');
    setShowCardDetails(false);
    setShowTransactions(true);
  }, []);

  const closeCardDetails = useCallback(() => {
    setShowCardDetails(false);
  }, []);

  const closeTransactions = useCallback(() => {
    setShowTransactions(false);
    setTransactionTableError(null);
    setTransactions([]);
    setTransactionSearchInput('');
    setTransactionSearch('');
    setTransactionType('');
    setTransactionPage(1);
    setTransactionTotal(0);
    setTransactionTotalPages(0);
  }, []);

  const handleTransactionSearchChange = useCallback(event => {
    setTransactionSearchInput(event.target.value);
    setTransactionPage(1);
  }, []);

  const handleTransactionTypeChange = useCallback(event => {
    setTransactionType(event.target.value);
    setTransactionPage(1);
  }, []);

  const handleTransactionPageChange = useCallback(page => {
    if (page < 1 || (transactionTotalPages > 0 && page > transactionTotalPages)) {
      return;
    }
    setTransactionPage(page);
  }, [transactionTotalPages]);

  const handleTransactionPageSizeChange = useCallback(event => {
    setTransactionPageSize(Number(event.target.value));
    setTransactionPage(1);
  }, []);

  const handleSortClick = useCallback(columnKey => {
    if (sortBy === columnKey) {
      setSortDir(previous => (previous === 'asc' ? 'desc' : 'asc'));
      return;
    }

    setSortBy(columnKey);
    setSortDir('asc');
  }, [sortBy]);

  const handleDeleteCard = useCallback(cardId => {
    if (isDeletingCard || isDownloadingCardBackup) return;

    setError(null);
    setDeleteDialogError(null);
    setDeletingCardId(cardId);
    setCardBackupDownloaded(false);

    // The delete confirmation replaces the card-details dialog.
    setShowCardDetails(false);
    setShowDeleteModal(true);
  }, [
    isDeletingCard,
    isDownloadingCardBackup,
  ]);

  const closeDeleteModal = useCallback(() => {
    if (isDeletingCard || isDownloadingCardBackup) return;

    setShowDeleteModal(false);
    setDeletingCardId(null);
    setDeleteDialogError(null);
    setCardBackupDownloaded(false);
  }, [isDeletingCard, isDownloadingCardBackup]);

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

  const handleDownloadCardBackupExcel = useCallback(async () => {
    if (!deletingCardId || isDeletingCard || isDownloadingCardBackup) return;

    try {
      setIsDownloadingCardBackup(true);
      setDeleteDialogError(null);

      if (!user?.id) {
        throw new Error(
          'Unable to determine the current user account for backup export.'
        );
      }

      const response = await exportUserTransactionsExcel(
        user.id,
        ['credit_cards']
      );

      downloadBlob(
        response.data,
        `credit_card_transactions_backup_${getTodayInputDate()}.xlsx`
      );

      setCardBackupDownloaded(true);
    } catch (err) {
      console.error('Failed to download credit-card Excel backup:', err);
      setDeleteDialogError(
        err.message ||
        'Unable to download the Excel credit-card transaction backup. Your credit card has not been deleted.'
      );
    } finally {
      setIsDownloadingCardBackup(false);
    }
  }, [
    deletingCardId,
    downloadBlob,
    isDeletingCard,
    isDownloadingCardBackup,
    user?.id,
  ]);

  const handleDownloadCardBackupPdf = useCallback(async () => {
    if (!deletingCardId || isDeletingCard || isDownloadingCardBackup) return;

    try {
      setIsDownloadingCardBackup(true);
      setDeleteDialogError(null);

      if (!user?.id) {
        throw new Error(
          'Unable to determine the current user account for backup export.'
        );
      }

      const response = await exportUserTransactionsPdf(
        user.id,
        ['credit_cards']
      );

      downloadBlob(
        response.data,
        `credit_card_transactions_backup_${getTodayInputDate()}.pdf`
      );

      setCardBackupDownloaded(true);
    } catch (err) {
      console.error('Failed to download credit-card PDF backup:', err);
      setDeleteDialogError(
        err.message ||
        'Unable to download the PDF credit-card transaction backup. Your credit card has not been deleted.'
      );
    } finally {
      setIsDownloadingCardBackup(false);
    }
  }, [
    deletingCardId,
    downloadBlob,
    isDeletingCard,
    isDownloadingCardBackup,
    user?.id,
  ]);

  const handleConfirmDeleteCard = useCallback(async () => {
    if (!deletingCardId || isDeletingCard || isDownloadingCardBackup) return;

    const card = cards.find(item => String(item.id) === String(deletingCardId));

    try {
      setIsDeletingCard(true);
      setDeleteDialogError(null);
      setError(null);

      await deleteCreditCard(deletingCardId);

      setCards(previousCards =>
        previousCards.filter(
          item => String(item.id) !== String(deletingCardId)
        )
      );

      if (
        selectedCard?.id &&
        String(selectedCard.id) === String(deletingCardId)
      ) {
        setSelectedCard(null);
        setShowCardDetails(false);
        setShowTransactions(false);
        setTransactions([]);
      }

      setShowDeleteModal(false);
      setDeletingCardId(null);
      setCardBackupDownloaded(false);
      setDeleteDialogError(null);
      setSuccess('Credit card deleted successfully.');
    } catch (err) {
      console.error('Error deleting credit card:', err);
      setDeleteDialogError(
        err.message ||
        `Failed to delete credit card "${card?.name || ''}".`
      );
    } finally {
      setIsDeletingCard(false);
    }
  }, [
    cards,
    deletingCardId,
    isDeletingCard,
    isDownloadingCardBackup,
    selectedCard?.id,
  ]);

  const visibleCards = useMemo(() => {
    const text = searchText.trim().toLowerCase();
    const numericKeys = [
      'limit',
      'used',
      'available_limit',
      'billed_unpaid',
      'unbilled_spends',
    ];

    return cards
      .filter(card => !text || (card.name || '').toLowerCase().includes(text))
      .slice()
      .sort((a, b) => {
        let first = a[sortBy];
        let second = b[sortBy];

        if (numericKeys.includes(sortBy)) {
          first = safeNumber(first);
          second = safeNumber(second);
        } else {
          first = String(first ?? '').toLowerCase();
          second = String(second ?? '').toLowerCase();
        }

        if (first < second) return sortDir === 'asc' ? -1 : 1;
        if (first > second) return sortDir === 'asc' ? 1 : -1;
        return 0;
      });
  }, [cards, searchText, sortBy, sortDir]);

  const totals = useMemo(() => {
    return visibleCards.reduce(
      (accumulator, card) => ({
        used: accumulator.used + safeNumber(card.used),
        billed_unpaid:
          accumulator.billed_unpaid + safeNumber(card.billed_unpaid),
        unbilled_spends:
          accumulator.unbilled_spends + safeNumber(card.unbilled_spends),
      }),
      { used: 0, billed_unpaid: 0, unbilled_spends: 0 }
    );
  }, [visibleCards]);

  const deletingCard = cards.find(
    card => String(card.id) === String(deletingCardId)
  );

  const transactionCardName = cards.find(
    card => String(card.id) === String(transactionData.cardId)
  )?.name;

  if (loading && cards.length === 0) {
    return (
      <div className="credit-card-container">
        <div className="cc-loading" role="status">
          Loading credit cards...
        </div>
      </div>
    );
  }

  return (
    <div className="credit-card-container">
      <h1>Credit Cards</h1>

      {error && (
        <div className="creditcard-error-with-close" role="alert">
          <span>{error}</span>
          <button
            type="button"
            className="creditcard-error-dismiss"
            onClick={() => setError(null)}
            aria-label="Dismiss error"
          >
            ×
          </button>
        </div>
      )}

      {success && (
        <div className="creditcard-success-with-close" role="status">
          <span>{success}</span>
          <button
            type="button"
            className="creditcard-success-dismiss"
            onClick={() => setSuccess(null)}
            aria-label="Dismiss success message"
          >
            ×
          </button>
        </div>
      )}

      <div className="credit-card-toolbar">
        <Button
          type="button"
          variant="primary"
          onClick={() => {
            setFormError(null);
            setSuccess(null);
            setFormData({
              id: '',
              name: '',
              limit: '',
              billing_cycle_start: '1',
            });
            setShowForm(true);
          }}
          disabled={loading}
        >
          Add Credit Card
        </Button>

        <div className="credit-card-search">
          <SearchBar
            value={searchText}
            onChange={event => setSearchText(event.target.value)}
            placeholder="Search by name..."
            ariaLabel="Search credit cards by name"
            disabled={loading}
          />
        </div>
      </div>

      <EntityFormDialog
        open={showForm}
        mode={formData.id ? 'edit' : 'create'}
        title={formData.id ? 'Edit Credit Card' : 'Add Credit Card'}
        onClose={resetForm}
        onSubmit={handleSubmit}
        submitting={loading}
        submitLabel={formData.id ? 'Update' : 'Save'}
        error={formError}
        onDismissError={() => setFormError(null)}
      >
        <div className="form-group">
          <label htmlFor="credit-card-name">Card Name</label>
          <input
            id="credit-card-name"
            type="text"
            name="name"
            placeholder="Card Name"
            value={formData.name}
            onChange={handleInputChange}
            required
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="credit-card-limit">Credit Limit</label>
          <input
            id="credit-card-limit"
            type="number"
            step="0.01"
            min="0"
            name="limit"
            placeholder="Credit Limit"
            value={formData.limit}
            onChange={handleInputChange}
            required
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="credit-card-billing-cycle">
            Billing Cycle Start Day (1-31)
          </label>
          <input
            id="credit-card-billing-cycle"
            type="number"
            min="1"
            max="31"
            name="billing_cycle_start"
            value={formData.billing_cycle_start}
            onChange={handleInputChange}
            required
            disabled={loading}
          />
        </div>
      </EntityFormDialog>

      <TransactionFormDialog
        open={showTransactionForm}
        title={
          <>
            Add Transaction -{' '}
            <span className="creditcard-accent-text">
              {transactionCardName || 'Credit Card'}
            </span>
          </>
        }
        onClose={resetTransactionForm}
        onSubmit={handleTransactionSubmit}
        submitting={loading}
        submitLabel="Submit"
      >
        {transactionFormError && (
          <div className="creditcard-error-with-close tx-form-error" role="alert">
            <span>{transactionFormError}</span>
            <button
              type="button"
              className="creditcard-error-dismiss"
              onClick={() => setTransactionFormError(null)}
              aria-label="Dismiss transaction form error"
            >
              ×
            </button>
          </div>
        )}

        <div className="form-group">
          <label htmlFor="credit-card-transaction-amount">Amount</label>
          <input
            id="credit-card-transaction-amount"
            type="number"
            step="0.01"
            min="0.01"
            name="amount"
            placeholder="Amount"
            value={transactionData.amount}
            onChange={handleTransactionChange}
            required
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="credit-card-transaction-date">Date</label>
          <input
            id="credit-card-transaction-date"
            type="date"
            name="date"
            value={transactionData.date}
            onChange={handleTransactionChange}
            required
            disabled={loading}
          />
          <small className="creditcard-date-note">
            Enter the calendar date only. The backend applies the existing IST
            transaction-time rules.
          </small>
        </div>

        <div className="form-group">
          <label htmlFor="credit-card-transaction-description">Description</label>
          <input
            id="credit-card-transaction-description"
            type="text"
            name="description"
            placeholder="Description"
            value={transactionData.description}
            onChange={handleTransactionChange}
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="credit-card-transaction-category">Category</label>
          <input
            id="credit-card-transaction-category"
            type="text"
            name="category"
            placeholder="Category"
            value={transactionData.category}
            onChange={handleTransactionChange}
            disabled={loading}
          />
        </div>

        <div
          className={`creditcard-radio-group ${transactionFormError ? 'has-error' : ''}`}
        >
          <span className="creditcard-radio-label">Transaction Type</span>
          <div className="creditcard-radio-options">
            <label>
              <input
                type="radio"
                name="isPayment"
                value="true"
                checked={transactionData.isPayment === true}
                onChange={() => {
                  setTransactionData(previous => ({
                    ...previous,
                    isPayment: true,
                  }));
                  setTransactionFormError(null);
                }}
                disabled={loading}
              />
              Payment
            </label>

            <label>
              <input
                type="radio"
                name="isPayment"
                value="false"
                checked={
                  transactionData.isPayment === false &&
                  transactionData.isPayment !== ''
                }
                onChange={() => {
                  setTransactionData(previous => ({
                    ...previous,
                    isPayment: false,
                  }));
                  setTransactionFormError(null);
                }}
                disabled={loading}
              />
              Expense
            </label>
          </div>
        </div>
      </TransactionFormDialog>

      <DataTable
        columns={[
          { key: 'name', label: 'Name', sortable: true },
          {
            key: 'limit',
            label: 'Limit',
            sortable: true,
            render: card => safeNumber(card.limit).toFixed(2),
          },
          {
            key: 'used',
            label: 'Used',
            sortable: true,
            render: card => safeNumber(card.used).toFixed(2),
          },
          {
            key: 'available_limit',
            label: 'Available',
            sortable: true,
            render: card => safeNumber(card.available_limit).toFixed(2),
          },
          {
            key: 'billed_unpaid',
            label: 'Billed Unpaid',
            sortable: true,
            render: card => safeNumber(card.billed_unpaid).toFixed(2),
          },
          {
            key: 'unbilled_spends',
            label: 'Unbilled Spends',
            sortable: true,
            render: card => safeNumber(card.unbilled_spends).toFixed(2),
          },
        ]}
        data={visibleCards}
        rowKey="id"
        loading={loading}
        emptyMessage="No credit cards found"
        sortBy={sortBy}
        sortDirection={sortDir}
        onSort={handleSortClick}
        renderActions={card => (
          <>
            <Button
              type="button"
              variant="secondary"
              onClick={() => handleViewCardDetails(card)}
              disabled={loading}
            >
              Details
            </Button>
            <Button
              type="button"
              variant="primary"
              onClick={() => handleAddTransaction(card.id)}
              disabled={loading}
            >
              Add Tx
            </Button>
          </>
        )}
        renderFooter={() => (
          <tr className="creditcard-totals-row">
            <td>Totals</td>
            <td />
            <td>{totals.used.toFixed(2)}</td>
            <td />
            <td>{totals.billed_unpaid.toFixed(2)}</td>
            <td>{totals.unbilled_spends.toFixed(2)}</td>
            <td />
          </tr>
        )}
      />

      {deletingCardId && (
        <DeleteConfirmationDialog
          isOpen={showDeleteModal}
          onClose={closeDeleteModal}
          onConfirm={handleConfirmDeleteCard}
          title="Delete Credit Card"
          headline={`Delete "${deletingCard?.name || 'this credit card'}"?`}
          description={`Current total payable: Rs.${safeNumber(
            deletingCard?.total_payable
          ).toFixed(2)}`}
          detailLines={[
            'This action cannot be undone.',
            'Any transaction history associated with this credit card may be permanently deleted.',
            'You may download a backup of your credit card transactions before deleting the card.',
          ]}
          isDeleting={isDeletingCard}
          confirmLabel="Delete Credit Card"
          confirmWithoutBackupLabel="Delete Without Backup"
          cancelLabel="Cancel"
          showBackupSection
          backupSectionTitle="Backup Credit Card Transactions"
          onDownloadExcel={handleDownloadCardBackupExcel}
          onDownloadPdf={handleDownloadCardBackupPdf}
          isDownloading={isDownloadingCardBackup}
          backupDownloaded={cardBackupDownloaded}
          backupConfirmedMessage="Credit card transaction backup downloaded successfully."
          excelDownloadLabel="Download Excel"
          pdfDownloadLabel="Download PDF"
          dialogError={deleteDialogError}
          onDismissDialogError={() => setDeleteDialogError(null)}
        />
      )}

      <Modal
        open={showCardDetails && Boolean(selectedCard)}
        title={`Card Details: ${selectedCard?.name || ''}`}
        onClose={closeCardDetails}
        className="creditcard-details-modal"
      >
        {selectedCard && (
          <>
            {billingError && (
              <div className="creditcard-error-with-close" role="alert">
                <span>{billingError}</span>
                <button
                  type="button"
                  className="creditcard-error-dismiss"
                  onClick={() => setBillingError(null)}
                  aria-label="Dismiss billing error"
                >
                  ×
                </button>
              </div>
            )}

            <div className="creditcard-details-panel">
              <div className="creditcard-detail-row">
                <span>Limit:</span>
                <strong>Rs.{safeNumber(selectedCard.limit).toFixed(2)}</strong>
              </div>
              <div className="creditcard-detail-row">
                <span>Used:</span>
                <strong>Rs.{safeNumber(selectedCard.used).toFixed(2)}</strong>
              </div>
              <div className="creditcard-detail-row">
                <span>Available:</span>
                <strong>
                  Rs.{safeNumber(selectedCard.available_limit).toFixed(2)}
                </strong>
              </div>
              <div className="creditcard-detail-row">
                <span>Billed Unpaid:</span>
                <strong>
                  Rs.{safeNumber(selectedCard.billed_unpaid).toFixed(2)}
                </strong>
              </div>
              <div className="creditcard-detail-row">
                <span>Unbilled Spends:</span>
                <strong>
                  Rs.{safeNumber(selectedCard.unbilled_spends).toFixed(2)}
                </strong>
              </div>
              <div className="creditcard-detail-row">
                <span>Billing Cycle Start:</span>
                <strong>{selectedCard.billing_cycle_start} of month</strong>
              </div>
              <div className="creditcard-detail-row">
                <span>Total Payable:</span>
                <strong>
                  Rs.{safeNumber(selectedCard.total_payable).toFixed(2)}
                </strong>
              </div>
              {selectedCard.last_payment_date && (
                <div className="creditcard-detail-row">
                  <span>Last Payment:</span>
                  <strong>
                    Rs.{safeNumber(selectedCard.last_payment_amount).toFixed(2)}{' '}
                    on {formatLastPaymentDate(selectedCard.last_payment_date)}
                  </strong>
                </div>
              )}
            </div>

            <div className="creditcard-modal-actions">
              <Button
                type="button"
                variant="secondary"
                onClick={() => handleViewTransactions(selectedCard)}
                disabled={loading}
              >
                View Transactions
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => handleProcessBilling(selectedCard.id)}
                disabled={loading}
              >
                Process Billing
              </Button>
              <Button
                type="button"
                variant="primary"
                onClick={() => handleEditCard(selectedCard)}
                disabled={loading}
              >
                Edit Card
              </Button>
              <Button
                type="button"
                variant="danger"
                onClick={() => handleDeleteCard(selectedCard.id)}
                disabled={loading || isDeletingCard}
              >
                Delete Card
              </Button>
            </div>
          </>
        )}
      </Modal>

      <TransactionTableDialog
        open={showTransactions && Boolean(selectedCard)}

        title={
          <>
            Transactions for{' '}
            <span className="creditcard-accent-text">
              {selectedCard?.name || 'Card'}
            </span>
          </>
        }
        transactions={transactions}
        loading={transactionsLoading}
        onClose={closeTransactions}
        searchText={transactionSearchInput}
        onSearchChange={handleTransactionSearchChange}
        transactionType={transactionType}
        onTransactionTypeChange={handleTransactionTypeChange}
        transactionTypeOptions={[
          { value: 'expense', label: 'Expense' },
          { value: 'payment', label: 'Payment' },
        ]}
        page={transactionPage}
        totalPages={transactionTotalPages}
        totalTransactions={transactionTotal}
        pageSize={transactionPageSize}
        onPageChange={handleTransactionPageChange}
        onPageSizeChange={handleTransactionPageSizeChange}
        onAddTransaction={() => {
          if (selectedCard) {
            handleAddTransaction(selectedCard.id);
          }
        }}
        addTransactionDisabled={loading || !selectedCard}
        error={transactionTableError}
        onDismissError={() => setTransactionTableError(null)}
        columns={[
          {
            key: 'date',
            label: 'Date',
          },
          {
            key: 'amount',
            label: 'Amount',
            render: transaction =>
              `${transaction.amount > 0 ? '+' : ''}${safeNumber(
                transaction.amount
              ).toFixed(2)}`,
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
            key: 'transaction_type',
            label: 'Type',
            render: transaction => (
              <span className={`creditcard-transaction-${transaction.transaction_type}`}>
                {transaction.transaction_type}
              </span>
            ),
          },
          {
            key: 'is_billed',
            label: 'Billed',
            render: transaction => (transaction.is_billed ? '✓' : ''),
          },
        ]}
        emptyMessage="No transactions found."
      />

      <Modal
        open={showBillingDetails && Boolean(billingDetails)}
        title="Billing Processed Successfully"
        onClose={() => setShowBillingDetails(false)}
      >
        {billingDetails && (
          <>
            <div className="creditcard-billing-details">
              <p>
                <strong>Transactions Billed:</strong>{' '}
                {billingDetails.transactionsBilled ?? '—'}
              </p>
              <p>
                <strong>Total Amount Billed:</strong>{' '}
                {billingDetails.totalAmountBilled == null
                  ? '—'
                  : `Rs.${safeNumber(
                      billingDetails.totalAmountBilled
                    ).toFixed(2)}`}
              </p>
              <p>
                <strong>New Billed Unpaid:</strong>{' '}
                Rs.{safeNumber(
                  billingDetails.card.billed_unpaid
                ).toFixed(2)}
              </p>
              <p>
                <strong>New Unbilled Spends:</strong>{' '}
                Rs.{safeNumber(
                  billingDetails.card.unbilled_spends
                ).toFixed(2)}
              </p>
            </div>

            <div className="creditcard-modal-actions">
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setShowBillingDetails(false);
                  handleViewTransactions(billingDetails.card);
                }}
                disabled={transactionsLoading}
              >
                View Updated Transactions
              </Button>
            </div>
          </>
        )}
      </Modal>
    </div>
  );
}
