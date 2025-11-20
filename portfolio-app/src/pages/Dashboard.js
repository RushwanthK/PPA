// src/pages/Dashboard.js
import React, { useEffect, useState, useCallback, useMemo, useRef } from 'react';
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
import { format, subDays, subMonths, startOfMonth, isValid } from 'date-fns';

/*
  Dashboard.js - full replacement
  Key improvements:
    - concurrency-limited fetching of per-entity transactions (no flood)
    - normalization of transaction shapes
    - cumulative net worth calculation (uses starting balances)
    - calculate spending-by-category with heuristics
    - useMemo for heavy derived data
    - better loading UX and debounced Apply Filter
*/

export default function Dashboard() {
  // domain data
  const [assets, setAssets] = useState([]);
  const [banks, setBanks] = useState([]);
  const [savings, setSavings] = useState([]);
  const [creditCards, setCreditCards] = useState([]);

  // dashboard state
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState('30d');
  const [filterApplied, setFilterApplied] = useState(false);

  // derived chart states
  const [allTransactions, setAllTransactions] = useState([]); // normalized txs (cached)
  const [ticker, setTicker] = useState(0); // use to force refresh if needed

  // UI small state
  const [isApplying, setIsApplying] = useState(false);

  // debounce ref to avoid double-click floods
  const applyTimeout = useRef(null);

  // Time ranges
  const timeRanges = {
    '7d': 'Last 7 Days',
    '30d': 'Last 30 Days',
    '90d': 'Last 90 Days',
    '6m': 'Last 6 Months',
    '1y': 'Last Year'
  };

  // Chart colors
  const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8', '#82CA9D'];

  // Simple currency formatter (no fractional digits as you used)
  const formatINR = (amount) =>
    new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0
    }).format(amount || 0);

  // ----------- Small utility helpers -----------
  const safeNumber = (v) => {
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  };

  // concurrency-limited mapper (simple worker pool)
  const mapWithConcurrency = async (items, fn, concurrency = 5) => {
    const results = new Array(items.length);
    let idx = 0;
    const workers = new Array(Math.min(concurrency, items.length)).fill(null).map(async () => {
      while (true) {
        const i = idx++;
        if (i >= items.length) break;
        try {
          results[i] = await fn(items[i], i);
        } catch (err) {
          console.warn('mapWithConcurrency error on item', items[i], err);
          results[i] = null;
        }
      }
    });
    await Promise.all(workers);
    return results;
  };

  // Normalize a raw transaction object to common shape:
  // { id, date: Date, amount: number, category: string, sourceType: 'asset'|'bank'|'saving'|'credit', raw: original }
  // Defensive normalize: ensures date is either a valid Date or null
