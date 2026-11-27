import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import Assets from './Assets';
import {
  createAsset,
  createAssetTransaction,
  deleteAsset,
  exportUserTransactionsExcel,
  getAssets,
  getAssetTransactions,
  updateAsset,
} from '../services/api';

// The page talks to the backend only through services/api, so mocking that
// module lets these tests drive the real page UI without a server. Response
// shapes mirror app/assets/assets_routes.py.
jest.mock('../services/api', () => ({
  getAssets: jest.fn(),
  createAsset: jest.fn(),
  updateAsset: jest.fn(),
  deleteAsset: jest.fn(),
  createAssetTransaction: jest.fn(),
  getAssetTransactions: jest.fn(),
  exportUserTransactionsExcel: jest.fn(),
  exportUserTransactionsPdf: jest.fn(),
}));

jest.mock('../AuthContext', () => ({
  useAuth: () => ({ user: { id: 1, name: 'tester' } }),
}));

const NIFTY = {
  id: 1,
  name: 'Nifty Index Fund',
  user_id: 1,
  platform: 'Zerodha',
  category: 'Mutual Funds',
  balance: 250000,
};

const EPF = {
  id: 2,
  name: 'EPF',
  user_id: 1,
  platform: null,
  category: 'Provident Fund',
  balance: 0,
};


const rowFor = name => screen.getByRole('cell', { name }).closest('tr');
const rowValues = name =>
  within(rowFor(name)).getAllByRole('cell').slice(0, 4).map(cell => cell.textContent);

const renderPage = async (waitForAsset = 'Nifty Index Fund') => {
  const user = userEvent.setup();
  render(<MemoryRouter><Assets /></MemoryRouter>);
  await screen.findByRole('heading', { name: 'Assets' });
  await screen.findByRole('cell', { name: waitForAsset });
  return user;
};

