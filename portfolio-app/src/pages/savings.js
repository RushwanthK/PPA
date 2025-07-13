import React, { useEffect, useState } from 'react';
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

  // Clear error message
  const clearError = () => setError(null);

  // Fetch data on component mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [savingsResponse, banksDropdownResponse] = await Promise.all([
          getSavings(),
          getBanksByUser()
        ]);

        setSavings(savingsResponse.data || savingsResponse);
        setFilteredBanks(banksDropdownResponse.data || banksDropdownResponse);
        setLoading(false);
      } catch (error) {
        console.error('Error fetching data:', error);
        setError('Failed to fetch data. Please try again later.');
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  // Handle transaction submission
  const handleTransactionSubmit = async (e) => {
    e.preventDefault();
    try {
      const { savingId, ...transactionData } = transaction;
      await addSavingTransaction(savingId, {
        ...transactionData,
        amount: parseFloat(transactionData.amount),
      });

      // Refresh transactions for this saving
      const response = await getSavingTransactions(savingId);
      const updatedTransactions = response.data || response;
      
      setTransactions(prev => ({
        ...prev,
        [savingId]: updatedTransactions
      }));

      // Refresh savings to update balances
      const savingsResponse = await getSavings();
      setSavings(savingsResponse.data || savingsResponse);

      // Reset form
      setTransaction({ 
        savingId: '', 
        type: 'deposit', 
        amount: '', 
        description: '', 
        category: '' 
      });
      setTransactionVisible(false);
    } catch (error) {
      console.error('Transaction failed:', error);
      setError(error.response?.data?.error || error.message || 'Transaction failed');
    }
  };

  // Handle add saving submission
  const handleAddSavingSubmit = async (e) => {
    e.preventDefault();
    try {
      await createSaving({
        name: newSaving.name,
        bank_id: newSaving.bankId || null
      });

      const response = await getSavings();
      setSavings(response.data || response);
      setNewSaving({ name: '', bankId: '', balance: 0 });
      setShowAddSavingForm(false);
    } catch (error) {
      console.error('Failed to add saving:', error);
      setError(error.response?.data?.error || error.message || 'Failed to add saving');
    }
  };

  const handleUserChange = async (userId) => {
    try {
      if (userId) {
        const banksResponse = await getBanksByUser(userId);
        setFilteredBanks(banksResponse);
      } else {
        setFilteredBanks([]);
      }
    } catch (error) {
      console.error('Error fetching banks:', error);
      setFilteredBanks([]);
      setError('Failed to load banks');
    }
  };

  // Fetch transactions for a saving
  const fetchTransactions = async (savingId) => {
    try {
      const response = await getSavingTransactions(savingId);
      setTransactions(prev => ({
        ...prev,
        [savingId]: response.data || response
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

  // Toggle transactions visibility
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

  // Handle saving deletion
  const handleDeleteSaving = async (savingId) => {
    const saving = savings.find(s => s.id === savingId);
    if (!saving) {
      setError("Saving account not found in state.");
      return;
    }
  
    if (saving.balance !== 0) {
      setError("Saving account cannot be deleted because its balance is not zero.");
      return;
    }
  
    if (!window.confirm("Are you sure you want to delete this saving account?")) return;
  
    try {
      await deleteSaving(savingId);
      const updatedSavings = await getSavings();
      setSavings(updatedSavings.data || updatedSavings);
    } catch (error) {
      console.error("Failed to delete saving:", error);
      setError(error.response?.data?.error || "Failed to delete saving");
    }
  };

  const handleUpdateSaving = async (e) => {
    e.preventDefault();
    try {
      const { id, ...updateData } = editingSaving;
      
      // Check if bank is being changed and show confirmation
      const originalSaving = savings.find(s => s.id === id);
      if (updateData.bankId !== originalSaving.bank_id && originalSaving.balance > 0) {
        const confirmMessage = `This saving account has a balance of Rs.${originalSaving.balance.toFixed(2)}. ` +
          `Changing the linked bank will transfer this amount between banks. Continue?`;
        
        if (!window.confirm(confirmMessage)) {
          return;
        }
      }

      const response = await updateSaving(id, {
        name: updateData.name,
        bank_id: updateData.bankId || null
      });

      // Show success message with balance info if available
      const successMessage = response.message || 'Saving account updated successfully';
      if (response.bank_balance !== undefined) {
        setError(`${successMessage}\nNew bank balance: Rs.${response.bank_balance.toFixed(2)}`);
      } else {
        setError(successMessage);
      }
      
      // Refresh all data (banks might have changed)
      const [savingsResponse, banksResponse] = await Promise.all([
        getSavings(),
        getBanks()
      ]);
      
      setSavings(savingsResponse.data || savingsResponse);
      setBanks(banksResponse.data || banksResponse);
      
      // Reset form
      setEditingSaving(null);
    } catch (error) {
      console.error('Failed to update saving:', error);
      setError(error.response?.data?.error || error.message || 'Failed to update saving');
    }
  };

  if (loading) return <div className="savings-loading">Loading...</div>;

  return (
    <div className="savings-container">
      <h1 className="savings-header">Savings Accounts</h1>
      {error && (
        <div className="savings-error-with-close">
          <span>{error}</span>
          <button className="error-dismiss" onClick={clearError} aria-label="Dismiss error">&times;</button>
        </div>
      )}
      <button 
        className="savings-add-btn"
        onClick={() => setShowAddSavingForm(true)}
      >
        Add Savings
      </button>

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
            {/* Add balance warning if changing bank */}
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
              <th>Account Name</th>
              <th>Balance</th>
              <th>Bank</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {savings.map(saving => (
              <React.Fragment key={saving.id}>
                <tr>
                  <td>{saving.name}</td>
                  <td className={saving.balance >= 0 ? 'positive-balance' : 'negative-balance'}>
                    Rs.{saving.balance?.toFixed(2) || '0.00'}
                  </td>
                  <td>{filteredBanks.find(b => b.id === saving.bank_id)?.name || 'N/A'}</td>
                  <td className="savings-actions">
                    <button 
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
                      className="savings-action-btn savings-transaction-btn"
                      onClick={async () => {
                      setTransaction({...transaction, savingId: saving.id});
                      setTransactionVisible(true);
    
                      // Fetch bank balance if saving has a linked bank
                      if (saving.bank_id) {
                        try {
                              const balanceData = await getBankBalance(saving.bank_id);
                              setBankBalanceInfo({
                                bankName: banks.find(b => b.id === saving.bank_id)?.name || 'Linked Bank',
                                balance: balanceData.balance
                              });
                            } catch (error) {
                        console.error('Error fetching bank balance:', error);
                        setBankBalanceInfo({
                          bankName: banks.find(b => b.id === saving.bank_id)?.name || 'Linked Bank',
                          balance: null,
                          error: 'Could not fetch balance'
                        });
                        }
                      } else {
                              setBankBalanceInfo(null);
                              }
                      }}
                    >
                    Add Transaction
                    </button>
                    <button 
                      className="savings-action-btn savings-view-btn"
                      onClick={() => toggleTransactions(saving.id)}
                    >
                      {expandedSavingId === saving.id ? 'Hide Transactions' : 'View Transactions'}
                    </button>
                    <button 
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
                                  <td>Rs.{tx.amount?.toFixed(2) || '0.00'}</td>
                                  <td>{tx.description || '—'}</td>
                                  <td>Rs.{tx.saving_balance_after?.toFixed(2) || '0.00'}</td>
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
        </table>
      </div>

      {/* Transaction Form Modal */}
      {transactionVisible && (
        <div className="savings-modal">
          <div className="savings-modal-content">
            <h2>Add Transaction</h2>
            {/* Add bank balance display */}
            {bankBalanceInfo && (
              <div className="bank-balance-display">
                <p>
                  <strong>{bankBalanceInfo.bankName}</strong> Balance: 
                  {bankBalanceInfo.balance !== null ? (
                    <span className="balance-amount">
                      Rs.{bankBalanceInfo.balance.toFixed(2)}
                    </span>
                  ) : (
                    <span className="balance-error">
                      {bankBalanceInfo.error || 'N/A'}
                    </span>
                  )}
                </p>
                {transaction.type === 'withdrawal' && bankBalanceInfo.balance !== null && (
                  <p className="balance-warning">
                    Note: Withdrawals will deduct from this bank account
                  </p>
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
                <button type="button" className="savings-cancel-btn" onClick={() => setTransactionVisible(false)}>
                  Cancel
                </button>
                <button type="submit" className="savings-submit-btn">
                  Submit Transaction
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}