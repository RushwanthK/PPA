import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import Bank from './bank';
import {
  addBankTransaction,
  createBank,
  deleteBank,
  exportUserTransactionsExcel,
  exportUserTransactionsPdf,
  getBankTransactions,
  getBanks,
  updateBank,
} from '../services/api';

// The page talks to the backend only through services/api, so mocking that
// module lets these tests drive the real page UI without a server.
jest.mock('../services/api', () => ({
  getBanks: jest.fn(),
  createBank: jest.fn(),
  updateBank: jest.fn(),
  deleteBank: jest.fn(),
  addBankTransaction: jest.fn(),
  getBankTransactions: jest.fn(),
  exportUserTransactionsExcel: jest.fn(),
  exportUserTransactionsPdf: jest.fn(),
}));

jest.mock('../AuthContext', () => ({
  useAuth: () => ({ user: { id: 1, name: 'tester' } }),
}));

const BANKS = [
  { id: 1, name: 'HDFC', balance: 1000 },
  { id: 2, name: 'SBI', balance: 0 },
];

const tx = (id, description, amount = 100) => ({
  id,
  date: '2026-11-01 10:00:00',
  transaction_type: 'expense',
  amount,
  description,
  category: 'Misc',
  bank_balance_after: 900,
});

const rowFor = name => screen.getByRole('cell', { name }).closest('tr');

const renderBankPage = async () => {
  const user = userEvent.setup();
  render(<Bank />);
  await screen.findByRole('heading', { name: 'Banks' });
  await screen.findByRole('cell', { name: 'HDFC' });
  return user;
};

