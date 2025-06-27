import React, { useState, useEffect } from 'react';
import { 
  getCreditCards, 
  createCreditCard, 
  getCreditCard,
  getUserCreditCards,
  updateCreditCard,
  deleteCreditCard,
  getCreditCardTransactions,
  addCreditCardTransaction,
  processBilling,
  getUsers
} from '../services/api';
import 'C:/Users/Rushw/Documents/PPA/portfolio-app/src/pages/creditcard.css';
import { format, parse } from 'date-fns';

export default function CreditCard() {
  const [cards, setCards] = useState([]);
  const [selectedCard, setSelectedCard] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [billingDetails, setBillingDetails] = useState(null);
  const [showBillingDetails, setShowBillingDetails] = useState(false);
  const [users, setUsers] = useState([]);
  const [formData, setFormData] = useState({
    name: '',
    userId: '',
    limit: '',
    billing_cycle_start: '1' // Default to 1st of the month
  });
  const [transactionData, setTransactionData] = useState({
    cardId: '',
    amount: '',
    date: format(new Date(), 'yyyy-MM-dd'), // User-friendly format
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

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [cardsResponse, usersResponse] = await Promise.all([
          getCreditCards(),
          getUsers()
        ]);
        
        setCards(cardsResponse || []);
        setUsers(usersResponse || []);
        setError(null);
      } catch (err) {
        console.error('Error fetching data:', err);
        setError('Failed to load credit card data');
        setCards([]);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  // Fetch detailed card information when selected
  const fetchCardDetails = async (cardId) => {
    try {
      setLoading(true);
      const card = await getCreditCard(cardId);
      setSelectedCard(card);
      setShowCardDetails(true);
      setError(null);
    } catch (err) {
      console.error('Error fetching card details:', err);
      setError('Failed to load card details');
    } finally {
      setLoading(false);
    }
  };

  // Fetch transactions for a card
  const fetchTransactions = async (cardId) => {
    try {
      setLoading(true);
      const transactions = await getCreditCardTransactions(cardId);
      setTransactions(transactions);
      setShowTransactions(true);
      setError(null);
    } catch (err) {
      console.error('Error fetching transactions:', err);
      setError('Failed to load transactions');
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleTransactionChange = (e) => {
    const { name, value, type, checked } = e.target;
    setTransactionData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleSubmit = async (e) => {
  e.preventDefault();
  try {
    setLoading(true);
    
    // Prepare the data exactly as backend expects it
    const cardData = {
      name: formData.name,
      user_id: parseInt(formData.userId),  // Note: using user_id not userId
      limit: parseFloat(formData.limit),
      billing_cycle_start: parseInt(formData.billing_cycle_start)
    };

    if (editMode && selectedCard) {
      // Update existing card - use the exact endpoint with card ID
      const response = await updateCreditCard(selectedCard.id, cardData);
      const updatedCard = response.card;
      
      // Update state with the exact response from backend
      const updatedCards = await getCreditCards();
      setCards(updatedCards);
      setSelectedCard(updatedCard);
      setEditMode(false);
    } else {
      // Create new card
      const newCard = await createCreditCard(cardData);
      setCards([...cards, newCard]);
    }
    
    resetForm();
  } catch (error) {
    console.error('Error saving card:', error);
    setError(error.message || 'Failed to save credit card');
  } finally {
    setLoading(false);
  }
};

  const handleTransactionSubmit = async (e) => {
    e.preventDefault();

    if (transactionData.isPayment === '') {
      alert('Please select whether this is a Payment or Expense.');
      return;
    }

    try {
      setLoading(true);
      
      // Convert date to DDMMYYYY format for backend
      const formattedDate = format(
        parse(transactionData.date, 'yyyy-MM-dd', new Date()),
        'ddMMyyyy'
      );

      await addCreditCardTransaction(transactionData.cardId, {
        amount: parseFloat(transactionData.isPayment ? 
          Math.abs(transactionData.amount) : 
          -Math.abs(transactionData.amount)),
        date: formattedDate,
        description: transactionData.description,
        category: transactionData.category,
        is_payment: transactionData.isPayment
      });
      
      // Refresh card details and transactions
      // Refresh the full card list to reflect latest balances
      const updatedCards = await getCreditCards();
      setCards(updatedCards);

      // Update selected card if it was visible before
      if (selectedCard) {
        const refreshedCard = updatedCards.find(c => c.id === selectedCard.id);
        setSelectedCard(refreshedCard || null);
      }
      
      resetTransactionForm();
    } catch (error) {
      console.error('Error adding transaction:', error);
      setError(error.message || 'Failed to add transaction');
    } finally {
      setLoading(false);
    }
  };

  const handleProcessBilling = async (cardId) => {
  try {
    setLoading(true);
    const response = await processBilling(cardId);
    const updatedCard = await getCreditCard(cardId);
    
    // Update the cards list with the updated card
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
  } catch (err) {
    console.error('Error processing billing:', err);
    setError('Failed to process billing');
  } finally {
    setLoading(false);
  }
};

  const handleDeleteCard = async (cardId) => {
    if (window.confirm('Are you sure you want to delete this credit card?')) {
      try {
        setLoading(true);
        await deleteCreditCard(cardId);
        const updatedCards = await getCreditCards();
        setCards(updatedCards);
        setSelectedCard(null);
        setShowCardDetails(false);
        setError(null);
      } catch (err) {
        console.error('Error deleting card:', err);
        setError(err.message || 'Failed to delete credit card');
      } finally {
        setLoading(false);
      }
    }
  };

  const handleAddTransaction = (cardId) => {
    setTransactionData(prev => ({ 
      ...prev, 
      cardId,
      date: format(new Date(), 'yyyy-MM-dd') // Reset to current date
    }));
    setShowCardDetails(false);
    setShowTransactions(false);
    setShowTransactionForm(true);
    
  };

  // Trigger edit mode and open the form while closing the details modal
const handleEditCard = (card) => {
  setFormData({
    name: card.name,
    userId: card.user_id,
    limit: card.limit.toString(),
    billing_cycle_start: card.billing_cycle_start.toString()
  });

  setSelectedCard(card);
  setEditMode(true);
  setShowForm(true);
  setShowCardDetails(false); // Close details modal to prevent overlap
};

  const resetForm = () => {
    setFormData({
      name: '',
      userId: '',
      limit: '',
      billing_cycle_start: '1'
    });
    setShowForm(false);
    setEditMode(false);
    setSelectedCard(null);
  };

  const resetTransactionForm = () => {
    setTransactionData({
      cardId: '',
      amount: '',
      date: format(new Date(), 'yyyy-MM-dd'),
      description: '',
      category: '',
      isPayment: ''
    });
    setShowTransactionForm(false);
  };

  const closeCardDetails = () => {
    setShowCardDetails(false);
    setSelectedCard(null);
  };

  const closeTransactions = () => {
    setShowTransactions(false);
    setTransactions([]);
  };

  if (loading) {
    return <div className="loading">Loading credit cards...</div>;
  }

  if (error) {
    return (
      <div className="error">
        {error}
        <button onClick={() => setError(null)}>Dismiss</button>
      </div>
    );
  }

  return (
    <div className="credit-card-container">
      <h1>Credit Cards</h1>
      
      <div className="actions">
        <button onClick={() => setShowForm(true)}>Add Credit Card</button>
      </div>

      {/* Credit Card Form */}
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
                <label>User</label>
                <select
                  name="userId"
                  value={formData.userId}
                  onChange={handleInputChange}
                  required
                >
                  <option value="">Select User</option>
                  {users.map(user => (
                    <option key={user.id} value={user.id}>{user.name}</option>
                  ))}
                </select>
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
                <button type="button" onClick={resetForm}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Transaction Form */}
      {showTransactionForm && (
        <div className="modal">
          <div className="modal-content">
            <h2>Add Transaction</h2>
            <form onSubmit={handleTransactionSubmit}>
              <div className="form-group">
                <label>Amount</label>
                <input
                  type="number"
                  step="0.01"
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
              
              <div className="form-group radio-group">
              <label>Transaction Type</label>
              <div className="radio-options">
                <label>
                  <input
                    type="radio"
                    name="isPayment"
                    value="true"
                    checked={transactionData.isPayment === true}
                    onChange={() => setTransactionData(prev => ({ ...prev, isPayment: true }))}
                  />
                  Payment
                </label>
                <label style={{ marginLeft: '20px' }}>
                  <input
                    type="radio"
                    name="isPayment"
                    value="false"
                    checked={transactionData.isPayment === false && transactionData.isPayment !== ''}
                    onChange={() => setTransactionData(prev => ({ ...prev, isPayment: false }))}
                  />
                  Expense
                </label>
              </div>
            </div>

              
              <div className="form-actions">
                <button type="submit" className="primary">Submit</button>
                <button type="button" onClick={resetTransactionForm}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Credit Cards Table */}
      <div className="cards-table">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Limit</th>
              <th>Used</th>
              <th>Available</th>
              <th>Billed Unpaid</th>
              <th>Unbilled Spends</th>
              <th>User</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {cards && cards.length > 0 ? (
              cards.map(card => (
                <tr key={card.id}>
                  <td>{card.name}</td>
                  <td>{card.limit?.toFixed(2)}</td>
                  <td>{card.used?.toFixed(2)}</td>
                  <td>{card.available_limit?.toFixed(2)}</td>
                  <td>{card.billed_unpaid?.toFixed(2)}</td>
                  <td>{card.unbilled_spends?.toFixed(2)}</td>
                  <td>
                    {users.find(u => u.id === card.user_id)?.name || 'N/A'}
                  </td>
                  <td className="actions-cell">
                    <button 
                      onClick={() => fetchCardDetails(card.id)}
                      className="info"
                    >
                      Details
                    </button>
                    <button 
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
                <td colSpan="8">No credit cards found</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Card Details Modal */}
      {showCardDetails && selectedCard && (
        <div className="modal">
          <div className="modal-content large">
            <div className="modal-header">
              <h2>Card Details: {selectedCard.name}</h2>
              <button onClick={closeCardDetails} className="close-button">&times;</button>
            </div>
            
            <div className="card-details">
              <div className="detail-row">
                <span className="detail-label">User:</span>
                <span>{users.find(u => u.id === selectedCard.user_id)?.name || 'N/A'}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Limit:</span>
                <span>${selectedCard.limit?.toFixed(2)}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Used:</span>
                <span>${selectedCard.used?.toFixed(2)}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Available:</span>
                <span>${selectedCard.available_limit?.toFixed(2)}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Billed Unpaid:</span>
                <span>${selectedCard.billed_unpaid?.toFixed(2)}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Unbilled Spends:</span>
                <span>${selectedCard.unbilled_spends?.toFixed(2)}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Billing Cycle Start:</span>
                <span>{selectedCard.billing_cycle_start} of month</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Total Payable:</span>
                <span>${selectedCard.total_payable?.toFixed(2)}</span>
              </div>
              {selectedCard.last_payment_date && (
                <div className="detail-row">
                  <span className="detail-label">Last Payment:</span>
                  <span>
                    ${selectedCard.last_payment_amount?.toFixed(2)} on{' '}
                    {format(
                      parse(selectedCard.last_payment_date, 'ddMMyyyy', new Date()),
                      'MMM dd, yyyy'
                    )}
                  </span>
                </div>
              )}
            </div>
            
            <div className="modal-actions">
              <button 
                onClick={() => fetchTransactions(selectedCard.id)}
                className="primary"
              >
                View Transactions
              </button>
              <button 
                onClick={() => handleProcessBilling(selectedCard.id)}
                className="secondary"
              >
                Process Billing
              </button>
              <button 
                onClick={() => handleEditCard(selectedCard)}
                className="info"
              >
                Edit Card
              </button>
              <button 
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
              <button onClick={closeTransactions} className="close-button">&times;</button>
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
                        <td>
                          {format(
                            parse(tx.date, 'ddMMyyyy', new Date()),
                            'MMM dd, yyyy'
                          )}
                        </td>
                        <td>
                          {tx.amount > 0 ? '+' : ''}{tx.amount?.toFixed(2)}
                        </td>
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
            
            <div className="modal-actions">
              <button 
                onClick={() => handleAddTransaction(selectedCard.id)}
                className="primary"
              >
                Add Transaction
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Add the NEW Billing Details Modal right here */}
      {showBillingDetails && billingDetails && (
        <div className="modal">
          <div className="modal-content">
            <div className="modal-header">
              <h2>Billing Processed Successfully</h2>
              <button onClick={() => setShowBillingDetails(false)} className="close-button">&times;</button>
            </div>
            
            <div className="billing-details">
              <p><strong>Transactions Billed:</strong> {billingDetails.transactionsBilled}</p>
              <p><strong>Total Amount Billed:</strong> ${billingDetails.totalAmountBilled?.toFixed(2)}</p>
              <p><strong>New Billed Unpaid:</strong> ${billingDetails.card.billed_unpaid?.toFixed(2)}</p>
              <p><strong>New Unbilled Spends:</strong> ${billingDetails.card.unbilled_spends?.toFixed(2)}</p>
            </div>
            
            <div className="modal-actions">
              <button 
                onClick={() => {
                  setShowBillingDetails(false);
                  fetchTransactions(billingDetails.card.id);
                }}
                className="primary"
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