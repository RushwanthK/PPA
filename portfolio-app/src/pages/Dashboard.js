import React, { useEffect, useState } from 'react';
import './Dashboard.css';
import {
  getAssets,
  getBanks,
  getSavings,
  getCreditCards,
  getBankTransactions,
  getAssetTransactions,
  getSavingTransactions,
  getCreditCardTransactions
} from '../services/api';
import {
  BarChart, Bar, PieChart, Pie, LineChart, Line,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, Cell
} from 'recharts';
import { format, subDays, subMonths, startOfMonth } from 'date-fns';

export default function Dashboard() {
  const [assets, setAssets] = useState([]);
  const [banks, setBanks] = useState([]);
  const [savings, setSavings] = useState([]);
  const [creditCards, setCreditCards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState('30d');
  const [filterApplied, setFilterApplied] = useState(false);
  
  const [spendingByCategory, setSpendingByCategory] = useState([]);
  const [netWorthHistory, setNetWorthHistory] = useState([]);
  const [savingsProgress, setSavingsProgress] = useState([]);

  // Time ranges
  const timeRanges = {
    '7d': 'Last 7 Days',
    '30d': 'Last 30 Days',
    '90d': 'Last 90 Days',
    '6m': 'Last 6 Months',
    '1y': 'Last Year'
  };

  // Calculate financial metrics
  const totalAssets = assets.reduce((sum, a) => sum + a.balance, 0);
  const totalBanks = banks.reduce((sum, b) => sum + b.balance, 0);
  const totalSavings = savings.reduce((sum, s) => sum + s.balance, 0);
  const totalDebt = creditCards.reduce((sum, c) => sum + c.used, 0);
  const netWorth = totalAssets + totalBanks + totalSavings - totalDebt;

  // Format currency
  const formatINR = (amount) => 
    new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0
    }).format(amount);

  // Fetch all data
  useEffect(() => {
    fetchData();
  }, []); // run once on initial load

  useEffect(() => {
    if (filterApplied) {
      fetchData();
      setFilterApplied(false);
    }
  }, [filterApplied, timeRange]); 

  const fetchData = async () => {
    try {
      setLoading(true);
      
      const [assetData, bankData, savingData, creditCardData] = await Promise.all([
        getAssets(),
        getBanks(),
        getSavings(),
        getCreditCards()
      ]);
      
      setAssets(assetData);
      setBanks(bankData.data || []);
      setSavings(savingData);
      setCreditCards(creditCardData);

      // Fetch transactions in parallel
      const allTransactions = await fetchTransactions(
        assetData, 
        bankData.data || [], 
        savingData, 
        creditCardData
      );
      
      const filteredTxns = filterTransactionsByRange(allTransactions, timeRange);
      
      setSpendingByCategory(calculateCategoryTotals(filteredTxns));
      setNetWorthHistory(calculateNetWorthHistory(filteredTxns, timeRange));
      setSavingsProgress(calculateSavingsProgress(savingData));
    } catch (error) {
      console.error('Error loading dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  // Fetch all transactions
  const fetchTransactions = async (assets, banks, savings, creditCards) => {
    const allTxns = [];
    
    // Asset transactions
    const assetTxns = await Promise.all(
      assets.map(a => getAssetTransactions(a.id))
    );
    assetTxns.forEach(res => {
      res.data?.forEach(tx => 
        allTxns.push({ 
          ...tx, 
          date: new Date(tx.date), 
          type: 'asset',
          amount: tx.transaction_type === 'withdrawal' ? -tx.amount : tx.amount
        })
      );
    });

    // Bank transactions
    const bankTxns = await Promise.all(
      banks.map(b => getBankTransactions(b.id))
    );
    bankTxns.forEach(res => {
      res.data?.forEach(tx => 
        allTxns.push({ 
          ...tx, 
          date: new Date(tx.date), 
          type: 'bank',
          amount: tx.transaction_type === 'expense' ? -tx.amount : tx.amount
        })
      );
    });

    // Saving transactions
    const savingTxns = await Promise.all(
      savings.map(s => getSavingTransactions(s.id))
    );
    savingTxns.forEach(res => {
      res.forEach(tx => 
        allTxns.push({ 
          ...tx, 
          date: new Date(tx.date), 
          type: 'saving',
          amount: tx.transaction_type === 'withdrawal' ? -tx.amount : tx.amount
        })
      );
    });

    // Credit card transactions
    const creditTxns = await Promise.all(
      creditCards.map(c => getCreditCardTransactions(c.id))
    );
    creditTxns.forEach(res => {
      res.forEach(tx => 
        allTxns.push({ 
          ...tx, 
          date: new Date(tx.date), 
          type: 'credit',
          amount: tx.amount
        })
      );
    });

    return allTxns;
  };

  // Filter transactions by time range
  const filterTransactionsByRange = (transactions, range) => {
    const now = new Date();
    let cutoff;
    
    switch(range) {
      case '7d': cutoff = subDays(now, 7); break;
      case '30d': cutoff = subDays(now, 30); break;
      case '90d': cutoff = subDays(now, 90); break;
      case '6m': cutoff = subMonths(now, 6); break;
      case '1y': cutoff = subMonths(now, 12); break;
      default: cutoff = subDays(now, 30);
    }
    
    return transactions.filter(tx => new Date(tx.date) > cutoff);
  };

  // Calculate spending by category
  const calculateCategoryTotals = (transactions) => {
    const categories = {};
    
    transactions.forEach(tx => {
      if (tx.amount < 0) {
        const category = tx.category || 'Uncategorized';
        categories[category] = (categories[category] || 0) + Math.abs(tx.amount);
      }
    });
    
    return Object.entries(categories)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 6);
  };

  // Calculate net worth history
  const calculateNetWorthHistory = (transactions, range) => {
    const history = [];
    const now = new Date();
    let startDate;
    
    switch(range) {
      case '7d': startDate = subDays(now, 7); break;
      case '30d': startDate = subDays(now, 30); break;
      case '90d': startDate = subDays(now, 90); break;
      case '6m': startDate = subMonths(now, 6); break;
      case '1y': startDate = subMonths(now, 12); break;
      default: startDate = subDays(now, 30);
    }
    
    // Group by day
    const dailyData = {};
    const dateFormat = range === '1y' || range === '6m' ? 'MMM yy' : 'dd MMM';
    
    transactions.forEach(tx => {
      const dateStr = format(new Date(tx.date), dateFormat);
      if (!dailyData[dateStr]) {
        dailyData[dateStr] = 0;
      }
      dailyData[dateStr] += tx.amount;
    });
    
    // Convert to array
    for (const [date, netChange] of Object.entries(dailyData)) {
      history.push({ date, netWorth: netChange });
    }
    
    return history.sort((a, b) => new Date(a.date) - new Date(b.date));
  };

  // Calculate savings progress
  const calculateSavingsProgress = (savings) => {
    return savings.map(saving => ({
      name: saving.name,
      value: saving.balance,
      goal: saving.goal || saving.balance * 1.5 // Default to 150% of current
    }));
  };

  // Apply filter
  const handleApplyFilter = () => {
    setFilterApplied(true);
  };

  if (loading && !filterApplied) {
    return (
      <div className="dashboard-container">
        <div className="loading-spinner"></div>
        <p>Loading financial data...</p>
      </div>
    );
  }

  // Chart colors
  const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8', '#82CA9D'];

  return (
    <div className="dashboard-container">
      <h1>Financial Dashboard</h1>
      
      <div className="filter-bar">
        <label>Time Range:</label>
        <select 
          value={timeRange} 
          onChange={(e) => setTimeRange(e.target.value)}
        >
          {Object.entries(timeRanges).map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>
        <button onClick={handleApplyFilter}>Apply Filter</button>
      </div>

      {/* Financial Summary Cards */}
      <div className="summary-grid">
        <div className="card net-worth">
          <h3>Net Worth</h3>
          <p>{formatINR(netWorth)}</p>
        </div>
        
        <div className="card">
          <h3>Total Assets</h3>
          <p>{formatINR(totalAssets)}</p>
        </div>
        
        <div className="card">
          <h3>Bank Balances</h3>
          <p>{formatINR(totalBanks)}</p>
        </div>
        
        <div className="card">
          <h3>Savings</h3>
          <p>{formatINR(totalSavings)}</p>
        </div>
        
        <div className="card debt">
          <h3>Credit Card Debt</h3>
          <p>{formatINR(totalDebt)}</p>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="charts-grid">
        {/* Spending by Category */}
        <div className="chart-card">
          <h3>Spending by Category ({timeRanges[timeRange]})</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={spendingByCategory}>
              <XAxis dataKey="name" />
              <YAxis tickFormatter={value => formatINR(value)} />
              <Tooltip formatter={value => formatINR(value)} />
              <Bar dataKey="value" fill="#8884d8">
                {spendingByCategory.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        
        {/* Savings Progress */}
        <div className="chart-card">
          <h3>Savings Progress</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={savingsProgress}
                cx="50%"
                cy="50%"
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
                nameKey="name"
                label={({ name, percent }) => 
                  `${name}: ${(percent * 100).toFixed(0)}%`}
              >
                {savingsProgress.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={value => formatINR(value)} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
        
        {/* Net Worth Trend */}
        <div className="chart-card">
          <h3>Net Worth Trend ({timeRanges[timeRange]})</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={netWorthHistory}>
              <XAxis dataKey="date" />
              <YAxis tickFormatter={value => formatINR(value)} />
              <Tooltip formatter={value => formatINR(value)} />
              <Legend />
              <Line 
                type="monotone" 
                dataKey="netWorth" 
                stroke="#8884d8" 
                strokeWidth={2}
                dot={{ r: 4 }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        
        {/* Asset Allocation */}
        <div className="chart-card">
          <h3>Asset Allocation</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={assets}
                cx="50%"
                cy="50%"
                outerRadius={80}
                fill="#8884d8"
                dataKey="balance"
                nameKey="name"
                label={({ name, percent }) => 
                  `${name}: ${(percent * 100).toFixed(0)}%`}
              >
                {assets.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={value => formatINR(value)} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}