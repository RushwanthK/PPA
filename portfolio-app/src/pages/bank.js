import React, { useState, useEffect } from 'react';
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
  const [formData, setFormData] = useState({
    id: '',
    name: ''
  });
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

  // Fetch data on component mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        
        const banksResponse = await getBanks();
        setBanks(Array.isArray(banksResponse?.data) ? banksResponse.data : []);
      } catch (err) {
        console.error('Error fetching data:', err);
        setError(err.message || 'Failed to fetch data');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  // Helper function to get user name

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleTransactionChange = (e) => {
    const { name, value } = e.target;
    setTransactionData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setError(null);
      setSuccess(null);
      setLoading(true);
      
      if (!formData.name) {
        throw new Error("Please enter a bank name");
      }
      
      if (formData.id) {
        const updatedBank = await updateBank(formData.id, {
          name: formData.name
        });
        
        setBanks(banks.map(bank => 
          bank.id === formData.id ? { ...bank, ...updatedBank } : bank
        ));
        setSuccess('Bank updated successfully!');
      } else {
        const newBank = await createBank({
          name: formData.name
        });
        
        setBanks([...banks, newBank]);
        setSuccess('Bank created successfully!');
      }
      
      resetForm();
    } catch (error) {
      console.error('Error saving bank:', error);
      setError(error.message || 'Failed to save bank');
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
      
      if (!transactionData.amount || isNaN(transactionData.amount)) {
        throw new Error("Please enter a valid amount");
      }
      
      if (parseFloat(transactionData.amount) <= 0) {
        throw new Error("Amount must be greater than 0");
      }
      
      await addBankTransaction(transactionData.bankId, {
        amount: parseFloat(transactionData.amount),
        type: transactionData.type,
        description: transactionData.description,
        category: transactionData.category
      });
      
      // Refresh banks to get updated balance
      const banksResponse = await getBanks();
      setBanks(banksResponse.data || []);
      setSuccess('Transaction added successfully!');
      
      // Reset form
      setTransactionData({
        bankId: '',
        amount: '',
        type: 'income',
        description: '',
        category: ''
      });
      setShowTransactionForm(false);
    } catch (error) {
      console.error('Error adding transaction:', error);
      setError(error.message || 'Failed to add transaction');
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
    
    // Refresh banks list
    const banksResponse = await getBanks();
    setBanks(banksResponse.data || []);
    setSuccess('Bank deleted successfully!');
  } catch (error) {
    console.error('Error deleting bank:', error);
    // Check for specific error message about linked savings
    if (error.response?.data?.error?.includes('linked savings accounts')) {
      setError('Cannot delete bank because it has linked savings accounts. Please remove all linked savings accounts first.');
    } else {
      setError(error.message || 'Failed to delete bank');
    }
  } finally {
    setLoading(false);
  }
};
  const handleEdit = (bank) => {
    setFormData({
      id: bank.id,
      name: bank.name
    });
    setShowForm(true);
  };

  const handleAddTransaction = (bankId) => {
    setTransactionData(prev => ({ 
      ...prev, 
      bankId: bankId.toString()
    }));
    setShowTransactionForm(true);
  };

  const handleViewTransactions = async (bankId) => {
    try {
      setError(null);
      setLoading(true);
      const response = await getBankTransactions(bankId);
      setTransactions(response.data || []);
      setSelectedBankId(bankId);
      setShowTransactions(true);
    } catch (error) {
      console.error('Error fetching transactions:', error);
      setError(error.message || 'Failed to fetch transactions');
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setFormData({
      id: '',
      name: '',
      userId: ''
    });
    setShowForm(false);
  };

  if (loading && banks.length === 0) return <div className="loading">Loading banks...</div>;
  
  return (
    <div className="bank-container">
      <h1>Banks</h1>
      
      {error && (
        <div className="bank-error-with-close">
          <span>{error}</span>
          <button className="error-dismiss" onClick={() => setError(null)} aria-label="Dismiss error">&times;</button>
        </div>
      )}
      
      {success && (
        <div className="success-message">
          <strong>Success:</strong> {success}
          <button onClick={() => setSuccess(null)} className="close-success">
            ×
          </button>
        </div>
      )}
      
      <button 
        onClick={() => setShowForm(true)}
        className="add-button"
        disabled={loading}
      >
        {loading ? 'Processing...' : 'Add Bank'}
      </button>

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
                <button 
                  type="submit" 
                  className="save-button"
                  disabled={loading}
                >
                  {loading ? 'Saving...' : 'Save'}
                </button>
                <button 
                  type="button" 
                  onClick={resetForm}
                  className="cancel-button"
                  disabled={loading}
                >
                  Cancel
                </button>
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
                <label htmlFor="category">Category:</label>
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
              
              <div className="form-actions">
                <button 
                  type="submit" 
                  className="save-button"
                  disabled={loading}
                >
                  {loading ? 'Processing...' : 'Submit'}
                </button>
                <button 
                  type="button" 
                  onClick={() => setShowTransactionForm(false)}
                  className="cancel-button"
                  disabled={loading}
                >
                  Cancel
                </button>
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
      <button 
        onClick={() => setShowTransactions(false)}
        className="close-button"
        style={{ position: 'absolute', top: '10px', right: '10px' }}
      >
        ×
      </button>
      
      <div className="table-container" style={{ marginTop: '20px' }}>
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
                  <td className={tx.transaction_type === 'income' ? 'income' : 'expense'}>
                    {tx.transaction_type}
                  </td>
                  <td>Rs. {parseFloat(tx.amount).toFixed(2)}</td>
                  <td>{tx.description || '-'}</td>
                  <td>{tx.category || '-'}</td>
                  <td>Rs. {parseFloat(tx.bank_balance_after).toFixed(2)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="6" className="no-data">
                  No transactions found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  </div>
)}

      {/* Banks Table */}
      <div className="table-container">
        <table className="banks-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Balance</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {banks.length > 0 ? (
              banks.map(bank => (
                <tr key={bank.id}>
                  <td>{bank.name}</td>
                  <td>Rs. {bank.balance?.toFixed(2) || '0.00'}</td>
                  <td className="actions-cell">
                    <button 
                      onClick={() => handleEdit(bank)}
                      className="edit-button"
                      disabled={loading}
                    >
                      Edit
                    </button>
                    <button 
                      onClick={() => handleAddTransaction(bank.id)}
                      className="transaction-button"
                      disabled={loading}
                    >
                      Add Transaction
                    </button>
                    <button 
                      onClick={() => handleViewTransactions(bank.id)}
                      className="view-button"
                      disabled={loading}
                    >
                      View Transactions
                    </button>
                    <button 
                      onClick={() => handleDeleteBank(bank.id)}
                      className="delete-button"
                      disabled={loading}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="4" className="no-data">
                  No banks found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}