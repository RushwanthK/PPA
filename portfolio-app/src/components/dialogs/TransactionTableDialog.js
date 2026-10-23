import React from 'react';
import Modal from '../ui/Modal';
import Button from '../ui/Button';
import SearchBar from '../ui/SearchBar';
import DataTable from '../ui/DataTable';
import './TransactionTableDialog.css';

function TransactionTableDialog({
  open,
  title = 'Transactions',
  modalClassName = '',
  transactions = [],
  columns = [],
  loading = false,
  onClose,
  onAddTransaction,
  addTransactionDisabled = false,
  emptyMessage = 'No transactions found.',
  searchText = '',
  searchPlaceholder = 'Search transactions...',
  onSearchChange,
  transactionType = '',
  onTransactionTypeChange,
  startDate = '',
  endDate = '',
  onStartDateChange,
  onEndDateChange,
  amountRange = '',
  onAmountRangeChange,
  onClearFilters,
  transactionTypeOptions = [
    { value: 'income', label: 'Income' },
    { value: 'expense', label: 'Expense' },
  ],
  page = 1,
  totalPages = 1,
  totalTransactions = 0,
  pageSize = 25,
  onPageChange,
  onPageSizeChange,
  error = null,
  onDismissError,
}) {
  const hasFilters = Boolean(
    onSearchChange ||
    onTransactionTypeChange ||
    onStartDateChange ||
    onEndDateChange ||
    onAmountRangeChange
  );
  const hasActiveFilters = Boolean(
    searchText ||
    transactionType ||
    startDate ||
    endDate ||
    amountRange
  );
  const canGoPrevious = page > 1 && !loading;
  const canGoNext = page < totalPages && !loading;

  return (
    <Modal
      open={open}
      title={title}
      onClose={onClose}
      className={`transaction-table-modal ${modalClassName}`.trim()}
    >
      {error && (
        <div className="transaction-table-dialog-error" role="alert">
          <span>{error}</span>

          {onDismissError && (
            <button
              type="button"
              className="transaction-table-dialog-error-dismiss"
              onClick={onDismissError}
              aria-label="Dismiss error"
            >
              ×
            </button>
          )}
        </div>
      )}
      
      <div className="transaction-table-toolbar">
        {hasFilters && (
          <div className="transaction-table-filters">
            {onSearchChange && (
              <div className="transaction-table-search">
                <SearchBar
                  value={searchText}
                  onChange={onSearchChange}
                  placeholder={searchPlaceholder}
                  ariaLabel="Search transactions"
                  disabled={loading}
                />
              </div>
            )}

            {onTransactionTypeChange && (
              <select
                value={transactionType}
                onChange={onTransactionTypeChange}
                aria-label="Filter transactions by type"
                disabled={loading}
                className="transaction-type-filter"
              >
                <option value="">All types</option>
                {transactionTypeOptions.map(option => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            )}

            {onStartDateChange && (
              <label className="transaction-date-filter-group">
                <span>From (IST)</span>
                <input
                  type="date"
                  value={startDate}
                  onChange={onStartDateChange}
                  max={endDate || undefined}
                  aria-label="Filter transactions from date (IST)"
                  disabled={loading}
                  className="transaction-date-filter"
                />
              </label>
            )}

            {onEndDateChange && (
              <label className="transaction-date-filter-group">
                <span>Through (IST)</span>
                <input
                  type="date"
                  value={endDate}
                  onChange={onEndDateChange}
                  min={startDate || undefined}
                  aria-label="Filter transactions through date (IST)"
                  disabled={loading}
                  className="transaction-date-filter"
                />
              </label>
            )}

            {onAmountRangeChange && (
              <select
                value={amountRange}
                onChange={onAmountRangeChange}
                aria-label="Filter transactions by amount range"
                disabled={loading}
                className="transaction-amount-filter"
              >
                <option value="">All amounts</option>
                <option value="under_500">₹0 to &lt;₹500</option>
                <option value="500_1000">₹500 to &lt;₹1,000</option>
                <option value="1000_5000">₹1,000 to &lt;₹5,000</option>
                <option value="5000_10000">₹5,000 to &lt;₹10,000</option>
                <option value="10000_plus">₹10,000+</option>
              </select>
            )}

            {onClearFilters && (
              <div className="transaction-clear-filters">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={onClearFilters}
                  disabled={loading || !hasActiveFilters}
                >
                  Clear Filters
                </Button>
              </div>
            )}
          </div>
        )}

        {onAddTransaction && (
          <Button
            type="button"
            variant="primary"
            onClick={onAddTransaction}
            disabled={addTransactionDisabled}
          >
            Add Transaction
          </Button>
        )}
      </div>

      <DataTable
        columns={columns}
        data={transactions}
        loading={loading}
        emptyMessage={emptyMessage}
      />

      {(totalPages > 0 || totalTransactions > 0) && (
        <div className="transaction-pagination" aria-label="Transaction pagination">
          <div className="transaction-pagination-summary">
            {totalTransactions === 0
              ? 'No transactions'
              : `Showing ${(page - 1) * pageSize + 1}-${Math.min(page * pageSize, totalTransactions)} of ${totalTransactions}`}
          </div>

          <div className="transaction-pagination-controls">
            <select
              value={pageSize}
              onChange={onPageSizeChange}
              aria-label="Transactions per page"
              disabled={loading}
              className="transaction-page-size"
            >
              <option value={25}>25 / page</option>
              <option value={50}>50 / page</option>
              <option value={100}>100 / page</option>
            </select>

            <Button
              type="button"
              variant="secondary"
              onClick={() => onPageChange?.(page - 1)}
              disabled={!canGoPrevious}
            >
              Previous
            </Button>

            <span className="transaction-page-number">
              Page {page} of {Math.max(totalPages, 1)}
            </span>

            <Button
              type="button"
              variant="secondary"
              onClick={() => onPageChange?.(page + 1)}
              disabled={!canGoNext}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}

export default TransactionTableDialog;