// src/pages/Dashboard.js
import React, { useEffect, useState, useCallback } from 'react';
import './Dashboard.css';
import {
  getDashboardSummary,
  getDashboardSpending,
  getDashboardAssetAllocation
} from '../services/api';
import {
  BarChart, Bar, PieChart, Pie,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, Cell
} from 'recharts';

export default function Dashboard() {
  const [summary, setSummary] = useState({
    total_assets: 0,
    total_bank_balance: 0,
    total_savings: 0,
    total_credit_card_debt: 0,
    net_worth: 0
  });

  const [spendingData, setSpendingData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);
  const [assetAllocation, setAssetAllocation] = useState([]);

  const FILTER_OPTIONS = [
    { key: '30d', label: 'Last 30 days' },
    { key: '3m', label: 'Last 3 months' },
    { key: '6m', label: 'Last 6 months' },
    { key: '1y', label: 'Last 1 year' },
    { key: 'all', label: 'All time' }
  ];
  const [spendRange, setSpendRange] = useState('30d');
  const [isApplyingSpend, setIsApplyingSpend] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);

      const summaryResp =
        await getDashboardSummary();

      setSummary(summaryResp);
    } catch (err) {
      console.error('Dashboard fetchData error', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadAssetAllocation = useCallback(async () => {
    try {
      const data =
        await getDashboardAssetAllocation();

      setAssetAllocation(data);
    } catch (error) {
      console.error(
        'Error loading asset allocation',
        error
      );
    }
  }, []);

  useEffect(() => {
    fetchData();
    loadAssetAllocation();
  }, [
    fetchData,
    loadAssetAllocation,
    refreshKey
  ]);

  useEffect(() => {
    const loadSpending = async () => {
      try {
        const data = await getDashboardSpending(spendRange);
        setSpendingData(data);
      } catch (error) {
        console.error('Error loading spending data', error);
      }
    };

    loadSpending();
  }, [spendRange]);

  const formatINR = (amount) =>
    new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(amount || 0);

  const spendingByCategory = spendingData;

  const handleRefresh = () => setRefreshKey(k => k + 1);

  if (loading) {
    return (
      <div className="dashboard-container">
        <div className="loading-spinner" />
        <p>Loading financial data...</p>
      </div>
    );
  }

  const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8', '#82CA9D', '#FF6B6B', '#00BFA6'];

  return (
    <div className="dashboard-container">
      <h1>Financial Dashboard</h1>

      <div className="summary-grid">
        <div className="card net-worth"><h3>Net Worth</h3><p>{formatINR(summary.net_worth)}</p></div>
        <div className="card"><h3>Total Assets</h3><p>{formatINR(summary.total_assets)}</p></div>
        <div className="card"><h3>Bank Balances</h3><p>{formatINR(summary.total_bank_balance)}</p></div>
        <div className="card"><h3>Savings</h3><p>{formatINR(summary.total_savings)}</p></div>
        <div className="card debt"><h3>Credit Card Debt</h3><p>{formatINR(summary.total_credit_card_debt)}</p></div>
      </div>

      <div className="charts-grid">
        <div className="chart-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3>Spending by Category</h3>
            <div className="chart-filter">
              <select value={spendRange} onChange={(e) => setSpendRange(e.target.value)}>
                {FILTER_OPTIONS.map(o => <option key={o.key} value={o.key}>{o.label}</option>)}
              </select>
              <button type="button" onClick={() => { setIsApplyingSpend(true); setTimeout(() => setIsApplyingSpend(false), 250); }} className="small-apply">
                {isApplyingSpend ? 'Applying...' : 'Apply'}
              </button>
            </div>
          </div>

          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={spendingByCategory}>
              <XAxis
                dataKey="name"
                interval={0}
                angle={-35}
                textAnchor="end"
                height={80}
              />
              <YAxis tickFormatter={(v) => `${Math.round(v)}`} />
              <Tooltip formatter={(v) => formatINR(v)} />
              <Bar dataKey="value">{spendingByCategory.map((entry, i) => <Cell key={`s-${i}`} fill={COLORS[i % COLORS.length]} />)}</Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3>Asset Allocation (by category)</h3>
            <div className="chart-filter" style={{ opacity: 0.85 }}>
              <span style={{ fontSize: 12, color: '#aaa' }}>Showing current balances</span>
            </div>
          </div>

          <ResponsiveContainer width="100%" height={320}>
            <PieChart>
              <Pie data={assetAllocation} cx="50%" cy="50%" outerRadius={100} dataKey="value" nameKey="name"
                   label={({ name, percent }) => `${name}: ${Math.round(percent * 100)}%`}>
                {assetAllocation.map((entry, i) => <Cell key={`a-${i}`} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip formatter={(v) => formatINR(v)} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div style={{ marginTop: 20, display: 'flex', justifyContent: 'flex-end' }}>
        <button type="button" onClick={handleRefresh} className="small-apply">Refresh Data</button>
      </div>
    </div>
  );
}