describe('Bank page', () => {
  beforeEach(() => {
    getBanks.mockResolvedValue({ data: BANKS.map(b => ({ ...b })) });
    getBankTransactions.mockResolvedValue({
      transactions: [],
      has_more: false,
      next_cursor: null,
    });
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.clearAllMocks();
    jest.restoreAllMocks();
  });

  test('lists banks with balances and a totals row', async () => {
    await renderBankPage();

    expect(within(rowFor('HDFC')).getByText('Rs. 1000.00')).toBeInTheDocument();
    expect(within(rowFor('SBI')).getByText('Rs. 0.00')).toBeInTheDocument();
    expect(within(rowFor('Totals')).getByText('Rs. 1000.00')).toBeInTheDocument();
  });

  test('shows the error when banks fail to load', async () => {
    getBanks.mockRejectedValue(new Error('Failed to fetch banks'));

    render(<Bank />);

    expect(await screen.findByText('Failed to fetch banks')).toBeInTheDocument();
    expect(screen.getByText('No banks found')).toBeInTheDocument();
  });

  test('filters the bank list by name', async () => {
    const user = await renderBankPage();

    await user.type(screen.getByRole('searchbox', { name: 'Search banks by name' }), 'sb');

    expect(screen.queryByRole('cell', { name: 'HDFC' })).not.toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'SBI' })).toBeInTheDocument();
  });

  test('creates a new bank', async () => {
    createBank.mockResolvedValue({ bank: { id: 3, name: 'ICICI', balance: 0 } });
    const user = await renderBankPage();

    await user.click(screen.getByRole('button', { name: 'Add Bank' }));
    await user.type(screen.getByLabelText('Bank Name:'), '  ICICI  ');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    expect(createBank).toHaveBeenCalledWith({ name: 'ICICI' });
    expect(await screen.findByRole('cell', { name: 'ICICI' })).toBeInTheDocument();
    expect(screen.getByText('Bank created successfully!')).toBeInTheDocument();
  });

  describe('editing a bank', () => {
    test('renames a bank with the form pre-filled', async () => {
      // Mirrors the real PUT /banks/<id> response.
      updateBank.mockResolvedValue({
        message: 'Bank updated successfully',
        bank: { id: 1, name: 'HDFC Salary', user_id: 1, balance: 1000 },
      });
      const user = await renderBankPage();

      await user.click(within(rowFor('HDFC')).getByRole('button', { name: 'Edit' }));
      const dialog = screen.getByRole('dialog', { name: 'Edit Bank' });
      const name = within(dialog).getByLabelText('Bank Name:');
      expect(name).toHaveValue('HDFC');

      await user.clear(name);
      await user.type(name, '  HDFC Salary ');
      await user.click(within(dialog).getByRole('button', { name: 'Update' }));

      expect(updateBank).toHaveBeenCalledWith(1, { name: 'HDFC Salary' });
      expect(await screen.findByText('Bank updated successfully!')).toBeInTheDocument();
      expect(rowFor('HDFC Salary')).toHaveTextContent('Rs. 1000.00');
      expect(screen.queryByRole('cell', { name: 'HDFC' })).not.toBeInTheDocument();
    });

    test('shows the backend error and keeps the old name on failure', async () => {
      updateBank.mockRejectedValue(new Error('Bank name already exists'));
      const user = await renderBankPage();

      await user.click(within(rowFor('HDFC')).getByRole('button', { name: 'Edit' }));
      const dialog = screen.getByRole('dialog', { name: 'Edit Bank' });
      const name = within(dialog).getByLabelText('Bank Name:');
      await user.clear(name);
      await user.type(name, 'SBI');
      await user.click(within(dialog).getByRole('button', { name: 'Update' }));

      expect(await within(dialog).findByRole('alert')).toHaveTextContent(
        'Bank name already exists'
      );
      expect(screen.getByRole('cell', { name: 'HDFC' })).toBeInTheDocument();
    });
  });

  describe('adding a transaction', () => {
    test('submits the transaction and updates the bank balance', async () => {
      addBankTransaction.mockResolvedValue({
        balance: 750,
        transaction: tx(10, 'Groceries', 250),
      });
      const user = await renderBankPage();

      await user.click(
        within(rowFor('HDFC')).getByRole('button', { name: 'Add Transaction' })
      );

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveTextContent('Add Transaction - HDFC');

      await user.selectOptions(within(dialog).getByLabelText('Transaction Type:'), 'expense');
      await user.type(within(dialog).getByLabelText('Amount:'), '250');
      await user.type(within(dialog).getByLabelText('Description:'), 'Groceries');
      await user.type(within(dialog).getByLabelText('Category:'), 'Food');
      await user.click(within(dialog).getByRole('button', { name: 'Submit' }));

      expect(addBankTransaction).toHaveBeenCalledWith('1', {
        amount: 250,
        type: 'expense',
        description: 'Groceries',
        category: 'Food',
      });

      expect(await screen.findByText('Transaction added successfully!')).toBeInTheDocument();
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      expect(within(rowFor('HDFC')).getByText('Rs. 750.00')).toBeInTheDocument();
    });

    test('keeps the dialog open and shows the backend error on failure', async () => {
      addBankTransaction.mockRejectedValue(new Error('Insufficient balance'));
      const user = await renderBankPage();

      await user.click(
        within(rowFor('SBI')).getByRole('button', { name: 'Add Transaction' })
      );
      const dialog = screen.getByRole('dialog');

      await user.selectOptions(within(dialog).getByLabelText('Transaction Type:'), 'expense');
      await user.type(within(dialog).getByLabelText('Amount:'), '500');
      await user.click(within(dialog).getByRole('button', { name: 'Submit' }));

      expect(await within(dialog).findByRole('alert')).toHaveTextContent(
        'Insufficient balance'
      );
      expect(within(rowFor('SBI')).getByText('Rs. 0.00')).toBeInTheDocument();
    });
  });

  describe('transaction history', () => {
    test('loads the first page with default filters and shows rows', async () => {
      getBankTransactions.mockResolvedValue({
        transactions: [tx(1, 'Rent', 15000)],
        has_more: false,
        next_cursor: null,
      });
      const user = await renderBankPage();

      await user.click(
        within(rowFor('HDFC')).getByRole('button', { name: 'View Transactions' })
      );

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveTextContent('Transactions for HDFC');
      expect(await within(dialog).findByText('Rent')).toBeInTheDocument();
      expect(within(dialog).getByText('Rs. 15000.00')).toBeInTheDocument();

      expect(getBankTransactions).toHaveBeenCalledWith(1, {
        cursor: undefined,
        page_size: 25,
        search: '',
        type: '',
        start_date: undefined,
        end_date: undefined,
        amount_range: undefined,
      });
    });

    test('moves through pages using the cursor returned by the backend', async () => {
      getBankTransactions
        .mockResolvedValueOnce({
          transactions: [tx(1, 'Page one row')],
          has_more: true,
          next_cursor: 'cursor-page-2',
        })
        .mockResolvedValueOnce({
          transactions: [tx(2, 'Page two row')],
          has_more: false,
          next_cursor: null,
        })
        .mockResolvedValueOnce({
          transactions: [tx(1, 'Page one row')],
          has_more: true,
          next_cursor: 'cursor-page-2',
        });

      const user = await renderBankPage();
      await user.click(
        within(rowFor('HDFC')).getByRole('button', { name: 'View Transactions' })
      );
      const dialog = screen.getByRole('dialog');

      await within(dialog).findByText('Page one row');
      await user.click(within(dialog).getByRole('button', { name: 'Next' }));

      expect(await within(dialog).findByText('Page two row')).toBeInTheDocument();
      expect(within(dialog).getByText('Page 2')).toBeInTheDocument();
      expect(getBankTransactions).toHaveBeenLastCalledWith(
        1,
        expect.objectContaining({ cursor: 'cursor-page-2' })
      );
      expect(within(dialog).getByRole('button', { name: 'Next' })).toBeDisabled();

      await user.click(within(dialog).getByRole('button', { name: 'Previous' }));

      expect(await within(dialog).findByText('Page one row')).toBeInTheDocument();
      expect(getBankTransactions).toHaveBeenLastCalledWith(
        1,
        expect.objectContaining({ cursor: undefined })
      );
    });

    test('changing a filter sends it to the backend and restarts from page 1', async () => {
      getBankTransactions.mockResolvedValue({
        transactions: [tx(1, 'Row')],
        has_more: true,
        next_cursor: 'cursor-page-2',
      });

      const user = await renderBankPage();
      await user.click(
        within(rowFor('HDFC')).getByRole('button', { name: 'View Transactions' })
      );
      const dialog = screen.getByRole('dialog');
      await within(dialog).findByText('Row');

      await user.click(within(dialog).getByRole('button', { name: 'Next' }));
      await within(dialog).findByText('Page 2');

      await user.selectOptions(
        within(dialog).getByRole('combobox', { name: 'Filter transactions by type' }),
        'expense'
      );
      await user.selectOptions(
        within(dialog).getByRole('combobox', { name: 'Filter transactions by amount range' }),
        '1000_5000'
      );

      await waitFor(() => {
        expect(getBankTransactions).toHaveBeenLastCalledWith(
          1,
          expect.objectContaining({
            cursor: undefined,
            type: 'expense',
            amount_range: '1000_5000',
          })
        );
      });
      expect(within(dialog).getByText('Page 1')).toBeInTheDocument();
    });

    test('changing rows per page restarts from page 1 with the new size', async () => {
      getBankTransactions.mockResolvedValue({
        transactions: [tx(1, 'Row')],
        has_more: true,
        next_cursor: 'cursor-page-2',
      });
      const user = await renderBankPage();
      await user.click(
        within(rowFor('HDFC')).getByRole('button', { name: 'View Transactions' })
      );
      const dialog = screen.getByRole('dialog');
      await within(dialog).findByText('Row');

      await user.click(within(dialog).getByRole('button', { name: 'Next' }));
      await within(dialog).findByText('Page 2');

      await user.selectOptions(
        within(dialog).getByRole('combobox', { name: 'Transactions per page' }),
        '50'
      );

      await waitFor(() => {
        expect(getBankTransactions).toHaveBeenLastCalledWith(
          1,
          expect.objectContaining({ page_size: 50, cursor: undefined })
        );
      });
      expect(within(dialog).getByText('Page 1')).toBeInTheDocument();
    });

    test('debounces the search box before calling the backend', async () => {
      const user = await renderBankPage();
      await user.click(
        within(rowFor('HDFC')).getByRole('button', { name: 'View Transactions' })
      );
      const dialog = screen.getByRole('dialog');
      await waitFor(() => expect(getBankTransactions).toHaveBeenCalledTimes(1));

      await user.type(
        within(dialog).getByRole('searchbox', { name: 'Search transactions' }),
        'rent'
      );

      await waitFor(() => {
        expect(getBankTransactions).toHaveBeenLastCalledWith(
          1,
          expect.objectContaining({ search: 'rent' })
        );
      });

      // No request was sent for the partial terms "r", "re" or "ren".
      const searchedTerms = getBankTransactions.mock.calls.map(([, params]) => params.search);
      expect(searchedTerms).not.toEqual(expect.arrayContaining(['r', 're', 'ren']));
    });

    test('shows an error inside the dialog when loading fails', async () => {
      getBankTransactions.mockRejectedValue(new Error('Invalid cursor'));
      const user = await renderBankPage();

      await user.click(
        within(rowFor('HDFC')).getByRole('button', { name: 'View Transactions' })
      );

      expect(
        await within(screen.getByRole('dialog')).findByRole('alert')
      ).toHaveTextContent('Invalid cursor');
    });
  });

  describe('deleting a bank', () => {
    test('blocks deletion of a bank with a non-zero balance', async () => {
      const user = await renderBankPage();

      await user.click(within(rowFor('HDFC')).getByRole('button', { name: 'Delete' }));

      expect(screen.getByRole('alert')).toHaveTextContent(
        'Cannot delete "HDFC" because its current balance is Rs. 1000.00'
      );

      await user.click(screen.getByRole('button', { name: 'Delete Without Backup' }));
      expect(deleteBank).not.toHaveBeenCalled();
    });

    test('deletes a zero-balance bank after confirmation', async () => {
      deleteBank.mockResolvedValue({});
      const user = await renderBankPage();

      await user.click(within(rowFor('SBI')).getByRole('button', { name: 'Delete' }));
      expect(screen.getByRole('heading', { name: 'Delete Bank Account' })).toBeInTheDocument();

      await user.click(screen.getByRole('button', { name: 'Delete Without Backup' }));

      expect(deleteBank).toHaveBeenCalledWith(2);
      expect(await screen.findByText('Bank deleted successfully!')).toBeInTheDocument();
      expect(screen.queryByRole('cell', { name: 'SBI' })).not.toBeInTheDocument();
    });

    test('explains when a bank cannot be deleted because of linked savings', async () => {
      deleteBank.mockRejectedValue(
        new Error('Cannot delete bank with linked savings accounts')
      );
      const user = await renderBankPage();

      await user.click(within(rowFor('SBI')).getByRole('button', { name: 'Delete' }));
      await user.click(screen.getByRole('button', { name: 'Delete Without Backup' }));

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Cannot delete bank because it has linked savings accounts. Please remove all linked savings accounts first.'
      );
      expect(screen.getByRole('cell', { name: 'SBI' })).toBeInTheDocument();
    });

    describe('backup before deleting', () => {
      beforeEach(() => {
        // jsdom does not implement object URLs or file downloads.
        window.URL.createObjectURL = jest.fn(() => 'blob:backup');
        window.URL.revokeObjectURL = jest.fn();
        jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
      });

      test.each([
        ['Download Excel', 'excel', /^bank_transactions_backup_\d{4}-\d{2}-\d{2}\.xlsx$/],
        ['Download PDF', 'pdf', /^bank_transactions_backup_\d{4}-\d{2}-\d{2}\.pdf$/],
      ])('%s exports bank transactions only, then allows deleting', async (
        buttonName,
        format,
        filenamePattern
      ) => {
        const exportFn =
          format === 'excel' ? exportUserTransactionsExcel : exportUserTransactionsPdf;
        exportFn.mockResolvedValue({ data: new Blob(['backup']) });
        const appendSpy = jest.spyOn(document.body, 'appendChild');
        const user = await renderBankPage();

        await user.click(within(rowFor('SBI')).getByRole('button', { name: 'Delete' }));
        await user.click(screen.getByRole('button', { name: buttonName }));

        expect(exportFn).toHaveBeenCalledWith(1, ['banks']);
        expect(
          await screen.findByText('Bank transaction backup downloaded successfully.')
        ).toBeInTheDocument();

        const link = appendSpy.mock.calls
          .map(([node]) => node)
          .find(node => node.tagName === 'A');
        expect(link.download).toMatch(filenamePattern);
        expect(window.URL.revokeObjectURL).toHaveBeenCalledWith('blob:backup');

        // Downloading a backup must never delete the bank by itself.
        expect(deleteBank).not.toHaveBeenCalled();
        expect(screen.getByRole('button', { name: 'Delete Bank' })).toBeInTheDocument();
      });

      test('a failed backup shows an error and deletes nothing', async () => {
        exportUserTransactionsExcel.mockRejectedValue(new Error('Network Error'));
        const user = await renderBankPage();

        await user.click(within(rowFor('SBI')).getByRole('button', { name: 'Delete' }));
        await user.click(screen.getByRole('button', { name: 'Download Excel' }));

        expect(await screen.findByRole('alert')).toHaveTextContent('Network Error');
        expect(deleteBank).not.toHaveBeenCalled();
        expect(
          screen.getByRole('button', { name: 'Delete Without Backup' })
        ).toBeInTheDocument();
      });
    });

    test('cancel closes the dialog without deleting', async () => {
      const user = await renderBankPage();

      await user.click(within(rowFor('SBI')).getByRole('button', { name: 'Delete' }));
      await user.click(screen.getByRole('button', { name: 'Cancel' }));

      expect(
        screen.queryByRole('heading', { name: 'Delete Bank Account' })
      ).not.toBeInTheDocument();
      expect(deleteBank).not.toHaveBeenCalled();
    });
  });
});