describe('Assets page', () => {
  beforeEach(() => {
    getAssets.mockResolvedValue([{ ...NIFTY }, { ...EPF }]);
    getAssetTransactions.mockResolvedValue({
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

  describe('asset list', () => {
    test('shows balance, platform and category, with N/A for a missing platform', async () => {
      await renderPage();

      expect(rowValues('Nifty Index Fund')).toEqual([
        'Nifty Index Fund',
        'Rs. 250000.00',
        'Zerodha',
        'Mutual Funds',
      ]);
      expect(rowValues('EPF')).toEqual(['EPF', 'Rs. 0.00', 'N/A', 'Provident Fund']);
      expect(within(rowFor('Totals')).getByText('Rs. 250000.00')).toBeInTheDocument();
    });

    test('search filters by name and updates the total', async () => {
      const user = await renderPage();

      await user.type(screen.getByRole('searchbox', { name: 'Search assets by name' }), 'epf');

      expect(screen.queryByRole('cell', { name: 'Nifty Index Fund' })).not.toBeInTheDocument();
      expect(within(rowFor('Totals')).getByText('Rs. 0.00')).toBeInTheDocument();
    });

    test('sorts by balance numerically and by category alphabetically', async () => {
      getAssets.mockResolvedValue([
        { ...NIFTY, name: 'Big', balance: 100000, category: 'Stocks' },
        { ...EPF, name: 'Small', balance: 9000, category: 'ETF' },
      ]);
      const user = await renderPage('Big');
      const firstName = () =>
        within(screen.getAllByRole('row')[1]).getAllByRole('cell')[0].textContent;

      await user.click(screen.getByRole('columnheader', { name: 'Balance' }));
      expect(firstName()).toBe('Small');

      await user.click(screen.getByRole('columnheader', { name: 'Category' }));
      expect(firstName()).toBe('Small'); // "ETF" < "Stocks"
    });

    test('shows the error when assets fail to load', async () => {
      getAssets.mockRejectedValue(new Error('Network Error'));

      render(<MemoryRouter><Assets /></MemoryRouter>);

      expect(await screen.findByRole('alert')).toHaveTextContent('Network Error');
      expect(screen.getByText('No assets found')).toBeInTheDocument();
    });
  });

  describe('creating and editing assets', () => {
    test('offers the six asset categories', async () => {
      const user = await renderPage();

      await user.click(screen.getByRole('button', { name: 'Add Asset' }));
      const select = within(screen.getByRole('dialog', { name: 'Add Asset' })).getByLabelText(
        'Category:'
      );

      expect(Array.from(select.options).map(o => o.value)).toEqual([
        '',
        'Provident Fund',
        'Mutual Funds',
        'Stocks',
        'ETF',
        'FD',
        'Other',
      ]);
    });

    test('creates an asset with trimmed name, platform and category', async () => {
      createAsset.mockResolvedValue({
        message: 'Asset created',
        asset: { id: 3, name: 'Gold ETF', user_id: 1, platform: 'Groww', category: 'ETF', balance: 0 },
      });
      const user = await renderPage();

      await user.click(screen.getByRole('button', { name: 'Add Asset' }));
      const dialog = screen.getByRole('dialog', { name: 'Add Asset' });
      await user.type(within(dialog).getByLabelText('Asset Name:'), '  Gold ETF ');
      await user.type(within(dialog).getByLabelText('Platform:'), 'Groww');
      await user.selectOptions(within(dialog).getByLabelText('Category:'), 'ETF');
      await user.click(within(dialog).getByRole('button', { name: 'Save' }));

      expect(createAsset).toHaveBeenCalledWith({
        name: 'Gold ETF',
        platform: 'Groww',
        category: 'ETF',
      });
      expect(await screen.findByRole('cell', { name: 'Gold ETF' })).toBeInTheDocument();
      expect(rowValues('Gold ETF')).toEqual(['Gold ETF', 'Rs. 0.00', 'Groww', 'ETF']);
    });

    test('shows the backend error message when create fails', async () => {
      createAsset.mockRejectedValue(new Error('Asset name already exists'));
      const user = await renderPage();

      await user.click(screen.getByRole('button', { name: 'Add Asset' }));
      const dialog = screen.getByRole('dialog', { name: 'Add Asset' });
      await user.type(within(dialog).getByLabelText('Asset Name:'), 'EPF');
      await user.selectOptions(within(dialog).getByLabelText('Category:'), 'Other');
      await user.click(within(dialog).getByRole('button', { name: 'Save' }));

      expect(await within(dialog).findByRole('alert')).toHaveTextContent(
        'Asset name already exists'
      );
    });

    test('edits an asset with the form pre-filled', async () => {
      updateAsset.mockResolvedValue({
        message: 'Asset updated',
        asset: { ...NIFTY, platform: 'Groww' },
      });
      const user = await renderPage();

      await user.click(within(rowFor('Nifty Index Fund')).getByRole('button', { name: 'Edit' }));
      const dialog = screen.getByRole('dialog', { name: 'Edit Asset' });
      expect(within(dialog).getByLabelText('Asset Name:')).toHaveValue('Nifty Index Fund');
      expect(within(dialog).getByLabelText('Category:')).toHaveValue('Mutual Funds');

      const platform = within(dialog).getByLabelText('Platform:');
      await user.clear(platform);
      await user.type(platform, 'Groww');
      await user.click(within(dialog).getByRole('button', { name: 'Update' }));

      expect(updateAsset).toHaveBeenCalledWith(1, {
        name: 'Nifty Index Fund',
        platform: 'Groww',
        category: 'Mutual Funds',
      });
      await waitFor(() => {
        expect(rowValues('Nifty Index Fund')[2]).toBe('Groww');
      });
    });
  });

  describe('deposits and withdrawals', () => {
    const openTransactionForm = async (user, name) => {
      await user.click(within(rowFor(name)).getByRole('button', { name: 'Add Transaction' }));
      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveTextContent(`Add Transaction - ${name}`);
      return dialog;
    };

    test('a deposit sends the amount and updates the asset balance', async () => {
      createAssetTransaction.mockResolvedValue({
        message: 'Transaction added',
        balance: 260000,
      });
      const user = await renderPage();

      const dialog = await openTransactionForm(user, 'Nifty Index Fund');
      await user.type(within(dialog).getByLabelText('Amount:'), '10000');
      await user.type(within(dialog).getByLabelText('Description:'), 'SIP');
      await user.click(within(dialog).getByRole('button', { name: 'Submit' }));

      expect(createAssetTransaction).toHaveBeenCalledWith('1', {
        amount: 10000,
        type: 'deposit',
        description: 'SIP',
        category: '',
      });
      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
      expect(rowValues('Nifty Index Fund')[1]).toBe('Rs. 260000.00');
    });

    test('a withdrawal uses the "withdraw" type the backend expects', async () => {
      createAssetTransaction.mockResolvedValue({ message: 'Transaction added', balance: 200000 });
      const user = await renderPage();

      const dialog = await openTransactionForm(user, 'Nifty Index Fund');
      await user.selectOptions(within(dialog).getByLabelText('Transaction Type:'), 'withdraw');
      await user.type(within(dialog).getByLabelText('Amount:'), '50000');
      await user.click(within(dialog).getByRole('button', { name: 'Submit' }));

      expect(createAssetTransaction).toHaveBeenCalledWith(
        '1',
        expect.objectContaining({ amount: 50000, type: 'withdraw' })
      );
      await waitFor(() => {
        expect(rowValues('Nifty Index Fund')[1]).toBe('Rs. 200000.00');
      });
    });

    test('shows the backend error and keeps the balance on failure', async () => {
      createAssetTransaction.mockRejectedValue(new Error('Insufficient balance'));
      const user = await renderPage();

      const dialog = await openTransactionForm(user, 'EPF');
      await user.selectOptions(within(dialog).getByLabelText('Transaction Type:'), 'withdraw');
      await user.type(within(dialog).getByLabelText('Amount:'), '100');
      await user.click(within(dialog).getByRole('button', { name: 'Submit' }));

      expect(await within(dialog).findByRole('alert')).toHaveTextContent('Insufficient balance');
      expect(rowValues('EPF')[1]).toBe('Rs. 0.00');
    });
  });

  describe('transaction history', () => {
    const openHistory = async user => {
      await user.click(
        within(rowFor('Nifty Index Fund')).getByRole('button', { name: 'View Transactions' })
      );
      return screen.getByRole('dialog');
    };

    test('loads page 1 and shows the transactions', async () => {
      getAssetTransactions.mockResolvedValue({
        transactions: [
          {
            id: 1,
            date: '2026-11-05 09:30:00',
            transaction_type: 'deposit',
            amount: 10000,
            description: '',
          },
        ],
        total: 1,
        total_pages: 1,
        page: 1,
      });
      const user = await renderPage();

      const dialog = await openHistory(user);
      expect(dialog).toHaveTextContent('Transactions for Nifty Index Fund');
      await within(dialog).findByText('2026-11-05 09:30:00');

      expect(getAssetTransactions).toHaveBeenCalledWith(1, {
        page: 1,
        page_size: 25,
        search: '',
        type: '',
      });
      const cells = within(within(dialog).getAllByRole('row')[1])
        .getAllByRole('cell')
        .map(cell => cell.textContent);
      expect(cells).toEqual(['2026-11-05 09:30:00', 'deposit', 'Rs. 10000.00', '-']);
    });

    test('offers Deposit and Withdraw filters and sends the choice', async () => {
      const user = await renderPage();

      const dialog = await openHistory(user);
      const typeFilter = within(dialog).getByRole('combobox', {
        name: 'Filter transactions by type',
      });
      expect(Array.from(typeFilter.options).map(o => o.value)).toEqual([
        '',
        'deposit',
        'withdraw',
      ]);

      await user.selectOptions(typeFilter, 'withdraw');

      await waitFor(() => {
        expect(getAssetTransactions).toHaveBeenLastCalledWith(
          1,
          expect.objectContaining({ type: 'withdraw', page: 1 })
        );
      });
    });

    test('shows an error inside the dialog when loading fails', async () => {
      getAssetTransactions.mockRejectedValue(new Error('Failed to fetch asset transactions'));
      const user = await renderPage();

      const dialog = await openHistory(user);

      expect(await within(dialog).findByRole('alert')).toHaveTextContent(
        'Failed to fetch asset transactions'
      );
    });
  });

  describe('deleting an asset', () => {
    test('blocks deletion while the asset still has a balance', async () => {
      const user = await renderPage();

      await user.click(within(rowFor('Nifty Index Fund')).getByRole('button', { name: 'Delete' }));

      expect(screen.getByRole('alert')).toHaveTextContent(
        'Asset "Nifty Index Fund" cannot be deleted because its current balance is Rs. 250000.00'
      );
      await user.click(screen.getByRole('button', { name: 'Delete Without Backup' }));
      expect(deleteAsset).not.toHaveBeenCalled();
    });

    test('deletes a zero-balance asset after confirmation', async () => {
      deleteAsset.mockResolvedValue({ message: 'Asset deleted' });
      const user = await renderPage();

      await user.click(within(rowFor('EPF')).getByRole('button', { name: 'Delete' }));
      expect(screen.getByRole('heading', { name: 'Delete Asset' })).toBeInTheDocument();
      await user.click(screen.getByRole('button', { name: 'Delete Without Backup' }));

      expect(deleteAsset).toHaveBeenCalledWith(2);
      await waitFor(() => {
        expect(screen.queryByRole('cell', { name: 'EPF' })).not.toBeInTheDocument();
      });
    });

    test('shows the backend reason and keeps the asset when deletion fails', async () => {
      deleteAsset.mockRejectedValue(
        new Error('Asset has transaction history and cannot be deleted')
      );
      const user = await renderPage();

      await user.click(within(rowFor('EPF')).getByRole('button', { name: 'Delete' }));
      await user.click(screen.getByRole('button', { name: 'Delete Without Backup' }));

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Asset has transaction history and cannot be deleted'
      );
      expect(screen.getByRole('cell', { name: 'EPF' })).toBeInTheDocument();
    });

    test('downloads an Excel backup of asset transactions only', async () => {
      exportUserTransactionsExcel.mockResolvedValue({ data: new Blob(['xlsx']) });
      window.URL.createObjectURL = jest.fn(() => 'blob:backup');
      window.URL.revokeObjectURL = jest.fn();
      jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
      const user = await renderPage();

      await user.click(within(rowFor('EPF')).getByRole('button', { name: 'Delete' }));
      await user.click(screen.getByRole('button', { name: 'Download Excel' }));

      expect(exportUserTransactionsExcel).toHaveBeenCalledWith(1, ['assets']);
      expect(
        await screen.findByText('Asset transaction backup downloaded successfully.')
      ).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Delete Asset' })).toBeInTheDocument();
      expect(deleteAsset).not.toHaveBeenCalled();
    });

    test('cancel closes the dialog without deleting', async () => {
      const user = await renderPage();

      await user.click(within(rowFor('EPF')).getByRole('button', { name: 'Delete' }));
      await user.click(screen.getByRole('button', { name: 'Cancel' }));

      expect(screen.queryByRole('heading', { name: 'Delete Asset' })).not.toBeInTheDocument();
      expect(deleteAsset).not.toHaveBeenCalled();
    });
  });
});
