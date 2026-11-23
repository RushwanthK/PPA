import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import TransactionTableDialog from './TransactionTableDialog';

const COLUMNS = [
  { key: 'description', label: 'Description' },
  { key: 'amount', label: 'Amount' },
];

const TRANSACTIONS = [
  { id: 1, description: 'Salary', amount: 50000 },
  { id: 2, description: 'Rent', amount: 15000 },
];

// The page-size <select> is always rendered, so give it a no-op handler by
// default (the real pages always pass one).
const BASE_PROPS = {
  open: true,
  title: 'Transactions',
  columns: COLUMNS,
  transactions: TRANSACTIONS,
  onPageSizeChange: () => {},
};

const renderDialog = (props = {}) =>
  render(<TransactionTableDialog {...BASE_PROPS} {...props} />);

// Controlled <select>s are reset by React after the change event, so record
// the value at the moment the handler runs.
const valueRecorder = () => {
  const values = [];
  const handler = jest.fn(event => values.push(event.target.value));
  return { handler, values };
};

describe('TransactionTableDialog', () => {
  test('renders nothing when closed', () => {
    renderDialog({ open: false });

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  test('renders the transactions and the empty message', () => {
    const { rerender } = renderDialog();

    expect(screen.getByText('Salary')).toBeInTheDocument();
    expect(screen.getByText('Rent')).toBeInTheDocument();

    rerender(
      <TransactionTableDialog
        {...BASE_PROPS}
        transactions={[]}
        emptyMessage="Nothing here"
      />
    );
    expect(screen.getByText('Nothing here')).toBeInTheDocument();
  });

  test('shows only the filters whose handlers are provided', () => {
    renderDialog({ onSearchChange: jest.fn() });

    expect(screen.getByRole('searchbox', { name: 'Search transactions' })).toBeInTheDocument();
    expect(
      screen.queryByRole('combobox', { name: 'Filter transactions by type' })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('combobox', { name: 'Filter transactions by amount range' })
    ).not.toBeInTheDocument();
  });

  test('forwards filter changes to their handlers', async () => {
    const typeChange = valueRecorder();
    const amountChange = valueRecorder();
    const onSearchChange = jest.fn();
    const user = userEvent.setup();

    renderDialog({
      onSearchChange,
      onTransactionTypeChange: typeChange.handler,
      onAmountRangeChange: amountChange.handler,
    });

    await user.type(screen.getByRole('searchbox', { name: 'Search transactions' }), 'r');
    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Filter transactions by type' }),
      'expense'
    );
    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Filter transactions by amount range' }),
      '1000_5000'
    );

    expect(onSearchChange).toHaveBeenCalled();
    expect(typeChange.values).toEqual(['expense']);
    expect(amountChange.values).toEqual(['1000_5000']);
  });

  test('offers the five backend amount bands', () => {
    renderDialog({ onAmountRangeChange: jest.fn() });

    const values = Array.from(
      screen.getByRole('combobox', { name: 'Filter transactions by amount range' }).options
    ).map(option => option.value);

    expect(values).toEqual([
      '',
      'under_500',
      '500_1000',
      '1000_5000',
      '5000_10000',
      '10000_plus',
    ]);
  });

  test('"Clear Filters" is disabled until a filter is active', async () => {
    const onClearFilters = jest.fn();
    const user = userEvent.setup();

    const { rerender } = renderDialog({
      onSearchChange: jest.fn(),
      onClearFilters,
    });

    expect(screen.getByRole('button', { name: 'Clear Filters' })).toBeDisabled();

    rerender(
      <TransactionTableDialog
        {...BASE_PROPS}
        onSearchChange={jest.fn()}
        onClearFilters={onClearFilters}
        transactionType="income"
      />
    );

    const clear = screen.getByRole('button', { name: 'Clear Filters' });
    expect(clear).toBeEnabled();
    await user.click(clear);
    expect(onClearFilters).toHaveBeenCalledTimes(1);
  });

  describe('cursor pagination', () => {
    test('Next follows hasMore and Previous is disabled on page 1', async () => {
      const onPageChange = jest.fn();
      const user = userEvent.setup();

      renderDialog({ cursorPagination: true, page: 1, hasMore: true, onPageChange });

      expect(screen.getByText('Showing 2 transactions on this page')).toBeInTheDocument();
      expect(screen.getByText('Page 1')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();

      await user.click(screen.getByRole('button', { name: 'Next' }));
      expect(onPageChange).toHaveBeenCalledWith(2);
    });

    test('Next is disabled on the last page and Previous goes back', async () => {
      const onPageChange = jest.fn();
      const user = userEvent.setup();

      renderDialog({ cursorPagination: true, page: 3, hasMore: false, onPageChange });

      expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();
      await user.click(screen.getByRole('button', { name: 'Previous' }));
      expect(onPageChange).toHaveBeenCalledWith(2);
    });

    test('both buttons are disabled while loading', () => {
      renderDialog({ cursorPagination: true, page: 2, hasMore: true, loading: true });

      expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
      expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();
    });
  });

  test('legacy page-number pagination shows the row range and total', () => {
    renderDialog({ page: 2, totalPages: 3, totalTransactions: 60, pageSize: 25 });

    expect(screen.getByText('Showing 26-50 of 60')).toBeInTheDocument();
    expect(screen.getByText('Page 2 of 3')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Next' })).toBeEnabled();
  });

  test('page-size changes are forwarded', async () => {
    const pageSizeChange = valueRecorder();
    const user = userEvent.setup();

    renderDialog({ cursorPagination: true, onPageSizeChange: pageSizeChange.handler });

    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Transactions per page' }),
      '50'
    );
    expect(pageSizeChange.values).toEqual(['50']);
  });

  test('shows a dismissible error', async () => {
    const onDismissError = jest.fn();
    const user = userEvent.setup();

    renderDialog({ error: 'Failed to fetch transactions', onDismissError });

    expect(screen.getByRole('alert')).toHaveTextContent('Failed to fetch transactions');
    await user.click(screen.getByRole('button', { name: 'Dismiss error' }));
    expect(onDismissError).toHaveBeenCalledTimes(1);
  });

  test('Add Transaction button calls its handler and respects disabled', async () => {
    const onAddTransaction = jest.fn();
    const user = userEvent.setup();

    const { rerender } = renderDialog({ onAddTransaction });

    await user.click(screen.getByRole('button', { name: 'Add Transaction' }));
    expect(onAddTransaction).toHaveBeenCalledTimes(1);

    rerender(
      <TransactionTableDialog
        {...BASE_PROPS}
        onAddTransaction={onAddTransaction}
        addTransactionDisabled
      />
    );
    expect(screen.getByRole('button', { name: 'Add Transaction' })).toBeDisabled();
  });
});
