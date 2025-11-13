// src/pages/bank.js
import React, { useState, useEffect, useMemo } from 'react';
import {
  getBanks,
  createBank,
  updateBank,
  deleteBank,
  addBankTransaction,
  getBankTransactions
} from '../services/api';
import './bank.css';

export default function Bank() {
  const [banks, setBanks] = useState([]);
  const [transactions, setTransactions] = useState([]);
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

      if (!formData.name) throw new Error('Please enter a bank name');

      if (formData.id) {
        const updatedBank = await updateBank(formData.id, { name: formData.name });
        // refresh list (safer to re-fetch)
        const banksResponse = await getBanks();
        setBanks(banksResponse.data || banksResponse || []);
        setSuccess('Bank updated successfully!');
      } else {
        await createBank({ name: formData.name });
        const banksResponse = await getBanks();
        setBanks(banksResponse.data || banksResponse || []);
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

      if (!transactionData.amount || isNaN(transactionData.amount)) throw new Error('Please enter a valid amount');
      if (parseFloat(transactionData.amount) <= 0) throw new Error('Amount must be greater than 0');

      await addBankTransaction(transactionData.bankId, {
        amount: parseFloat(transactionData.amount),
        type: transactionData.type,
        description: transactionData.description,
        category: transactionData.category
      });

      // Refresh banks to reflect updated balance
      const banksResponse = await getBanks();
      setBanks(banksResponse.data || banksResponse || []);
      setSuccess('Transaction added successfully!');

      // Reset and close transaction form
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
      setError(err.message || 'Failed to add transaction');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteBank = async (bankId) => {
    if (!window.confirm('Are you sure you want to delete this bank?')) return;
    try {
      setError(null);
      setSuccess(null);
      setLoading(true);
      await deleteBank(bankId);
      const banksResponse = await getBanks();
      setBanks(banksResponse.data || banksResponse || []);
      setSuccess('Bank deleted successfully!');
    } catch (err) {
      console.error('Error deleting bank:', err);
      // customized error message (as you had)
      if (err.response?.data?.error?.includes('linked savings accounts')) {
        setError('Cannot delete bank because it has linked savings accounts. Please remove all linked savings accounts first.');
      } else {
        setError(err.message || 'Failed to delete bank');
      }
    } finally {
      setLoading(false);
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

  const handleViewTransactions = async (bankId) => {
    try {
      setError(null);
      setLoading(true);
      const response = await getBankTransactions(bankId);
      const txs = response?.data || response || [];
      setTransactions(txs);
      setSelectedBankId(bankId);
      setShowTransactions(true);
    } catch (err) {
      console.error('Error fetching transactions:', err);
      setError(err.message || 'Failed to fetch transactions');
    } finally {
      setLoading(false);
    }
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

      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <button
          type="button"
          onClick={() => setShowForm(true)}
          className="add-button"
          disabled={loading}
        >
          {loading ? 'Processing...' : 'Add Bank'}
        </button>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            type="text"
            placeholder="Search by name..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ padding: '8px 10px', borderRadius: 4, border: '1px solid #444', background: '#2d2d2d', color: '#fff' }}
            aria-label="Search banks by name"
          />
        </div>
      </div>

      {/* Bank Form Modal */}
      {showForm && (
        <div className="modal">
          <div className="modal-content">
            <h2>{formData.id ? 'Edit' : 'Add'} Bank</h2>
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label htmlFor="name">Bank Name:</label>
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

              <div className="form-actions">
                <button type="submit" className="save-button" disabled={loading}>
                  {loading ? 'Saving...' : 'Save'}
                </button>
                <button type="button" onClick={resetForm} className="cancel-button" disabled={loading}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Transaction Form Modal */}
      {showTransactionForm && (
        <div className="modal">
          <div className="modal-content">
            <h2>Add Transaction</h2>
            <form onSubmit={handleTransactionSubmit}>
              <div className="form-group">
                <label htmlFor="type">Transaction Type:</label>
                <select id="type" name="type" value={transactionData.type} onChange={handleTransactionChange} required disabled={loading}>
                  <option value="income">Income</option>
                  <option value="expense">Expense</option>
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="amount">Amount:</label>
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
                <label htmlFor="description">Description:</label>
                <input type="text" id="description" name="description" placeholder="Description" value={transactionData.description} onChange={handleTransactionChange} disabled={loading} />
              </div>

              <div className="form-group">
                <label htmlFor="category">Category:</label>
                <input type="text" id="category" name="category" placeholder="Category" value={transactionData.category} onChange={handleTransactionChange} disabled={loading} />
              </div>

              <div className="form-actions">
                <button type="submit" className="save-button" disabled={loading}>{loading ? 'Processing...' : 'Submit'}</button>
                <button type="button" className="cancel-button" onClick={() => setShowTransactionForm(false)} disabled={loading}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Transactions Modal */}
      {showTransactions && (
        <div className="modal">
          <div className="modal-content">
            <h2>Transactions for {banks.find(b => b.id === selectedBankId)?.name || 'Bank'}</h2>
            <button type="button" onClick={() => setShowTransactions(false)} className="close-button" style={{ position: 'absolute', top: 10, right: 10 }}>×</button>

            <div className="table-container" style={{ marginTop: 20 }}>
              <table className="banks-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Type</th>
                    <th>Amount</th>
                    <th>Description</th>
                    <th>Category</th>
                    <th>Balance After</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.length > 0 ? (
                    transactions.map(tx => (
                      <tr key={tx.id}>
                        <td>{tx.date}</td>
                        <td className={tx.transaction_type === 'income' ? 'income' : 'expense'}>{tx.transaction_type}</td>
                        <td>Rs. {parseFloat(tx.amount).toFixed(2)}</td>
                        <td>{tx.description || '-'}</td>
                        <td>{tx.category || '-'}</td>
                        <td>Rs. {parseFloat(tx.bank_balance_after).toFixed(2)}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="6" className="no-data">No transactions found</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Banks Table */}
      <div className="table-container" style={{ marginTop: 20 }}>
        <table className="banks-table">
          <thead>
            <tr>
              <th className="sortable" onClick={() => handleSortClick('name')}>
                Name {sortBy === 'name' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
              </th>
              <th className="sortable" onClick={() => handleSortClick('balance')}>
                Balance {sortBy === 'balance' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
              </th>
              <th>Actions</th>
            </tr>
          </thead>

          <tbody>
            {visibleBanks.length > 0 ? (
              visibleBanks.map(bank => (
                <tr key={bank.id}>
                  <td>{bank.name}</td>
                  <td>Rs. {safeNumber(bank.balance).toFixed(2)}</td>
                  <td className="actions-cell">
                    <button type="button" onClick={() => handleEdit(bank)} className="edit-button" disabled={loading}>Edit</button>
                    <button type="button" onClick={() => handleAddTransaction(bank.id)} className="transaction-button" disabled={loading}>Add Transaction</button>
                    <button type="button" onClick={() => handleViewTransactions(bank.id)} className="view-button" disabled={loading}>View Transactions</button>
                    <button type="button" onClick={() => handleDeleteBank(bank.id)} className="delete-button" disabled={loading}>Delete</button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="3" className="no-data">No banks found</td>
              </tr>
            )}
          </tbody>

          <tfoot>
            <tr className="totals-row">
              <td style={{ fontWeight: 600 }}>Totals</td>
              <td style={{ fontWeight: 600 }}>Rs. {totals.balance.toFixed(2)}</td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
