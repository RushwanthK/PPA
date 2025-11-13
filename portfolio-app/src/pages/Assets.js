// src/pages/assets.js
import React, { useEffect, useState, useMemo } from 'react';
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

  // UI: search & sort
  const [searchText, setSearchText] = useState('');
  const [sortBy, setSortBy] = useState('name'); // default column
  const [sortDir, setSortDir] = useState('asc'); // 'asc' or 'desc'

  const clearError = () => setError(null);

  const safeNumber = (v) => {
    const n = Number(v);
    return Number.isNaN(n) ? 0 : n;
  };

  // Fetch data on component mount and when refreshFlag flips
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const assetsResponse = await getAssets();
        // support both shapes: response or response.data
        const arr = assetsResponse?.data || assetsResponse || [];
        setAssets(arr);
        setError(null);
      } catch (err) {
        console.error('Error fetching data:', err);
        setError('Failed to fetch data. Please try again later.');
        setAssets([]);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [refreshFlag]);

  // Handle transaction submission
  const handleTransactionSubmit = async (e) => {
    e.preventDefault();
    try {
      const { assetId, ...txn } = transaction;
      if (!assetId) throw new Error('Asset not selected for transaction');
      if (!txn.amount || isNaN(txn.amount)) throw new Error('Please enter a valid amount');

      await createAssetTransaction(assetId, {
        ...txn,
        amount: parseFloat(txn.amount),
      });

      // Refresh assets and transactions for that asset
      const [updatedAssetsResp, updatedTransactionsResp] = await Promise.all([
        getAssets(),
        getAssetTransactions(assetId)
      ]);
      const updatedAssets = updatedAssetsResp?.data || updatedAssetsResp || [];
      const updatedTransactions = updatedTransactionsResp?.data || updatedTransactionsResp || [];

      setAssets(updatedAssets);
      setTransactions(prev => ({ ...prev, [assetId]: updatedTransactions }));

      // Reset form
      setTransaction({ assetId: '', type: 'deposit', amount: '', description: '', category: '' });
      setTransactionVisible(false);
      setError(null);
    } catch (err) {
      console.error('Transaction failed:', err);
      setError(err.response?.data?.error || err.message || 'Transaction failed');
    }
  };

  // Handle add asset submission
  const handleAddAssetSubmit = async (e) => {
    e.preventDefault();
    try {
      if (!newAsset.name) throw new Error('Please enter an asset name');

      await createAsset({
        name: newAsset.name,
        platform: newAsset.platform,
        category: newAsset.category
      });

      // Refresh assets list
      const response = await getAssets();
      setAssets(response?.data || response || []);

      // Reset
      setNewAsset({ name: '', platform: '', category: '' });
      setShowAddAssetForm(false);
      setError(null);
    } catch (err) {
      console.error('Failed to add asset:', err);
      setError(err.response?.data?.error || err.message || 'Failed to add asset');
    }
  };

  // Fetch transactions for an asset
  const fetchTransactions = async (assetId) => {
    try {
      const response = await getAssetTransactions(assetId);
      const txs = response?.data || response || [];
      setTransactions(prev => ({ ...prev, [assetId]: txs }));
    } catch (err) {
      console.error('Error fetching transactions:', err);
      setTransactions(prev => ({ ...prev, [assetId]: [] }));
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

    if (safeNumber(asset.balance) !== 0) {
      setError("Asset cannot be deleted because its balance is not zero.");
      return;
    }

    if (!window.confirm("Are you sure you want to delete this asset?")) return;

    try {
      await deleteAsset(assetId);
      // Trigger refresh
      setRefreshFlag(prev => !prev);
      setError(null);
    } catch (err) {
      console.error("Failed to delete asset:", err);
      setError(err.response?.data?.error || "Failed to delete asset");
    }
  };

  const handleUpdateAsset = async (e) => {
    e.preventDefault();
    try {
      if (!editingAsset) return;
      const { id, ...updateData } = editingAsset;

      await updateAsset(id, {
        name: updateData.name,
        platform: updateData.platform,
        category: updateData.category
      });

      // Refresh assets
      setRefreshFlag(prev => !prev);
      setEditingAsset(null);
      setError(null);
    } catch (err) {
      console.error('Failed to update asset:', err);
      setError(err.response?.data?.error || err.message || 'Failed to update asset');
    }
  };

  // Sorting & filtering helpers
  const handleSortClick = (column) => {
    if (sortBy === column) {
      setSortDir(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(column);
      setSortDir('asc');
    }
  };

  const visibleAssets = useMemo(() => {
    const text = (searchText || '').trim().toLowerCase();
    const filtered = (assets || []).filter(a => {
      if (!text) return true;
      return (a.name || '').toLowerCase().includes(text);
    });

    const sorted = filtered.sort((a, b) => {
      let va, vb;
      if (sortBy === 'balance') {
        va = safeNumber(a.balance);
        vb = safeNumber(b.balance);
      } else if (sortBy === 'platform') {
        va = (a.platform || '').toString().toLowerCase();
        vb = (b.platform || '').toString().toLowerCase();
      } else if (sortBy === 'category') {
        va = (a.category || '').toString().toLowerCase();
        vb = (b.category || '').toString().toLowerCase();
      } else {
        // default name
        va = (a.name || '').toString().toLowerCase();
        vb = (b.name || '').toString().toLowerCase();
      }

      if (va < vb) return sortDir === 'asc' ? -1 : 1;
      if (va > vb) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });

    return sorted;
  }, [assets, searchText, sortBy, sortDir]);

  // Totals (sum of Balance for visible rows) — Option A
  const totals = useMemo(() => {
    return visibleAssets.reduce((acc, a) => {
      acc.balance += safeNumber(a.balance);
      return acc;
    }, { balance: 0 });
  }, [visibleAssets]);

  if (loading) return <div className="loading">Loading...</div>;

  return (
    <div className="assets-container">
      <h1>Assets</h1>

      {error && (
        <div className="error-with-close">
          <span>{error}</span>
          <button type="button" className="error-dismiss" onClick={clearError} aria-label="Dismiss error">&times;</button>
        </div>
      )}

      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 8 }}>
        <button type="button" className="add-asset-btn" onClick={() => setShowAddAssetForm(true)}>Add Asset</button>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            type="text"
            placeholder="Search by asset name..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ padding: '8px 10px', borderRadius: 4, border: '1px solid #444', background: '#2d2d2d', color: '#fff' }}
            aria-label="Search assets by name"
          />
        </div>
      </div>

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

              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <button type="submit" className="modal-submit-btn">Add</button>
                <button type="button" className="modal-cancel-btn" onClick={() => setShowAddAssetForm(false)}>Cancel</button>
              </div>
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

              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <button type="submit" className="modal-submit-btn">Update</button>
                <button type="button" className="modal-cancel-btn" onClick={() => setEditingAsset(null)}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Assets Table */}
      <table className="assets-table">
        <thead>
          <tr>
            <th className="sortable" onClick={() => handleSortClick('name')}>
              Name {sortBy === 'name' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
            </th>
            <th className="sortable" onClick={() => handleSortClick('balance')}>
              Balance {sortBy === 'balance' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
            </th>
            <th className="sortable" onClick={() => handleSortClick('platform')}>
              Platform {sortBy === 'platform' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
            </th>
            <th className="sortable" onClick={() => handleSortClick('category')}>
              Category {sortBy === 'category' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
            </th>
            <th>Actions</th>
          </tr>
        </thead>

        <tbody>
          {visibleAssets.length > 0 ? visibleAssets.map(asset => (
            <React.Fragment key={asset.id}>
              <tr>
                <td>{asset.name}</td>
                <td style={{ textAlign: 'right' }}>Rs. {safeNumber(asset.balance).toFixed(2)}</td>
                <td>{asset.platform || 'N/A'}</td>
                <td>{asset.category || 'N/A'}</td>
                <td>
                  <button
                    type="button"
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
                    type="button"
                    className="add-transaction-btn"
                    onClick={() => {
                      setTransaction(prev => ({ ...prev, assetId: asset.id }));
                      setTransactionVisible(true);
                    }}
                  >
                    Add Transaction
                  </button>

                  <button
                    type="button"
                    className="view-transactions-btn"
                    onClick={() => toggleTransactions(asset.id)}
                  >
                    {expandedAssetId === asset.id ? 'Hide Transactions' : 'View Transactions'}
                  </button>

                  <button
                    type="button"
                    className="delete-asset-btn"
                    onClick={() => handleDeleteAsset(asset.id)}
                  >
                    Delete
                  </button>
                </td>
              </tr>

              {expandedAssetId === asset.id && (
                <tr>
                  <td colSpan="5">
                    <div className="transactions">
                      <h3>Transactions</h3>
                      {transactions[asset.id]?.length > 0 ? (
                        <table className="inner-transactions-table">
                          <thead>
                            <tr>
                              <th>Date</th>
                              <th>Type</th>
                              <th style={{ textAlign: 'right' }}>Amount</th>
                              <th>Description</th>
                            </tr>
                          </thead>
                          <tbody>
                            {transactions[asset.id].map(tx => (
                              <tr key={tx.id}>
                                <td>{tx.date ? new Date(tx.date).toLocaleString() : 'N/A'}</td>
                                <td>{tx.transaction_type || 'N/A'}</td>
                                <td style={{ textAlign: 'right' }}>Rs. {safeNumber(tx.amount).toFixed(2)}</td>
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
          )) : (
            <tr>
              <td colSpan="5" className="no-data">No assets found</td>
            </tr>
          )}
        </tbody>

        <tfoot>
          <tr className="totals-row">
            <td style={{ fontWeight: 600 }}>Totals</td>
            <td style={{ fontWeight: 600, textAlign: 'right' }}>Rs. {totals.balance.toFixed(2)}</td>
            <td></td>
            <td></td>
            <td></td>
          </tr>
        </tfoot>
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

              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <button type="submit" className="modal-submit-btn">Submit</button>
                <button type="button" className="modal-cancel-btn" onClick={() => setTransactionVisible(false)}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
