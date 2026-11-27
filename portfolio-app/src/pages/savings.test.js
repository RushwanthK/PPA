import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import Savings from './savings';
import {
  addSavingTransaction,
  createSaving,
  deleteSaving,
  exportUserTransactionsExcel,
  getBankBalance,
  getBanksByUser,
  getSavings,
  getSavingTransactions,
  updateSaving,
} from '../services/api';

// The page talks to the backend only through services/api, so mocking that
// module lets these tests drive the real page UI without a server. Response
// shapes mirror app/savings/savings_routes.py and app/banks/bank_routes.py.
jest.mock('../services/api', () => ({
  getSavings: jest.fn(),
  createSaving: jest.fn(),
  updateSaving: jest.fn(),
  deleteSaving: jest.fn(),
  addSavingTransaction: jest.fn(),
  getSavingTransactions: jest.fn(),
  getBanksByUser: jest.fn(),
  getBankBalance: jest.fn(),
  exportUserTransactionsExcel: jest.fn(),
  exportUserTransactionsPdf: jest.fn(),
}));

jest.mock('../AuthContext', () => ({
  useAuth: () => ({ user: { id: 1, name: 'tester' } }),
}));

const BANKS = [
  { id: 10, name: 'HDFC' },
  { id: 20, name: 'SBI' },
];

const EMERGENCY = { id: 1, name: 'Emergency Fund', user_id: 1, bank_id: 10, bank_name: 'HDFC', balance: 5000 };
const VACATION = { id: 2, name: 'Vacation', user_id: 1, bank_id: 20, bank_name: 'SBI', balance: 0 };

const rowFor = name => screen.getByRole('cell', { name }).closest('tr');
const rowValues = name =>
  within(rowFor(name)).getAllByRole('cell').slice(0, 3).map(cell => cell.textContent);

const renderPage = async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><Savings /></MemoryRouter>);
  await screen.findByRole('heading', { name: 'Savings Accounts' });
  await screen.findByRole('cell', { name: 'Emergency Fund' });
  return user;
};

