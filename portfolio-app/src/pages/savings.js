// src/pages/savings.js
import React, { useEffect, useState, useMemo } from 'react';
import { 
  getSavings, 
  createSaving, 
  updateSaving, 
  deleteSaving, 
  addSavingTransaction, 
  getSavingTransactions,
  getUsers,
  getBanks,
  getBanksByUser,
  getBankBalance
} from '../services/api';
import './savings.css';

export default function Savings() {
  const [savings, setSavings] = useState([]);
  const [users, setUsers] = useState([]);
  const [banks, setBanks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filteredBanks, setFilteredBanks] = useState([]);
  const [error, setError] = useState(null);
  const [bankBalanceInfo, setBankBalanceInfo] = useState(null);
  const [editingSaving, setEditingSaving] = useState(null);
  const [transactionVisible, setTransactionVisible] = useState(false);
  const [transaction, setTransaction] = useState({ 
    savingId: '', 
    type: 'deposit', 
    amount: '', 
    description: '', 
    category: '' 
  });
  const [newSaving, setNewSaving] = useState({
    name: '',
    bankId: '',
    balance: 0
  });
  const [showAddSavingForm, setShowAddSavingForm] = useState(false);
  const [expandedSavingId, setExpandedSavingId] = useState(null);
  const [transactions, setTransactions] = useState({});

  // UI for search & sort
  const [searchText, setSearchText] = useState('');
  const [sortBy, setSortBy] = useState('name'); // 'name' | 'balance' | 'bank'
  const [sortDir, setSortDir] = useState('asc'); // 'asc' | 'desc'

  // Clear error message
  const clearError = () => setError(null);

  // Safe numeric parser
  const safeNumber = (v) => {
    const n = Number(v);
    return Number.isNaN(n) ? 0 : n;
  };

  // Fetch data on component mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [savingsResponse, banksDropdownResponse] = await Promise.all([
          getSavings(),
          getBanksByUser()
        ]);

        setSavings(savingsResponse.data || savingsResponse || []);
        setFilteredBanks(banksDropdownResponse.data || banksDropdownResponse || []);
      } catch (error) {
        console.error('Error fetching data:', error);
        setError('Failed to fetch data. Please try again later.');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  // ---------- transactions ----------
  const fetchTransactions = async (savingId) => {
    try {
      const response = await getSavingTransactions(savingId);
      setTransactions(prev => ({
        ...prev,
        [savingId]: response.data || response || []
      }));
    } catch (error) {
      console.error('Error fetching transactions:', error);
      setTransactions(prev => ({
        ...prev,
        [savingId]: []
      }));
      setError('Failed to load transactions');
    }
  };

  const toggleTransactions = async (savingId) => {
    if (expandedSavingId === savingId) {
      setExpandedSavingId(null);
    } else {
      setExpandedSavingId(savingId);
      if (!transactions[savingId]) {
        await fetchTransactions(savingId);
      }
    }
  };

  // ---------- add / update / delete savings ----------
  const handleAddSavingSubmit = async (e) => {
    e.preventDefault();
    try {
      await createSaving({
        name: newSaving.name,
        bank_id: newSaving.bankId || null
      });

      const response = await getSavings();
      setSavings(response.data || response || []);
      setNewSaving({ name: '', bankId: '', balance: 0 });
      setShowAddSavingForm(false);
      setError(null);
    } catch (error) {
      console.error('Failed to add saving:', error);
      setError(error.response?.data?.error || error.message || 'Failed to add saving');
    }
  };

  const handleUpdateSaving = async (e) => {
    e.preventDefault();
    try {
      const { id, ...updateData } = editingSaving;
      
      // Check bank change
      const originalSaving = savings.find(s => s.id === id);
      if (updateData.bankId !== originalSaving?.bank_id && originalSaving && safeNumber(originalSaving.balance) > 0) {
        const confirmMessage = `This saving account has a balance of Rs.${safeNumber(originalSaving.balance).toFixed(2)}. Changing the linked bank will transfer this amount between banks. Continue?`;
        if (!window.confirm(confirmMessage)) return;
      }

      const response = await updateSaving(id, {
        name: updateData.name,
        bank_id: updateData.bankId || null
      });

      // Refresh data
      const [savingsResponse, banksResponse] = await Promise.all([getSavings(), getBanks()]);
      setSavings(savingsResponse.data || savingsResponse || []);
      setBanks(banksResponse.data || banksResponse || []);

      // Show any message returned
      if (response?.message) setError(response.message);
      editingSaving && setEditingSaving(null);
    } catch (error) {
      console.error('Failed to update saving:', error);
      setError(error.response?.data?.error || error.message || 'Failed to update saving');
    }
  };

  const handleDeleteSaving = async (savingId) => {
    const saving = savings.find(s => s.id === savingId);
    if (!saving) {
      setError("Saving account not found in state.");
      return;
    }

    if (safeNumber(saving.balance) !== 0) {
      setError("Saving account cannot be deleted because its balance is not zero.");
      return;
    }

    if (!window.confirm("Are you sure you want to delete this saving account?")) return;

    try {
      await deleteSaving(savingId);
      const updatedSavings = await getSavings();
      setSavings(updatedSavings.data || updatedSavings || []);
      setError(null);
    } catch (error) {
      console.error("Failed to delete saving:", error);
      setError(error.response?.data?.error || "Failed to delete saving");
    }
  };

  // ---------- transactions (submit) ----------
  const handleTransactionSubmit = async (e) => {
    e.preventDefault();
    try {
      const { savingId, ...transactionData } = transaction;
      await addSavingTransaction(savingId, {
        ...transactionData,
        amount: parseFloat(transactionData.amount),
      });

      // Refresh transactions & savings
      const response = await getSavingTransactions(savingId);
      const updatedTransactions = response.data || response || [];
      setTransactions(prev => ({ ...prev, [savingId]: updatedTransactions }));

      const savingsResponse = await getSavings();
      setSavings(savingsResponse.data || savingsResponse || []);

      // Reset
      setTransaction({ savingId: '', type: 'deposit', amount: '', description: '', category: '' });
      setTransactionVisible(false);
      setError(null);
    } catch (error) {
      console.error('Transaction failed:', error);
      setError(error.response?.data?.error || error.message || 'Transaction failed');
    }
  };

  // ---------- bank helpers ----------
  const handleUserChange = async (userId) => {
    try {
      if (userId) {
        const banksResponse = await getBanksByUser(userId);
        setFilteredBanks(banksResponse.data || banksResponse || []);
      } else {
        setFilteredBanks([]);
      }
    } catch (error) {
      console.error('Error fetching banks:', error);
      setFilteredBanks([]);
      setError('Failed to load banks');
    }
  };

  const handleAddTransactionClick = async (saving) => {
    setTransaction(prev => ({ ...prev, savingId: saving.id }));
    setTransactionVisible(true);

    if (saving.bank_id) {
      try {
        const balanceData = await getBankBalance(saving.bank_id);
        setBankBalanceInfo({
          bankName: (filteredBanks.find(b => b.id === saving.bank_id) || banks.find(b => b.id === saving.bank_id) || {}).name || 'Linked Bank',
          balance: balanceData.balance
        });
      } catch (error) {
        console.error('Error fetching bank balance:', error);
        setBankBalanceInfo({
          bankName: (filteredBanks.find(b => b.id === saving.bank_id) || banks.find(b => b.id === saving.bank_id) || {}).name || 'Linked Bank',
          balance: null,
          error: 'Could not fetch balance'
        });
      }
    } else {
      setBankBalanceInfo(null);
    }
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

  const visibleSavings = useMemo(() => {
    const text = (searchText || '').trim().toLowerCase();
    const filtered = (savings || []).filter(s => {
      if (!text) return true;
      return (s.name || '').toLowerCase().includes(text);
    });

    const sorted = filtered.sort((a, b) => {
      let va, vb;
      if (sortBy === 'balance') {
        va = safeNumber(a.balance);
        vb = safeNumber(b.balance);
      } else if (sortBy === 'bank') {
        va = (filteredBanks.find(x => x.id === a.bank_id)?.name || '').toLowerCase();
        vb = (filteredBanks.find(x => x.id === b.bank_id)?.name || '').toLowerCase();
      } else {
        // default name
        va = (a.name || '').toLowerCase();
        vb = (b.name || '').toLowerCase();
      }

      if (va < vb) return sortDir === 'asc' ? -1 : 1;
      if (va > vb) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });

    return sorted;
  }, [savings, searchText, sortBy, sortDir, filteredBanks]);

  // Totals reflect visibleSavings (Option A)
  const totals = useMemo(() => {
    return visibleSavings.reduce((acc, s) => {
      acc.balance += safeNumber(s.balance);
      return acc;
    }, { balance: 0 });
  }, [visibleSavings]);

  if (loading) return <div className="savings-loading">Loading...</div>;

  return (
    <div className="savings-container">
      <h1 className="savings-header">Savings Accounts</h1>

      {error && (
        <div className="savings-error-with-close">
          <span>{error}</span>
          <button type="button" className="error-dismiss" onClick={clearError} aria-label="Dismiss error">&times;</button>
        </div>
      )}

      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <button
          type="button"
          className="savings-add-btn"
          onClick={() => setShowAddSavingForm(true)}
        >
          Add Savings
        </button>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            type="text"
            placeholder="Search by account name..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ padding: '8px 10px', borderRadius: 4, border: '1px solid #444', background: '#2d2d2d', color: '#fff' }}
            aria-label="Search savings by name"
          />
        </div>
      </div>

      {/* Add Saving Form Modal */}
      {showAddSavingForm && (
        <div className="savings-modal">
          <div className="savings-modal-content">
            <h2>Create New Savings Account</h2>
            <form onSubmit={handleAddSavingSubmit}>
              <div className="savings-form-group">
                <label>Account Name</label>
                <input
                  type="text"
                  value={newSaving.name}
                  onChange={(e) => setNewSaving({ ...newSaving, name: e.target.value })}
                  required
                />
              </div>

              <div className="savings-form-group">
                <label>Bank (Optional)</label>
                <select
                  value={newSaving.bankId}
                  onChange={(e) => setNewSaving({ ...newSaving, bankId: e.target.value })}
                >
                  <option value="">Select Bank</option>
                  {filteredBanks.map(bank => (
                    <option key={bank.id} value={bank.id}>{bank.name}</option>
                  ))}
                </select>
              </div>

              <div className="savings-modal-actions">
                <button type="submit" className="savings-submit-btn">Create</button>
                <button type="button" className="savings-cancel-btn" onClick={() => setShowAddSavingForm(false)}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Update Saving Form Modal */}
      {editingSaving && (
        <div className="savings-modal">
          <div className="savings-modal-content">
            <h2>Update Savings Account</h2>

            {editingSaving.bankId !== savings.find(s => s.id === editingSaving.id)?.bank_id && 
            savings.find(s => s.id === editingSaving.id)?.balance > 0 && (
              <div className="bank-change-warning">
                <p>
                  <strong>Warning:</strong> This account has a balance of Rs.
                  {savings.find(s => s.id === editingSaving.id)?.balance.toFixed(2)}.
                  Changing the linked bank will transfer this amount between banks.
                </p>
              </div>
            )}

            <form onSubmit={handleUpdateSaving}>
              <div className="savings-form-group">
                <label>Account Name</label>
                <input
                  type="text"
                  value={editingSaving.name}
                  onChange={(e) => setEditingSaving({...editingSaving, name: e.target.value})}
                  required
                />
              </div>
              
              <div className="savings-form-group">
                <label>Bank (Optional)</label>
                <select
                  value={editingSaving.bankId}
                  onChange={(e) => setEditingSaving({ ...editingSaving, bankId: e.target.value })}
                >
                  <option value="">Select Bank</option>
                  {filteredBanks.map(bank => (
                    <option key={bank.id} value={bank.id}>{bank.name}</option>
                  ))}
                </select>
              </div>
              
              <div className="savings-modal-actions">
                <button type="button" className="savings-cancel-btn" onClick={() => setEditingSaving(null)}>
                  Cancel
                </button>
                <button type="submit" className="savings-submit-btn">
                  Update Account
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Savings Accounts Table */}
      <div className="savings-table-container">
        <table className="savings-table">
          <thead>
            <tr>
              <th className="sortable" onClick={() => handleSortClick('name')}>
                Account Name {sortBy === 'name' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
              </th>
              <th className="sortable" onClick={() => handleSortClick('balance')}>
                Balance {sortBy === 'balance' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
              </th>
              <th className="sortable" onClick={() => handleSortClick('bank')}>
                Bank {sortBy === 'bank' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
              </th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {visibleSavings.map(saving => (
              <React.Fragment key={saving.id}>
                <tr>
                  <td>{saving.name}</td>
                  <td className={safeNumber(saving.balance) >= 0 ? 'positive-balance' : 'negative-balance'}>
                    Rs.{safeNumber(saving.balance).toFixed(2)}
                  </td>
                  <td>{filteredBanks.find(b => b.id === saving.bank_id)?.name || 'N/A'}</td>
                  <td className="savings-actions">
                    <button
                      type="button"
                      className="savings-action-btn savings-edit-btn"
                      onClick={() => setEditingSaving({
                        id: saving.id,
                        name: saving.name,
                        bankId: saving.bank_id
                      })}
                    >
                      Update
                    </button>
                    <button
                      type="button"
                      className="savings-action-btn savings-transaction-btn"
                      onClick={() => handleAddTransactionClick(saving)}
                    >
                      Add Transaction
                    </button>
                    <button
                      type="button"
                      className="savings-action-btn savings-view-btn"
                      onClick={() => toggleTransactions(saving.id)}
                    >
                      {expandedSavingId === saving.id ? 'Hide Transactions' : 'View Transactions'}
                    </button>
                    <button
                      type="button"
                      className="savings-action-btn savings-delete-btn"
                      onClick={() => handleDeleteSaving(saving.id)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>

                {expandedSavingId === saving.id && (
                  <tr className="transactions-row">
                    <td colSpan="5">
                      <div className="transactions-container">
                        <h3>Transaction History</h3>
                        {transactions[saving.id]?.length > 0 ? (
                          <table className="transactions-table">
                            <thead>
                              <tr>
                                <th>Date</th>
                                <th>Type</th>
                                <th>Amount</th>
                                <th>Description</th>
                                <th>Balance After</th>
                              </tr>
                            </thead>
                            <tbody>
                              {transactions[saving.id].map(tx => (
                                <tr key={tx.id}>
                                  <td>{tx.date ? new Date(tx.date).toLocaleString() : 'N/A'}</td>
                                  <td className={`tx-type-${tx.transaction_type}`}>
                                    {tx.transaction_type || 'N/A'}
                                  </td>
                                  <td>Rs.{safeNumber(tx.amount).toFixed(2)}</td>
                                  <td>{tx.description || '—'}</td>
                                  <td>Rs.{safeNumber(tx.saving_balance_after).toFixed(2)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        ) : (
                          <p className="no-transactions">No transactions found for this account.</p>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>

          <tfoot>
            <tr className="totals-row">
              <td style={{ fontWeight: 600 }}>Totals</td>
              <td style={{ fontWeight: 600 }}>Rs.{totals.balance.toFixed(2)}</td>
              <td></td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Transaction Form Modal */}
      {transactionVisible && (
        <div className="savings-modal">
          <div className="savings-modal-content">
            <h2>Add Transaction</h2>
            {bankBalanceInfo && (
              <div className="bank-balance-display">
                <p>
                  <strong>{bankBalanceInfo.bankName}</strong> Balance: 
                  {bankBalanceInfo.balance !== null ? (
                    <span className="balance-amount">Rs.{bankBalanceInfo.balance.toFixed(2)}</span>
                  ) : (
                    <span className="balance-error">{bankBalanceInfo.error || 'N/A'}</span>
                  )}
                </p>
                {transaction.type === 'withdrawal' && bankBalanceInfo.balance !== null && (
                  <p className="balance-warning">Note: Withdrawals will deduct from this bank account</p>
                )}
              </div>
            )}

            <form onSubmit={handleTransactionSubmit}>
              <div className="savings-form-group">
                <label>Transaction Type</label>
                <select
                  value={transaction.type}
                  onChange={(e) => setTransaction({...transaction, type: e.target.value})}
                  required
                >
                  <option value="deposit">Deposit</option>
                  <option value="withdrawal">Withdrawal</option>
                </select>
              </div>
              
              <div className="savings-form-group">
                <label>Amount</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={transaction.amount}
                  onChange={(e) => setTransaction({...transaction, amount: e.target.value})}
                  required
                />
              </div>
              
              <div className="savings-form-group">
                <label>Description (Optional)</label>
                <input
                  type="text"
                  value={transaction.description}
                  onChange={(e) => setTransaction({...transaction, description: e.target.value})}
                />
              </div>
              
              <div className="savings-form-group">
                <label>Category (Optional)</label>
                <input
                  type="text"
                  value={transaction.category}
                  onChange={(e) => setTransaction({...transaction, category: e.target.value})}
                />
              </div>
              
              <div className="savings-modal-actions">
                <button type="button" className="savings-cancel-btn" onClick={() => setTransactionVisible(false)}>Cancel</button>
                <button type="submit" className="savings-submit-btn">Submit Transaction</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
