import React, { useEffect, useState, useCallback } from 'react';
import { 
  getAssets, 
  createAssetTransaction, 
  createAsset,
  getAssetTransactions, 
  deleteAsset,
  updateAsset
} from '../services/api';
import './Assets.css';

export default function Assets() {
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingAsset, setEditingAsset] = useState(null);
  const [transactionVisible, setTransactionVisible] = useState(false);
  const [transaction, setTransaction] = useState({ 
    assetId: '', 
    type: 'deposit', 
    amount: '', 
    description: '', 
    category: '' 
  });
  const [refreshFlag, setRefreshFlag] = useState(false);
  const [newAsset, setNewAsset] = useState({ 
    name: '',
    platform: '',
    category: ''
  });
  const [showAddAssetForm, setShowAddAssetForm] = useState(false);
  const [expandedAssetId, setExpandedAssetId] = useState(null);
  const [transactions, setTransactions] = useState({});

const clearError = () => {
  setError(null);
};

  // Fetch data on component mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        const assetsResponse = await getAssets();
        setAssets(assetsResponse);
        setLoading(false);
      } catch (error) {
        console.error('Error fetching data:', error);
        setError('Failed to fetch data. Please try again later.');
        setLoading(false);
      }
    };

    fetchData();
  }, [refreshFlag]);

  // Handle transaction submission
  const handleTransactionSubmit = async (e) => {
    e.preventDefault();
    try {
      const { assetId, ...transactionData } = transaction;
      await createAssetTransaction(assetId, {
        ...transactionData,
        amount: parseFloat(transactionData.amount),
      });

      // Refresh both transactions and assets list
      const [updatedAssets, updatedTransactions] = await Promise.all([
        getAssets(),
        getAssetTransactions(assetId)
      ]);

      setAssets(updatedAssets.data || updatedAssets);
      setTransactions(prev => ({
        ...prev,
        [assetId]: updatedTransactions.data || updatedTransactions
      }));

      // Reset form
      setTransaction({ 
        assetId: '', 
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

  // Handle add asset submission
  const handleAddAssetSubmit = async (e) => {
    e.preventDefault();
    try {
      await createAsset({
        name: newAsset.name,
        platform: newAsset.platform,
        category: newAsset.category
      });
      
      // Refresh assets list
      const response = await getAssets();
      setAssets(response.data || response);
      
      // Reset form
      setNewAsset({ name: '', platform: '', category: '' });
      setShowAddAssetForm(false);
    } catch (error) {
      console.error('Failed to add asset:', error);
      setError(error.response?.data?.error || error.message || 'Failed to add asset');
    }
  };

  // Fetch transactions for an asset
  const fetchTransactions = async (assetId) => {
    try {
      const response = await getAssetTransactions(assetId);
      setTransactions(prev => ({
        ...prev,
        [assetId]: response.data || response
      }));
    } catch (error) {
      console.error('Error fetching transactions:', error);
      setTransactions(prev => ({
        ...prev,
        [assetId]: []
      }));
    }
  };

  // Toggle transactions visibility
  const toggleTransactions = async (assetId) => {
    if (expandedAssetId === assetId) {
      setExpandedAssetId(null);
    } else {
      setExpandedAssetId(assetId);
      if (!transactions[assetId]) {
        await fetchTransactions(assetId);
      }
    }
  };

  // Handle asset deletion
  const handleDeleteAsset = async (assetId) => {
    const asset = assets.find(a => a.id === assetId);
    if (!asset) {
      setError("Asset not found in state.");
      return;
    }
  
    console.log(`Attempting to delete asset ID: ${assetId}, balance: ${asset.balance}`);
  
    if (asset.balance !== 0) {
      setError("Asset cannot be deleted because its balance is not zero.");
      return;
    }
  
    if (!window.confirm("Are you sure you want to delete this asset?")) return;
  
    try {
      await deleteAsset(assetId);
      setRefreshFlag(prev => !prev);
    } catch (error) {
      console.error("Failed to delete asset:", error);
      setError(error.response?.data?.error || "Failed to delete asset");
    }
  };

  const handleUpdateAsset = async (e) => {
    e.preventDefault();
    try {
      const { id, ...updateData } = editingAsset;
      await updateAsset(id, {
        name: updateData.name,
        platform: updateData.platform,
        category: updateData.category
      });
      
      // Refresh assets list
      setRefreshFlag(prev => !prev);
      
      // Reset form
      setEditingAsset(null);
    } catch (error) {
      console.error('Failed to update asset:', error);
      setError(error.response?.data?.error || error.message || 'Failed to update asset');
    }
  };

  if (loading) return <div className="loading">Loading...</div>;
 

  return (
    <div className="assets-container">
      <h1>Assets</h1>
      {error && (
        <div className="error-with-close">
          <span>{error}</span>
          <button className="error-dismiss" onClick={clearError} aria-label="Dismiss error">&times;</button>
        </div>
      )}
      <button className="add-asset-btn" onClick={() => setShowAddAssetForm(true)}>Add Asset</button>

      {/* Add Asset Form */}
      {showAddAssetForm && (
        <div className="modal">
          <div className="modal-content">
            <h2>Add New Asset</h2>
            <form onSubmit={handleAddAssetSubmit}>
              <input
                type="text"
                placeholder="Asset Name"
                value={newAsset.name}
                onChange={(e) => setNewAsset({...newAsset, name: e.target.value})}
                required
              />
              
              <input
                type="text"
                placeholder="Platform (Optional)"
                value={newAsset.platform}
                onChange={(e) => setNewAsset({...newAsset, platform: e.target.value})}
              />
              
              <input
                type="text"
                placeholder="Category (Optional)"
                value={newAsset.category}
                onChange={(e) => setNewAsset({...newAsset, category: e.target.value})}
              />
              
              <button type="submit" className="modal-submit-btn">Add</button>
              <button type="button" className="modal-cancel-btn" onClick={() => setShowAddAssetForm(false)}>Cancel</button>
            </form>
          </div>
        </div>
      )}

      {/* Update Asset Form */}
      {editingAsset && (
        <div className="modal">
          <div className="modal-content">
            <h2>Update Asset</h2>
            <form onSubmit={handleUpdateAsset}>
              <input
                type="text"
                placeholder="Asset Name"
                value={editingAsset.name}
                onChange={(e) => setEditingAsset({...editingAsset, name: e.target.value})}
                required
              />
              
              <input
                type="text"
                placeholder="Platform (Optional)"
                value={editingAsset.platform}
                onChange={(e) => setEditingAsset({...editingAsset, platform: e.target.value})}
              />
              
              <input
                type="text"
                placeholder="Category (Optional)"
                value={editingAsset.category}
                onChange={(e) => setEditingAsset({...editingAsset, category: e.target.value})}
              />
              
              <button type="submit" className="modal-submit-btn">Update</button>
              <button type="button" className="modal-cancel-btn" onClick={() => setEditingAsset(null)}>Cancel</button>
            </form>
          </div>
        </div>
      )}

      {/* Assets Table */}
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Balance</th>
            <th>Platform</th>
            <th>Category</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {assets.map(asset => (
            <React.Fragment key={asset.id}>
              <tr>
                <td>{asset.name}</td>
                <td>{asset.balance?.toFixed(2) || '0.00'}</td>
                <td>{asset.platform || 'N/A'}</td>
                <td>{asset.category || 'N/A'}</td>
                <td>
                  <button 
                    className="update-asset-btn"
                    onClick={() => setEditingAsset({
                      id: asset.id,
                      name: asset.name,
                      platform: asset.platform,
                      category: asset.category
                    })}
                  >
                    Update
                  </button>
                  
                  <button 
                    className="add-transaction-btn"
                    onClick={() => {
                      setTransaction({...transaction, assetId: asset.id});
                      setTransactionVisible(true);
                    }}
                  >
                    Add Transaction
                  </button>
                  
                  <button 
                    className="view-transactions-btn"
                    onClick={() => toggleTransactions(asset.id)}
                  >
                    {expandedAssetId === asset.id ? 'Hide Transactions' : 'View Transactions'}
                  </button>
                  
                  <button 
                    className="delete-asset-btn"
                    onClick={() => handleDeleteAsset(asset.id)}
                  >
                    Delete
                  </button>
                </td>
              </tr>
              
              {expandedAssetId === asset.id && (
                <tr>
                  <td colSpan="6">
                    <div className="transactions">
                      <h3>Transactions</h3>
                      {transactions[asset.id]?.length > 0 ? (
                        <table>
                          <thead>
                            <tr>
                              <th>Date</th>
                              <th>Type</th>
                              <th>Amount</th>
                              <th>Description</th>
                            </tr>
                          </thead>
                          <tbody>
                            {transactions[asset.id].map(tx => (
                              <tr key={tx.id}>
                                <td>{tx.date ? new Date(tx.date).toLocaleString() : 'N/A'}</td>
                                <td>{tx.transaction_type || 'N/A'}</td>
                                <td>{tx.amount?.toFixed(2) || 'N/A'}</td>
                                <td>{tx.description || 'N/A'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      ) : (
                        <p>No transactions found for this asset.</p>
                      )}
                    </div>
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>

      {/* Transaction Form */}
      {transactionVisible && (
        <div className="modal">
          <div className="modal-content">
            <h2>Add Transaction</h2>
            <form onSubmit={handleTransactionSubmit}>
              <select
                value={transaction.type}
                onChange={(e) => setTransaction({...transaction, type: e.target.value})}
                required
              >
                <option value="deposit">Deposit</option>
                <option value="withdraw">Withdraw</option>
              </select>
              
              <input
                type="number"
                step="0.01"
                min="0.01"
                placeholder="Amount"
                value={transaction.amount}
                onChange={(e) => setTransaction({...transaction, amount: e.target.value})}
                required
              />
              
              <input
                type="text"
                placeholder="Description (Optional)"
                value={transaction.description}
                onChange={(e) => setTransaction({...transaction, description: e.target.value})}
              />
              
              <input
                type="text"
                placeholder="Category (Optional)"
                value={transaction.category}
                onChange={(e) => setTransaction({...transaction, category: e.target.value})}
              />
              
              <button type="submit" className="modal-submit-btn">Submit</button>
              <button type="button" className="modal-cancel-btn" onClick={() => setTransactionVisible(false)}>Cancel</button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}