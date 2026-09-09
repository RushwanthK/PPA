import React from 'react';
import Modal from '../ui/Modal';
import Button from '../ui/Button';
import SearchBar from '../ui/SearchBar';
import DataTable from '../ui/DataTable';

function TransactionTableDialog({
  open,
  title = 'Transactions',
  transactions = [],
  columns = [],
  loading = false,
  onClose,
  onAddTransaction,
  addTransactionDisabled = false,
  emptyMessage = 'No transactions found.',
  searchText = '',
  onSearchChange,
  transactionType = '',
  onTransactionTypeChange,
  page = 1,
  totalPages = 1,
  totalTransactions = 0,
  pageSize = 25,
  onPageChange,
  onPageSizeChange,
}) {
  const hasFilters = Boolean(onSearchChange || onTransactionTypeChange);
  const canGoPrevious = page > 1 && !loading;
  const canGoNext = page < totalPages && !loading;

  return (
    <Modal
      open={open}
      title={title}
      onClose={onClose}
      className="transaction-table-modal"
    >
      <div className="transaction-table-toolbar">
        {hasFilters && (
          <div className="transaction-table-filters">
            {onSearchChange && (
              <SearchBar
                value={searchText}
                onChange={onSearchChange}
                placeholder="Search transactions..."
                ariaLabel="Search transactions"
                disabled={loading}
              />
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
                <option value="income">Income</option>
                <option value="expense">Expense</option>
              </select>
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
