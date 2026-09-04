// src/pages/creditcard.js
import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { 
  getCreditCards, 
  createCreditCard, 
  getCreditCard,
  updateCreditCard,
  deleteCreditCard,
  getCreditCardTransactions,
  addCreditCardTransaction,
  processBilling,
  getUsers,
  exportUserTransactionsExcel,
  exportUserTransactionsPdf
} from '../services/api';
import './creditcard.css';
import DeleteConfirmationDialog from '../components/Deleteconfirmationdialog';
import { format, parse } from 'date-fns';

export default function CreditCard() {
  const [cards, setCards] = useState([]);
  const [selectedCard, setSelectedCard] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [billingDetails, setBillingDetails] = useState(null);
  const [showBillingDetails, setShowBillingDetails] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    limit: '',
    billing_cycle_start: '1'
  });
  const [transactionData, setTransactionData] = useState({
    cardId: '',
    amount: '',
    date: format(new Date(), 'yyyy-MM-dd'),
    description: '',
    category: '',
    isPayment: ''
  });
  const [showForm, setShowForm] = useState(false);
  const [showTransactionForm, setShowTransactionForm] = useState(false);
  const [showCardDetails, setShowCardDetails] = useState(false);
  const [showTransactions, setShowTransactions] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editMode, setEditMode] = useState(false);
  // Credit-card delete dialog state
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletingCardId, setDeletingCardId] = useState(null);
  const [isDeletingCard, setIsDeletingCard] = useState(false);

  // Errors specifically belonging to the delete dialog.
  // These must not appear behind/below the dialog.
  const [deleteDialogError, setDeleteDialogError] = useState(null);

  // Error specifically belonging to the "Add Transaction" form (e.g. no
  // Payment/Expense type selected). Kept separate from the page-level
  // `error` banner so it shows right next to the field that needs
  // attention instead of behind the modal.
  const [transactionFormError, setTransactionFormError] = useState(null);

  // Backup/download state.
  const [isDownloadingCardBackup, setIsDownloadingCardBackup] = useState(false);
  const [cardBackupDownloaded, setCardBackupDownloaded] = useState(false);

  // Sorting / filtering state
  const [searchText, setSearchText] = useState('');
  const [sortBy, setSortBy] = useState('name');
  const [sortDir, setSortDir] = useState('asc');

  // Guards against setState calls after this page has been navigated
  // away from while a request (card list, card details, transactions,
  // billing, backup export, delete) is still in flight. Important on a
  // financial page where several of these actions are async and the
  // user may click through quickly.
  const isMounted = useRef(true);
  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
    };
  }, []);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const cardsResponse = await getCreditCards();
        if (isMounted.current) {
          setCards(cardsResponse || []);
          setError(null);
        }
      } catch (err) {
        console.error('Error fetching data:', err);
        if (isMounted.current) {
          setError('Failed to load credit card data');
          setCards([]);
        }
      } finally {
        if (isMounted.current) setLoading(false);
      }
    };

    fetchData();
  }, []);

  // API + UI handlers (kept behavior from your original code)
  const fetchCardDetails = useCallback(async (cardId) => {
    try {
      setLoading(true);
      const card = await getCreditCard(cardId);
      if (isMounted.current) {
        setSelectedCard(card);
        setShowCardDetails(true);
        setError(null);
      }
    } catch (err) {
      console.error('Error fetching card details:', err);
      if (isMounted.current) setError('Failed to load card details');
    } finally {
      if (isMounted.current) setLoading(false);
    }
  }, []);

  const fetchTransactions = useCallback(async (cardId) => {
    try {
      setLoading(true);
      const txs = await getCreditCardTransactions(cardId);
      if (isMounted.current) {
        setTransactions(txs);
        setShowTransactions(true);
        setError(null);
      }
    } catch (err) {
      console.error('Error fetching transactions:', err);
      if (isMounted.current) setError('Failed to load transactions');
    } finally {
      if (isMounted.current) setLoading(false);
    }
  }, []);

  const handleInputChange = useCallback((e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  }, []);

  const handleTransactionChange = useCallback((e) => {
    const { name, value, type, checked } = e.target;
    setTransactionData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  }, []);

  const handleSubmit = useCallback(async (e) => {
    e.preventDefault();
    try {
      setLoading(true);
      const cardData = {
        name: formData.name,
        limit: parseFloat(formData.limit),
        billing_cycle_start: parseInt(formData.billing_cycle_start)
      };

      if (editMode && selectedCard) {
        const response = await updateCreditCard(selectedCard.id, cardData);
        const updatedCards = await getCreditCards();
        if (isMounted.current) {
          setCards(updatedCards);
          setSelectedCard(response.card || selectedCard);
          setEditMode(false);
        }
      } else {
        await createCreditCard(cardData);
        const updatedCards = await getCreditCards();
        if (isMounted.current) setCards(updatedCards);
      }

      if (isMounted.current) resetForm();
    } catch (error) {
      console.error('Error saving card:', error);
      if (isMounted.current) setError(error.message || 'Failed to save credit card');
    } finally {
      if (isMounted.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formData, editMode, selectedCard]);

  const handleTransactionSubmit = useCallback(async (e) => {
    e.preventDefault();

    if (transactionData.isPayment === '') {
      setTransactionFormError('Please select whether this is a Payment or Expense.');
      return;
    }

    setTransactionFormError(null);

    try {
      setLoading(true);

      await addCreditCardTransaction(transactionData.cardId, {
        amount: parseFloat(transactionData.isPayment ? 
          Math.abs(transactionData.amount) : 
          -Math.abs(transactionData.amount)),
        date: transactionData.date,
        description: transactionData.description,
        category: transactionData.category,
        is_payment: transactionData.isPayment
      });

      // Refresh
      const updatedCards = await getCreditCards();

      if (isMounted.current) {
        setCards(updatedCards);

        if (selectedCard) {
          const refreshedCard = updatedCards.find(c => c.id === selectedCard.id);
          setSelectedCard(refreshedCard || null);
        }

        resetTransactionForm();
      }
    } catch (error) {
      console.error('Error adding transaction:', error);
      if (isMounted.current) setTransactionFormError(error.message || 'Failed to add transaction');
    } finally {
      if (isMounted.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [transactionData, selectedCard]);

  const handleProcessBilling = useCallback(async (cardId) => {
    try {
      setLoading(true);
      const response = await processBilling(cardId);
      const updatedCard = await getCreditCard(cardId);

      if (isMounted.current) {
        setCards(prevCards =>
          prevCards.map(card =>
            card.id === cardId ? updatedCard : card
          )
        );

        setBillingDetails({
          transactionsBilled: response.transactions_billed,
          totalAmountBilled: response.total_amount_billed,
          card: updatedCard
        });

        setSelectedCard(updatedCard);
        setShowBillingDetails(true);
        setError(null);
      }
    } catch (err) {
      console.error('Error processing billing:', err);
      if (isMounted.current) setError('Failed to process billing');
    } finally {
      if (isMounted.current) setLoading(false);
    }
  }, []);

  const handleDeleteCard = useCallback((cardId) => {
    if (isDeletingCard || isDownloadingCardBackup) {
      return;
    }

    // Clear normal page errors. Delete-specific errors belong
    // inside the confirmation dialog.
    setError(null);

    setDeleteDialogError(null);
    setDeletingCardId(cardId);
    setCardBackupDownloaded(false);
    setShowDeleteModal(true);
  }, [isDeletingCard, isDownloadingCardBackup]);

  const closeDeleteModal = useCallback(() => {
    if (isDeletingCard || isDownloadingCardBackup) {
      return;
    }

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

  const getCurrentUserIdForBackup = useCallback(async () => {
    const usersResponse = await getUsers();

    const users = Array.isArray(usersResponse)
      ? usersResponse
      : (
          Array.isArray(usersResponse?.data)
            ? usersResponse.data
            : []
        );

    const userId = users[0]?.id;

    if (!userId) {
      throw new Error(
        'Unable to determine the current user account for backup export.'
      );
    }

    return userId;
  }, []);

  const handleDownloadCardBackupExcel = useCallback(async () => {
    if (
      !deletingCardId ||
      isDeletingCard ||
      isDownloadingCardBackup
    ) {
      return;
    }

    try {
      setIsDownloadingCardBackup(true);
      setDeleteDialogError(null);

      const userId = await getCurrentUserIdForBackup();

      // Reuse the existing user transaction export API.
      // "credit_cards" means only credit-card transactions.
      const response = await exportUserTransactionsExcel(
        userId,
        ['credit_cards']
      );

      const filename =
        `credit_card_transactions_backup_${new Date()
          .toISOString()
          .slice(0, 10)}.xlsx`;

      downloadBlob(response.data, filename);

      if (isMounted.current) setCardBackupDownloaded(true);
    } catch (err) {
      console.error(
        'Failed to download credit-card Excel backup:',
        err
      );

      if (isMounted.current) {
        setDeleteDialogError(
          err.message ||
          'Unable to download the Excel credit-card transaction backup. Your credit card has not been deleted.'
        );
      }
    } finally {
      if (isMounted.current) setIsDownloadingCardBackup(false);
    }
  }, [deletingCardId, isDeletingCard, isDownloadingCardBackup, getCurrentUserIdForBackup, downloadBlob]);

  const handleDownloadCardBackupPdf = useCallback(async () => {
    if (
      !deletingCardId ||
      isDeletingCard ||
      isDownloadingCardBackup
    ) {
      return;
    }

    try {
      setIsDownloadingCardBackup(true);
      setDeleteDialogError(null);

      const userId = await getCurrentUserIdForBackup();

      const response = await exportUserTransactionsPdf(
        userId,
        ['credit_cards']
      );

      const filename =
        `credit_card_transactions_backup_${new Date()
          .toISOString()
          .slice(0, 10)}.pdf`;

      downloadBlob(response.data, filename);

      if (isMounted.current) setCardBackupDownloaded(true);
    } catch (err) {
      console.error(
        'Failed to download credit-card PDF backup:',
        err
      );

      if (isMounted.current) {
        setDeleteDialogError(
          err.message ||
          'Unable to download the PDF credit-card transaction backup. Your credit card has not been deleted.'
        );
      }
    } finally {
      if (isMounted.current) setIsDownloadingCardBackup(false);
    }
  }, [deletingCardId, isDeletingCard, isDownloadingCardBackup, getCurrentUserIdForBackup, downloadBlob]);

  const handleConfirmDeleteCard = useCallback(async () => {
    if (
      !deletingCardId ||
      isDeletingCard ||
      isDownloadingCardBackup
    ) {
      return;
    }

    const card = cards.find(
      c => String(c.id) === String(deletingCardId)
    );

    try {
      setIsDeletingCard(true);
      setDeleteDialogError(null);
      setError(null);

      await deleteCreditCard(deletingCardId);

      const updatedCards = await getCreditCards();

      if (isMounted.current) {
        setCards(updatedCards);

        // Keep the existing behavior after deletion.
        setSelectedCard(null);
        setShowCardDetails(false);

        setShowDeleteModal(false);
        setDeletingCardId(null);
        setCardBackupDownloaded(false);
        setDeleteDialogError(null);

        setError(null);
      }
    } catch (err) {
      console.error('Error deleting credit card:', err);

      // IMPORTANT:
      // Keep this error inside the dialog.
      // Do not use setError() here.
      if (isMounted.current) {
        setDeleteDialogError(
          err.message ||
          `Failed to delete credit card "${card?.name || ''}".`
        );
      }
    } finally {
      if (isMounted.current) setIsDeletingCard(false);
    }
  }, [deletingCardId, isDeletingCard, isDownloadingCardBackup, cards]);

  const handleAddTransaction = useCallback((cardId) => {
    setTransactionData(prev => ({ 
      ...prev, 
      cardId,
      date: format(new Date(), 'yyyy-MM-dd')
    }));
    setTransactionFormError(null);
    setShowCardDetails(false);
    setShowTransactions(false);
    setShowTransactionForm(true);
  }, []);

  const handleEditCard = useCallback((card) => {
    setFormData({
      name: card.name,
      limit: card.limit.toString(),
      billing_cycle_start: card.billing_cycle_start.toString()
    });

    setSelectedCard(card);
    setEditMode(true);
    setShowForm(true);
    setShowCardDetails(false);
  }, []);

  const resetForm = useCallback(() => {
    setFormData({
      name: '',
      limit: '',
      billing_cycle_start: '1'
    });
    setShowForm(false);
    setEditMode(false);
    setSelectedCard(null);
  }, []);

  const resetTransactionForm = useCallback(() => {
    setTransactionData({
      cardId: '',
      amount: '',
      date: format(new Date(), 'yyyy-MM-dd'),
      description: '',
      category: '',
      isPayment: ''
    });
    setTransactionFormError(null);
    setShowTransactionForm(false);
  }, []);

  const closeCardDetails = useCallback(() => {
    setShowCardDetails(false);
    setSelectedCard(null);
  }, []);

  const closeTransactions = useCallback(() => {
    setShowTransactions(false);
    setTransactions([]);
  }, []);

  // Sorting/filter helpers
  const handleSortClick = useCallback((columnKey) => {
    if (sortBy === columnKey) {
      setSortDir(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(columnKey);
      setSortDir('asc');
    }
  }, [sortBy]);

  const safeNumber = useCallback((val) => {
    const n = Number(val);
    return Number.isNaN(n) ? 0 : n;
  }, []);

  const visibleCards = useMemo(() => {
    const text = (searchText || '').trim().toLowerCase();
    const filtered = (cards || []).filter(c => {
      if (!text) return true;
      return (c.name || '').toLowerCase().includes(text);
    });

    const numericKeys = ['limit', 'used', 'available_limit', 'billed_unpaid', 'unbilled_spends'];
    const sorted = filtered.sort((a, b) => {
      let va = a[sortBy];
      let vb = b[sortBy];

      if (numericKeys.includes(sortBy)) {
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
  }, [cards, searchText, sortBy, sortDir, safeNumber]);

  const totals = useMemo(() => {
    const t = visibleCards.reduce((acc, c) => {
      acc.used += safeNumber(c.used);
      acc.billed_unpaid += safeNumber(c.billed_unpaid);
      acc.unbilled_spends += safeNumber(c.unbilled_spends);
      return acc;
    }, { used: 0, billed_unpaid: 0, unbilled_spends: 0 });
    return t;
  }, [visibleCards, safeNumber]);

  if (loading) {
    return (
      <div className="credit-card-container">
        <div className="loading">
          <div className="cc-loading-spinner" />
          Loading credit cards...
        </div>
      </div>
    );
  }

  return (
    <div className="credit-card-container">
      <h1>Credit Cards</h1>
      {error && (
        <div className="creditcard-error-with-close">
          <span>{error}</span>
          <button type="button" className="error-dismiss" onClick={() => setError(null)} aria-label="Dismiss error">&times;</button>
        </div>
      )}

      <div className="actions">
        <button type="button" className="primary" onClick={() => setShowForm(true)}>Add Credit Card</button>

        <div className="search-wrap">
          <input
            type="text"
            className="search-input"
            placeholder="Search by name..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
          />
        </div>
      </div>

      {/* ADD / EDIT CREDIT CARD FORM (restored) */}
      {showForm && (
        <div className="modal">
          <div className="modal-content">
            <h2>{editMode ? 'Edit Credit Card' : 'Add Credit Card'}</h2>
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label>Card Name</label>
                <input
                  type="text"
                  name="name"
                  placeholder="Card Name"
                  value={formData.name}
                  onChange={handleInputChange}
                  required
                />
              </div>

              <div className="form-group">
                <label>Credit Limit</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  name="limit"
                  placeholder="Credit Limit"
                  value={formData.limit}
                  onChange={handleInputChange}
                  required
                />
              </div>

              <div className="form-group">
                <label>Billing Cycle Start Day (1-31)</label>
                <input
                  type="number"
                  min="1"
                  max="31"
                  name="billing_cycle_start"
                  value={formData.billing_cycle_start}
                  onChange={handleInputChange}
                  required
                />
              </div>

              <div className="form-actions">
                <button type="submit" className="primary">
                  {editMode ? 'Update' : 'Save'}
                </button>
                <button type="button" className="danger" onClick={resetForm}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* TRANSACTION FORM (restored) */}
      {showTransactionForm && (
        <div className="modal">
          <div className="modal-content">
            <h2>Add Transaction - <span className="tx-card-name">{cards.find(c => c.id === transactionData.cardId)?.name || 'Credit Card'}</span></h2>

            {transactionFormError && (
              <div className="creditcard-error-with-close tx-form-error">
                <span>{transactionFormError}</span>
                <button type="button" className="error-dismiss" onClick={() => setTransactionFormError(null)} aria-label="Dismiss error">&times;</button>
              </div>
            )}

            <form onSubmit={handleTransactionSubmit}>
              <div className="form-group">
                <label>Amount</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  name="amount"
                  placeholder="Amount"
                  value={transactionData.amount}
                  onChange={handleTransactionChange}
                  required
                />
              </div>

              <div className="form-group">
                <label>Date</label>
                <input
                  type="date"
                  name="date"
                  value={transactionData.date}
                  onChange={handleTransactionChange}
                  required
                />
              </div>

              <div className="form-group">
                <label>Description</label>
                <input
                  type="text"
                  name="description"
                  placeholder="Description"
                  value={transactionData.description}
                  onChange={handleTransactionChange}
                />
              </div>

              <div className="form-group">
                <label>Category</label>
                <input
                  type="text"
                  name="category"
                  placeholder="Category"
                  value={transactionData.category}
                  onChange={handleTransactionChange}
                />
              </div>

              <div className={`form-group radio-group ${transactionFormError ? 'has-error' : ''}`}>
                <label>Transaction Type</label>
                <div className="radio-options">
                  <label>
                    <input
                      type="radio"
                      name="isPayment"
                      value="true"
                      checked={transactionData.isPayment === true}
                      onChange={() => { setTransactionData(prev => ({ ...prev, isPayment: true })); setTransactionFormError(null); }}
                    />
                    Payment
                  </label>
                  <label>
                    <input
                      type="radio"
                      name="isPayment"
                      value="false"
                      checked={transactionData.isPayment === false && transactionData.isPayment !== ''}
                      onChange={() => { setTransactionData(prev => ({ ...prev, isPayment: false })); setTransactionFormError(null); }}
                    />
                    Expense
                  </label>
                </div>
              </div>

              <div className="form-actions">
                <button type="submit" className="primary">Submit</button>
                <button type="button" className="danger" onClick={resetTransactionForm}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Credit Cards Table */}
      <div className="cards-table">
        <div className="cards-table-scroll">
        <table>
          <thead>
            <tr>
              <th className="sortable" onClick={() => handleSortClick('name')}>
                Name {sortBy === 'name' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
              </th>
              <th className="sortable" onClick={() => handleSortClick('limit')}>
                Limit {sortBy === 'limit' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
              </th>
              <th className="sortable" onClick={() => handleSortClick('used')}>
                Used {sortBy === 'used' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
              </th>
              <th className="sortable" onClick={() => handleSortClick('available_limit')}>
                Available {sortBy === 'available_limit' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
              </th>
              <th className="sortable" onClick={() => handleSortClick('billed_unpaid')}>
                Billed Unpaid {sortBy === 'billed_unpaid' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
              </th>
              <th className="sortable" onClick={() => handleSortClick('unbilled_spends')}>
                Unbilled Spends {sortBy === 'unbilled_spends' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
              </th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {visibleCards && visibleCards.length > 0 ? (
              visibleCards.map(card => (
                <tr key={card.id}>
                  <td>{card.name}</td>
                  <td>{safeNumber(card.limit).toFixed(2)}</td>
                  <td>{safeNumber(card.used).toFixed(2)}</td>
                  <td>{safeNumber(card.available_limit).toFixed(2)}</td>
                  <td>{safeNumber(card.billed_unpaid).toFixed(2)}</td>
                  <td>{safeNumber(card.unbilled_spends).toFixed(2)}</td>
                  <td className="actions-cell">
                    <button type="button"
                      onClick={() => fetchCardDetails(card.id)}
                      className="info"
                    >
                      Details
                    </button>
                    <button type="button"
                      onClick={() => handleAddTransaction(card.id)}
                      className="primary"
                    >
                      Add Tx
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="7">No credit cards found</td>
              </tr>
            )}
          </tbody>

          <tfoot>
            <tr className="totals-row">
              <td>Totals</td>
              <td></td>
              <td>{totals.used.toFixed(2)}</td>
              <td></td>
              <td>{totals.billed_unpaid.toFixed(2)}</td>
              <td>{totals.unbilled_spends.toFixed(2)}</td>
              <td></td>
            </tr>
          </tfoot>
        </table>
        </div>
      </div>

      {/* Credit Card Delete Confirmation Dialog */}
      {deletingCardId && (
        <DeleteConfirmationDialog
          isOpen={showDeleteModal}
          onClose={closeDeleteModal}
          onConfirm={handleConfirmDeleteCard}

          title="Delete Credit Card"

          headline={`Delete "${
            cards.find(c => String(c.id) === String(deletingCardId))?.name
            || 'this credit card'
          }"?`}

          description={`Current total payable: Rs.${
            safeNumber(
              cards.find(
                c => String(c.id) === String(deletingCardId)
              )?.total_payable
            ).toFixed(2)
          }`}

          detailLines={[
            'This action cannot be undone.',
            'Any transaction history associated with this credit card may be permanently deleted.',
            'You may download a backup of your credit card transactions before deleting the card.'
          ]}

          isDeleting={isDeletingCard}

          confirmLabel="Delete Credit Card"
          confirmWithoutBackupLabel="Delete Without Backup"

          cancelLabel="Cancel"

          /* Backup */
          showBackupSection={true}
          backupSectionTitle="Backup Credit Card Transactions"

          onDownloadExcel={handleDownloadCardBackupExcel}
          onDownloadPdf={handleDownloadCardBackupPdf}

          isDownloading={isDownloadingCardBackup}
          backupDownloaded={cardBackupDownloaded}

          backupConfirmedMessage={
            'Credit card transaction backup downloaded successfully.'
          }

          excelDownloadLabel="Download Excel"
          pdfDownloadLabel="Download PDF"

          /* Error */
          dialogError={deleteDialogError}
          onDismissDialogError={() => setDeleteDialogError(null)}
        />
      )}

      {/* Card Details Modal */}
      {showCardDetails && selectedCard && (
        <div className="modal">
          <div className="modal-content large">
            <div className="modal-header">
              <h2>Card Details: {selectedCard.name}</h2>
              <button type="button" onClick={closeCardDetails} className="close-button">&times;</button>
            </div>

            <div className="card-details">
              <div className="detail-row">
                <span className="detail-label">Limit:</span>
                <span>Rs.{selectedCard.limit?.toFixed(2)}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Used:</span>
                <span>Rs.{selectedCard.used?.toFixed(2)}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Available:</span>
                <span>Rs.{selectedCard.available_limit?.toFixed(2)}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Billed Unpaid:</span>
                <span>Rs.{selectedCard.billed_unpaid?.toFixed(2)}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Unbilled Spends:</span>
                <span>Rs.{selectedCard.unbilled_spends?.toFixed(2)}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Billing Cycle Start:</span>
                <span>{selectedCard.billing_cycle_start} of month</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Total Payable:</span>
                <span>Rs.{selectedCard.total_payable?.toFixed(2)}</span>
              </div>
              {selectedCard.last_payment_date && (
                <div className="detail-row">
                  <span className="detail-label">Last Payment:</span>
                  <span>
                    Rs.{selectedCard.last_payment_amount?.toFixed(2)} on{' '}
                    {format(
                      parse(selectedCard.last_payment_date, 'ddMMyyyy', new Date()),
                      'MMM dd, yyyy'
                    )}
                  </span>
                </div>
              )}
            </div>

            <div className="modal-actions">
              <button type="button"
                onClick={() => fetchTransactions(selectedCard.id)}
                className="info"
              >
                View Transactions
              </button>
              <button type="button"
                onClick={() => handleProcessBilling(selectedCard.id)}
                className="secondary"
              >
                Process Billing
              </button>
              <button type="button"
                onClick={() => handleEditCard(selectedCard)}
                className="primary"
              >
                Edit Card
              </button>
              <button type="button"
                onClick={() => handleDeleteCard(selectedCard.id)}
                className="danger"
              >
                Delete Card
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Transactions Modal */}
      {showTransactions && (
        <div className="modal">
          <div className="modal-content x-large">
            <div className="modal-header">
              <h2>Transactions for {selectedCard?.name || 'Card'}</h2>
              <div className="transaction-header-actions"><button type="button" onClick={() => handleAddTransaction(selectedCard.id)} className="primary">Add Transaction</button>
                <button type="button" onClick={closeTransactions} className="close-button">&times;</button>
              </div>
            </div>

            <div className="transactions-table">
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Amount</th>
                    <th>Description</th>
                    <th>Category</th>
                    <th>Type</th>
                    <th>Billed</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions && transactions.length > 0 ? (
                    transactions.map(tx => (
                      <tr key={tx.id} className={tx.is_payment ? 'payment' : 'expense'}>
                        <td>{tx.date}</td>
                        <td>{tx.amount > 0 ? '+' : ''}{tx.amount?.toFixed(2)}</td>
                        <td>{tx.description}</td>
                        <td>{tx.category}</td>
                        <td>{tx.transaction_type}</td>
                        <td>{tx.is_billed ? '✓' : ''}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="6">No transactions found</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            
          </div>
        </div>
      )}

      {/* Billing modal */}
      {showBillingDetails && billingDetails && (
        <div className="modal">
          <div className="modal-content">
            <div className="modal-header">
              <h2>Billing Processed Successfully</h2>
              <button type="button" onClick={() => setShowBillingDetails(false)} className="close-button">&times;</button>
            </div>

            <div className="billing-details">
              <p><strong>Transactions Billed:</strong> {billingDetails.transactionsBilled}</p>
              <p><strong>Total Amount Billed:</strong> Rs.{billingDetails.totalAmountBilled?.toFixed(2)}</p>
              <p><strong>New Billed Unpaid:</strong> Rs.{billingDetails.card.billed_unpaid?.toFixed(2)}</p>
              <p><strong>New Unbilled Spends:</strong> Rs.{billingDetails.card.unbilled_spends?.toFixed(2)}</p>
            </div>

            <div className="modal-actions">
              <button type="button"
                onClick={() => {
                  setShowBillingDetails(false);
                  fetchTransactions(billingDetails.card.id);
                }}
                className="info"
              >
                View Updated Transactions
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}