describe('Savings page', () => {
  beforeEach(() => {
    getSavings.mockResolvedValue([{ ...EMERGENCY }, { ...VACATION }]);
    getBanksByUser.mockResolvedValue(BANKS.map(bank => ({ ...bank })));
    getBankBalance.mockResolvedValue({ id: 10, name: 'HDFC', balance: 80000 });
    getSavingTransactions.mockResolvedValue({
      transactions: [],
      total: 0,
      total_pages: 0,
      page: 1,
    });
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.clearAllMocks();
    jest.restoreAllMocks();
  });

  describe('savings list', () => {
    test('shows each account with its balance and linked bank, plus a total', async () => {
      await renderPage();

      expect(rowValues('Emergency Fund')).toEqual(['Emergency Fund', 'Rs. 5000.00', 'HDFC']);
      expect(rowValues('Vacation')).toEqual(['Vacation', 'Rs. 0.00', 'SBI']);
      expect(within(rowFor('Totals')).getByText('Rs. 5000.00')).toBeInTheDocument();
    });

    test('shows N/A when the linked bank is unknown', async () => {
      getSavings.mockResolvedValue([{ ...EMERGENCY, bank_id: 99 }]);
      await renderPage();

      expect(rowValues('Emergency Fund')[2]).toBe('N/A');
    });

    test('search filters by account name', async () => {
      const user = await renderPage();

      await user.type(
        screen.getByRole('searchbox', { name: 'Search savings accounts by name' }),
        'vac'
      );

      expect(screen.queryByRole('cell', { name: 'Emergency Fund' })).not.toBeInTheDocument();
      expect(screen.getByRole('cell', { name: 'Vacation' })).toBeInTheDocument();
      expect(within(rowFor('Totals')).getByText('Rs. 0.00')).toBeInTheDocument();
    });

    test('sorts by balance numerically', async () => {
      getSavings.mockResolvedValue([
        { ...EMERGENCY, name: 'Big', balance: 100000 },
        { ...VACATION, name: 'Small', balance: 9000 },
      ]);
      const user = userEvent.setup();
      render(<MemoryRouter><Savings /></MemoryRouter>);
      await screen.findByRole('cell', { name: 'Big' });

      await user.click(screen.getByRole('columnheader', { name: 'Balance' }));

      const firstName = within(screen.getAllByRole('row')[1]).getAllByRole('cell')[0];
      expect(firstName).toHaveTextContent('Small');
    });

    test('shows the error when loading fails', async () => {
      getSavings.mockRejectedValue(new Error('Failed to fetch savings: boom'));

      render(<MemoryRouter><Savings /></MemoryRouter>);

      expect(await screen.findByText('Failed to fetch savings: boom')).toBeInTheDocument();
      expect(screen.getByText('No savings accounts found')).toBeInTheDocument();
    });
  });

  describe('creating and editing accounts', () => {
    test('creates an account linked to the chosen bank', async () => {
      createSaving.mockResolvedValue({
        message: 'Saving account created!',
        saving: { id: 3, name: 'House', user_id: 1, bank_id: 20, balance: 0 },
      });
      const user = await renderPage();

      await user.click(screen.getByRole('button', { name: 'Add Savings' }));
      const dialog = screen.getByRole('dialog', { name: 'Add Savings Account' });

      await user.type(within(dialog).getByLabelText('Account Name:'), '  House  ');
      await user.selectOptions(within(dialog).getByLabelText('Bank:'), 'SBI');
      await user.click(within(dialog).getByRole('button', { name: 'Save' }));

      expect(createSaving).toHaveBeenCalledWith({ name: 'House', bank_id: 20 });
      expect(await screen.findByRole('cell', { name: 'House' })).toBeInTheDocument();
      expect(rowValues('House')).toEqual(['House', 'Rs. 0.00', 'SBI']);
    });

    test('shows the backend error and keeps the form open when create fails', async () => {
      createSaving.mockRejectedValue(
        new Error('Failed to create saving: Saving account name already exists')
      );
      const user = await renderPage();

      await user.click(screen.getByRole('button', { name: 'Add Savings' }));
      const dialog = screen.getByRole('dialog', { name: 'Add Savings Account' });
      await user.type(within(dialog).getByLabelText('Account Name:'), 'Vacation');
      await user.selectOptions(within(dialog).getByLabelText('Bank:'), 'HDFC');
      await user.click(within(dialog).getByRole('button', { name: 'Save' }));

      expect(await within(dialog).findByRole('alert')).toHaveTextContent(
        'Saving account name already exists'
      );
    });

    test('renaming an account does not ask about moving money', async () => {
      updateSaving.mockResolvedValue({
        message: 'Saving account updated successfully',
        saving: { ...EMERGENCY, name: 'Rainy Day' },
      });
      const confirmSpy = jest.spyOn(window, 'confirm');
      const user = await renderPage();

      await user.click(within(rowFor('Emergency Fund')).getByRole('button', { name: 'Edit' }));
      const dialog = screen.getByRole('dialog', { name: 'Edit Savings Account' });
      expect(within(dialog).getByLabelText('Bank:')).toHaveValue('10');

      const name = within(dialog).getByLabelText('Account Name:');
      await user.clear(name);
      await user.type(name, 'Rainy Day');
      await user.click(within(dialog).getByRole('button', { name: 'Update' }));

      expect(confirmSpy).not.toHaveBeenCalled();
      expect(updateSaving).toHaveBeenCalledWith(1, { name: 'Rainy Day', bank_id: 10 });
      expect(await screen.findByRole('cell', { name: 'Rainy Day' })).toBeInTheDocument();
    });

    test('moving a funded account to another bank warns and asks for confirmation', async () => {
      updateSaving.mockResolvedValue({
        message: 'Saving account updated successfully',
        saving: { ...EMERGENCY, bank_id: 20 },
      });
      const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(true);
      const user = await renderPage();

      await user.click(within(rowFor('Emergency Fund')).getByRole('button', { name: 'Edit' }));
      const dialog = screen.getByRole('dialog', { name: 'Edit Savings Account' });
      await user.selectOptions(within(dialog).getByLabelText('Bank:'), 'SBI');

      expect(dialog).toHaveTextContent(
        'Warning: This account has a balance of Rs. 5000.00. Changing the linked bank will transfer this amount between banks.'
      );

      await user.click(within(dialog).getByRole('button', { name: 'Update' }));

      expect(confirmSpy).toHaveBeenCalledWith(
        expect.stringContaining('balance of Rs. 5000.00')
      );
      expect(updateSaving).toHaveBeenCalledWith(1, { name: 'Emergency Fund', bank_id: 20 });
      await waitFor(() => {
        expect(rowValues('Emergency Fund')[2]).toBe('SBI');
      });
    });

    test('declining the bank-change confirmation sends nothing', async () => {
      jest.spyOn(window, 'confirm').mockReturnValue(false);
      const user = await renderPage();

      await user.click(within(rowFor('Emergency Fund')).getByRole('button', { name: 'Edit' }));
      const dialog = screen.getByRole('dialog', { name: 'Edit Savings Account' });
      await user.selectOptions(within(dialog).getByLabelText('Bank:'), 'SBI');
      await user.click(within(dialog).getByRole('button', { name: 'Update' }));

      expect(updateSaving).not.toHaveBeenCalled();
      expect(rowValues('Emergency Fund')[2]).toBe('HDFC');
    });

    test('an empty account can change bank without a confirmation', async () => {
      updateSaving.mockResolvedValue({
        message: 'Saving account updated successfully',
        saving: { ...VACATION, bank_id: 10 },
      });
      const confirmSpy = jest.spyOn(window, 'confirm');
      const user = await renderPage();

      await user.click(within(rowFor('Vacation')).getByRole('button', { name: 'Edit' }));
      const dialog = screen.getByRole('dialog', { name: 'Edit Savings Account' });
      await user.selectOptions(within(dialog).getByLabelText('Bank:'), 'HDFC');

      expect(dialog).not.toHaveTextContent('Warning:');
      await user.click(within(dialog).getByRole('button', { name: 'Update' }));

      expect(confirmSpy).not.toHaveBeenCalled();
      expect(updateSaving).toHaveBeenCalledWith(2, { name: 'Vacation', bank_id: 10 });
    });
  });

  describe('deposits and withdrawals', () => {
    const openTransactionForm = async (user, name) => {
      await user.click(within(rowFor(name)).getByRole('button', { name: 'Add Transaction' }));
      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveTextContent(`Add Transaction - ${name}`);
      return dialog;
    };

    test('shows the linked bank balance and explains the money movement', async () => {
      const user = await renderPage();

      const dialog = await openTransactionForm(user, 'Emergency Fund');

      expect(getBankBalance).toHaveBeenCalledWith(10);
      expect(await within(dialog).findByText('Rs. 80000.00')).toBeInTheDocument();
      expect(dialog).toHaveTextContent('HDFC Balance:');
      expect(dialog).toHaveTextContent('Deposits will deduct the amount from this bank account.');

      await user.selectOptions(within(dialog).getByLabelText('Transaction Type:'), 'withdrawal');
      expect(dialog).toHaveTextContent('Withdrawals will add the amount back to this bank account.');
    });

    test('shows a message when the bank balance cannot be loaded', async () => {
      getBankBalance.mockRejectedValue(new Error('Bank not found'));
      const user = await renderPage();

      const dialog = await openTransactionForm(user, 'Emergency Fund');

      expect(await within(dialog).findByText('Bank not found')).toBeInTheDocument();
      expect(dialog).not.toHaveTextContent('Deposits will deduct');
    });

    test('a deposit sends a positive amount and updates the savings balance', async () => {
      addSavingTransaction.mockResolvedValue({
        message: 'Transaction added',
        saving_balance: 7500,
        bank_balance: 77500,
      });
      const user = await renderPage();

      const dialog = await openTransactionForm(user, 'Emergency Fund');
      await user.type(within(dialog).getByLabelText('Amount:'), '2500');
      await user.type(within(dialog).getByLabelText('Description:'), 'Monthly');
      await user.type(within(dialog).getByLabelText('Category:'), 'Goal');
      await user.click(within(dialog).getByRole('button', { name: 'Submit' }));

      expect(addSavingTransaction).toHaveBeenCalledWith('1', {
        amount: 2500,
        type: 'deposit',
        description: 'Monthly',
        category: 'Goal',
      });
      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
      expect(rowValues('Emergency Fund')[1]).toBe('Rs. 7500.00');
      expect(within(rowFor('Totals')).getByText('Rs. 7500.00')).toBeInTheDocument();
    });

    test('a withdrawal sends the withdrawal type', async () => {
      addSavingTransaction.mockResolvedValue({
        message: 'Transaction added',
        saving_balance: 4000,
        bank_balance: 81000,
      });
      const user = await renderPage();

      const dialog = await openTransactionForm(user, 'Emergency Fund');
      await user.selectOptions(within(dialog).getByLabelText('Transaction Type:'), 'withdrawal');
      await user.type(within(dialog).getByLabelText('Amount:'), '1000');
      await user.click(within(dialog).getByRole('button', { name: 'Submit' }));

      expect(addSavingTransaction).toHaveBeenCalledWith(
        '1',
        expect.objectContaining({ amount: 1000, type: 'withdrawal' })
      );
      await waitFor(() => {
        expect(rowValues('Emergency Fund')[1]).toBe('Rs. 4000.00');
      });
    });

    test('shows the backend error (e.g. insufficient bank balance) and keeps the balance', async () => {
      addSavingTransaction.mockRejectedValue(
        new Error('Failed to add saving transaction: Insufficient bank balance')
      );
      const user = await renderPage();

      const dialog = await openTransactionForm(user, 'Vacation');
      await user.type(within(dialog).getByLabelText('Amount:'), '999999');
      await user.click(within(dialog).getByRole('button', { name: 'Submit' }));

      expect(await within(dialog).findByRole('alert')).toHaveTextContent(
        'Insufficient bank balance'
      );
      expect(rowValues('Vacation')[1]).toBe('Rs. 0.00');
    });
  });

  describe('transaction history', () => {
    const openHistory = async (user, name = 'Emergency Fund') => {
      await user.click(within(rowFor(name)).getByRole('button', { name: 'View Transactions' }));
      return screen.getByRole('dialog');
    };

    test('loads page 1 and shows the transactions', async () => {
      getSavingTransactions.mockResolvedValue({
        transactions: [
          {
            id: 1,
            date: '2026-11-01 10:00:00',
            transaction_type: 'deposit',
            amount: 5000,
            description: 'Opening',
            category: '',
            saving_balance_after: 5000,
          },
        ],
        total: 1,
        total_pages: 1,
        page: 1,
      });
      const user = await renderPage();

      const dialog = await openHistory(user);
      expect(dialog).toHaveTextContent('Transactions for Emergency Fund');
      await within(dialog).findByText('Opening');

      expect(getSavingTransactions).toHaveBeenCalledWith(1, {
        page: 1,
        page_size: 25,
        search: '',
        type: '',
      });

      const cells = within(within(dialog).getAllByRole('row')[1])
        .getAllByRole('cell')
        .map(cell => cell.textContent);
      expect(cells).toEqual([
        '2026-11-01 10:00:00',
        'deposit',
        'Rs. 5000.00',
        'Opening',
        '-',
        'Rs. 5000.00',
      ]);
    });

    test('offers Deposit and Withdrawal filters and sends the choice', async () => {
      const user = await renderPage();

      const dialog = await openHistory(user);
      const typeFilter = within(dialog).getByRole('combobox', {
        name: 'Filter transactions by type',
      });
      expect(Array.from(typeFilter.options).map(o => o.value)).toEqual([
        '',
        'deposit',
        'withdrawal',
      ]);

      await user.selectOptions(typeFilter, 'withdrawal');

      await waitFor(() => {
        expect(getSavingTransactions).toHaveBeenLastCalledWith(
          1,
          expect.objectContaining({ type: 'withdrawal', page: 1 })
        );
      });
    });

    test('Next requests the next page number', async () => {
      getSavingTransactions.mockImplementation(async (savingId, params) => ({
        transactions: [
          {
            id: params.page,
            date: '2026-11-01',
            transaction_type: 'deposit',
            amount: 100,
            description: `Row on page ${params.page}`,
          },
        ],
        total: 30,
        total_pages: 2,
        page: params.page,
      }));
      const user = await renderPage();

      const dialog = await openHistory(user);
      await within(dialog).findByText('Row on page 1');
      await user.click(within(dialog).getByRole('button', { name: 'Next' }));

      expect(await within(dialog).findByText('Row on page 2')).toBeInTheDocument();
      expect(within(dialog).getByText('Page 2 of 2')).toBeInTheDocument();
      expect(within(dialog).getByRole('button', { name: 'Next' })).toBeDisabled();
    });

    test('shows an error inside the dialog when loading fails', async () => {
      getSavingTransactions.mockRejectedValue(
        new Error('Failed to fetch saving transactions: boom')
      );
      const user = await renderPage();

      const dialog = await openHistory(user);

      expect(await within(dialog).findByRole('alert')).toHaveTextContent(
        'Failed to fetch saving transactions: boom'
      );
    });
  });

  describe('deleting an account', () => {
    test('blocks deletion while the account still has a balance', async () => {
      const user = await renderPage();

      await user.click(within(rowFor('Emergency Fund')).getByRole('button', { name: 'Delete' }));

      expect(screen.getByRole('alert')).toHaveTextContent(
        'Saving account "Emergency Fund" cannot be deleted because its current balance is Rs. 5000.00'
      );

      await user.click(screen.getByRole('button', { name: 'Delete Without Backup' }));
      expect(deleteSaving).not.toHaveBeenCalled();
    });

    test('deletes an empty account after confirmation', async () => {
      deleteSaving.mockResolvedValue({ message: 'Saving account deleted' });
      const user = await renderPage();

      await user.click(within(rowFor('Vacation')).getByRole('button', { name: 'Delete' }));
      expect(screen.getByRole('heading', { name: 'Delete Savings Account' })).toBeInTheDocument();

      await user.click(screen.getByRole('button', { name: 'Delete Without Backup' }));

      expect(deleteSaving).toHaveBeenCalledWith(2);
      await waitFor(() => {
        expect(screen.queryByRole('cell', { name: 'Vacation' })).not.toBeInTheDocument();
      });
    });

    test('keeps the account and shows the error when deletion fails', async () => {
      deleteSaving.mockRejectedValue(new Error('Failed to delete saving: Server error'));
      const user = await renderPage();

      await user.click(within(rowFor('Vacation')).getByRole('button', { name: 'Delete' }));
      await user.click(screen.getByRole('button', { name: 'Delete Without Backup' }));

      expect(await screen.findByRole('alert')).toHaveTextContent('Server error');
      expect(screen.getByRole('cell', { name: 'Vacation' })).toBeInTheDocument();
    });

    test('downloads an Excel backup of savings transactions only', async () => {
      exportUserTransactionsExcel.mockResolvedValue({ data: new Blob(['xlsx']) });
      window.URL.createObjectURL = jest.fn(() => 'blob:backup');
      window.URL.revokeObjectURL = jest.fn();
      jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
      const user = await renderPage();

      await user.click(within(rowFor('Vacation')).getByRole('button', { name: 'Delete' }));
      await user.click(screen.getByRole('button', { name: 'Download Excel' }));

      expect(exportUserTransactionsExcel).toHaveBeenCalledWith(1, ['savings']);
      expect(
        await screen.findByText('Savings transaction backup downloaded successfully.')
      ).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Delete Savings Account' })).toBeInTheDocument();
      expect(deleteSaving).not.toHaveBeenCalled();
    });

    test('cancel closes the dialog without deleting', async () => {
      const user = await renderPage();

      await user.click(within(rowFor('Vacation')).getByRole('button', { name: 'Delete' }));
      await user.click(screen.getByRole('button', { name: 'Cancel' }));

      expect(
        screen.queryByRole('heading', { name: 'Delete Savings Account' })
      ).not.toBeInTheDocument();
      expect(deleteSaving).not.toHaveBeenCalled();
    });
  });
});
