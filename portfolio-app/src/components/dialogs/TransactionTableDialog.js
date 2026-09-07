import React from 'react';
import Modal from '../ui/Modal';
import Button from '../ui/Button';
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
}) {
  return (
    <Modal
      open={open}
      title={title}
      onClose={onClose}
      className="transaction-table-modal"
    >
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

      <DataTable
        columns={columns}
        data={transactions}
        loading={loading}
        emptyMessage={emptyMessage}
      />
    </Modal>
  );
}

export default TransactionTableDialog;