const normalizeTransaction = (raw, sourceType) => {
  const obj = raw && raw.data ? raw.data : raw;
  // Try to parse date safely
  let parsedDate = null;
  if (obj && obj.date) {
    // some backends send ISO string, some send epoch; new Date(...) handles many formats
    const cand = new Date(obj.date);
    if (isValid(cand)) parsedDate = cand;
  }
  // If no valid date, set to null (we will skip null-dated txns later)
  const amt = (() => {
    const a = obj?.amount ?? obj?.amt ?? obj?.value ?? 0;
    const n = Number(a);
    return Number.isFinite(n) ? n : 0;
  })();

  const category = obj?.category || obj?.tx_category || obj?.category_name || obj?.categoryName || 'Uncategorized';

  return {
    id: obj?.id ?? obj?.tx_id ?? null,
    date: parsedDate,              // either Date or null
    amount: amt,
    category,
    sourceType,
    raw: obj
  };
};

  // ----------- Fetching transactions safely -----------
  // We attempt to pass { since } to service functions if they accept it (they may ignore).
  // This function fetches transactions for each entity group using limited concurrency.
  const fetchTransactionsForEntities = async (entities, fetchFn, sourceType, concurrency = 5, sinceIso = null) => {
    if (!Array.isArray(entities) || entities.length === 0) return [];
    const results = await mapWithConcurrency(entities, async (ent) => {
      try {
        // Try to call fetchFn with (id, { since: ... }) signature if supported
        const maybeResp = await (fetchFn.length >= 2 ? fetchFn(ent.id, { since: sinceIso }) : fetchFn(ent.id));
        const arr = maybeResp?.data ?? maybeResp ?? [];
        return Array.isArray(arr) ? arr.map(r => normalizeTransaction(r, sourceType)) : [];
      } catch (err) {
        console.warn(`Error fetching transactions for ${sourceType} id=${ent?.id}`, err);
        return [];
      }
    }, concurrency);

    // flatten and return
    return results.flat().filter(Boolean);
  };

  // Master fetch: fetch assets/banks/savings/creditcards, then transactions in controlled batches
  const fetchData = useCallback(async (range) => {
    try {
      setLoading(true);

      // 1) fetch master lists in parallel
      const [assetData, bankData, savingData, creditCardData] = await Promise.all([
        getAssets(),
        getBanks(),
        getSavings(),
        getCreditCards()
      ]);

      const assetsArr = assetData?.data ?? assetData ?? [];
      const banksArr = bankData?.data ?? bankData ?? [];
      const savingsArr = savingData?.data ?? savingData ?? [];
      const creditCardsArr = creditCardData?.data ?? creditCardData ?? [];

      setAssets(assetsArr);
      setBanks(banksArr);
      setSavings(savingsArr);
      setCreditCards(creditCardsArr);

      // Compute an optional cutoff ISO for transaction queries (helpful if backend supports it)
      let cutoffDate = null;
      const now = new Date();
      switch (range) {
        case '7d': cutoffDate = subDays(now, 7); break;
        case '30d': cutoffDate = subDays(now, 30); break;
        case '90d': cutoffDate = subDays(now, 90); break;
        case '6m': cutoffDate = subMonths(now, 6); break;
        case '1y': cutoffDate = subMonths(now, 12); break;
        default: cutoffDate = subDays(now, 30);
      }
      const sinceIso = cutoffDate ? cutoffDate.toISOString() : null;

      // 2) fetch transactions for each group with concurrency limits
      // increase concurrency a bit for assets/banks if you expect many
      const [
        assetTxns,
        bankTxns,
        savingTxns,
        creditTxns
      ] = await Promise.all([
        fetchTransactionsForEntities(assetsArr, getAssetTransactions, 'asset', 6, sinceIso),
        fetchTransactionsForEntities(banksArr, getBankTransactions, 'bank', 6, sinceIso),
        fetchTransactionsForEntities(savingsArr, getSavingTransactions, 'saving', 6, sinceIso),
        fetchTransactionsForEntities(creditCardsArr, getCreditCardTransactions, 'credit', 6, sinceIso)
      ]);

      // 3) flatten and set
      const allTxns = [...assetTxns, ...bankTxns, ...savingTxns, ...creditTxns];
      // sort by date ascending to make subsequent logic consistent
      allTxns.sort((a, b) => a.date - b.date);
      setAllTransactions(allTxns);

    } catch (err) {
      console.error('fetchData error', err);
      // keep previous state if error occurs
    } finally {
      setLoading(false);
    }
  }, []);

  // initial load and re-load when timeRange changes or when filter applied
  useEffect(() => {
    // initial fetch
    fetchData(timeRange);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchData, ticker]);

  // React when user presses Apply Filter: debounce to avoid double clicks
  useEffect(() => {
    if (!filterApplied) return;
    setIsApplying(true);
    // small debounce to allow quick interactions
    if (applyTimeout.current) clearTimeout(applyTimeout.current);
    applyTimeout.current = setTimeout(async () => {
      await fetchData(timeRange);
      setFilterApplied(false);
      setIsApplying(false);
    }, 250);
    // cleanup
    return () => {
      if (applyTimeout.current) clearTimeout(applyTimeout.current);
    };
  }, [filterApplied, fetchData, timeRange]);

  // ----------- Derived / memoized chart data -----------
  // Spending by category (expenses only).
  // Heuristic: treat negative amounts as outflows; for credit source assume positive charges are expenses.
  const spendingByCategory = useMemo(() => {
    const cat = {};
    for (const tx of allTransactions) {
      const amt = safeNumber(tx.amount);
      let expense = 0;
      if (amt < 0) expense = Math.abs(amt);
      else if (tx.sourceType === 'credit') expense = Math.abs(amt); // many credit APIs store charges as positive
      else expense = 0;

      if (expense <= 0) continue;
      const name = tx.category || 'Uncategorized';
      cat[name] = (cat[name] || 0) + expense;
    }

    const arr = Object.entries(cat).map(([name, value]) => ({ name, value }));
    arr.sort((a, b) => b.value - a.value);
    return arr.slice(0, 6);
  }, [allTransactions]);

  // Savings progress (simple mapping from savings state)
  const savingsProgress = useMemo(() => {
    return (savings || []).map(s => ({
      name: s.name,
      value: safeNumber(s.balance),
      goal: s.goal ?? Math.max(1, safeNumber(s.balance) * 1.5)
    }));
  }, [savings]);

  // Net worth history — cumulative net worth timeline
  const netWorthHistory = useMemo(() => {
    const now = new Date();
    let start;
    let dateFormat;
    switch (timeRange) {
      case '7d': start = subDays(now, 7); dateFormat = 'dd MMM'; break;
      case '30d': start = subDays(now, 30); dateFormat = 'dd MMM'; break;
      case '90d': start = subDays(now, 90); dateFormat = 'dd MMM'; break;
      case '6m': start = subMonths(now, 6); dateFormat = 'MMM yy'; break;
      case '1y': start = subMonths(now, 12); dateFormat = 'MMM yy'; break;
      default: start = subDays(now, 30); dateFormat = 'dd MMM';
    }

    // Validate start
    if (!isValid(start)) start = new Date();

    // starting balances
    const startingAssets = (assets || []).reduce((s, x) => s + safeNumber(x.balance), 0);
    const startingBanks = (banks || []).reduce((s, x) => s + safeNumber(x.balance), 0);
    const startingSavings = (savings || []).reduce((s, x) => s + safeNumber(x.balance), 0);
    const startingDebt = (creditCards || []).reduce((s, x) => s + safeNumber(x.used), 0);
    let startingNetWorth = startingAssets + startingBanks + startingSavings - startingDebt;

    // Group transactions by bucket, but skip txns with invalid/null dates
    const buckets = new Map();
    for (const tx of allTransactions) {
      if (!tx || !tx.date) continue;               // skip null / missing date
      if (!(tx.date instanceof Date) || !isValid(tx.date)) continue; // skip invalid date
      if (tx.date < start) continue;
      const key = format(tx.date, dateFormat);     // safe because we've validated tx.date
      buckets.set(key, (buckets.get(key) || 0) + safeNumber(tx.amount));
    }

    // Build ordered timeline
    const timeline = [];
    if (dateFormat === 'dd MMM') {
      const dayMs = 24 * 60 * 60 * 1000;
      for (let t = +start; t <= +now; t += dayMs) {
        const d = new Date(t);
        const key = format(d, dateFormat);
        const change = buckets.get(key) || 0;
        timeline.push({ date: key, change });
      }
    } else {
      let cur = startOfMonth(start);
      const end = startOfMonth(now);
      while (cur <= end) {
        const key = format(cur, dateFormat);
        const change = buckets.get(key) || 0;
        timeline.push({ date: key, change });
        cur = subMonths(cur, -1);
      }
    }

    // cumulative sums
    const history = [];
    let running = startingNetWorth;
    for (const item of timeline) {
      running += safeNumber(item.change);
      history.push({ date: item.date, netWorth: Math.round(running) });
    }

    if (history.length === 0) {
      const safeStartKey = isValid(start) ? format(start, dateFormat) : format(now, dateFormat);
      return [{ date: safeStartKey, netWorth: Math.round(startingNetWorth) }];
    }
    return history;
  }, [allTransactions, assets, banks, savings, creditCards, timeRange]);

  // Summaries used in header cards
  const totalAssets = useMemo(() => (assets || []).reduce((s, a) => s + safeNumber(a.balance), 0), [assets]);
  const totalBanks = useMemo(() => (banks || []).reduce((s, b) => s + safeNumber(b.balance), 0), [banks]);
  const totalSavings = useMemo(() => (savings || []).reduce((s, sv) => s + safeNumber(sv.balance), 0), [savings]);
  const totalDebt = useMemo(() => (creditCards || []).reduce((s, c) => s + safeNumber(c.used), 0), [creditCards]);
  const netWorth = totalAssets + totalBanks + totalSavings - totalDebt;

  // ----------- UI handlers -----------
  const handleApplyFilter = () => {
    // toggles a state which will trigger fetch (debounced in effect)
    setFilterApplied(true);
  };

  // manual refresh (if needed)
  const handleRefresh = () => {
    setTicker(t => t + 1);
  };

  // Loading skeleton vs spinner: keep your spinner but show per-section fallback if needed
  if (loading && !isApplying) {
    return (
      <div className="dashboard-container">
        <div className="loading-spinner"></div>
        <p>Loading financial data...</p>
      </div>
    );
  }

  // ----------- Render -----------
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

        <button onClick={handleApplyFilter} disabled={isApplying} style={{ opacity: isApplying ? 0.7 : 1 }}>
          {isApplying ? 'Applying...' : 'Apply Filter'}
        </button>

        <button onClick={handleRefresh} style={{ marginLeft: 'auto' }}>Refresh</button>
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
                  <Cell key={`cell-s-${index}`} fill={COLORS[index % COLORS.length]} />
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
                data={assets || []}
                cx="50%"
                cy="50%"
                outerRadius={80}
                fill="#8884d8"
                dataKey="balance"
                nameKey="name"
                label={({ name, percent }) =>
                  `${name}: ${(percent * 100).toFixed(0)}%`}
              >
                {(assets || []).map((entry, index) => (
                  <Cell key={`cell-a-${index}`} fill={COLORS[index % COLORS.length]} />
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
