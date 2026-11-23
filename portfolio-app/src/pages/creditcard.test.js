import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import CreditCard from './creditcard';
import {
  addCreditCardTransaction,
  createCreditCard,
  deleteCreditCard,
  exportUserTransactionsExcel,
  getCreditCards,
  getCreditCardTransactions,
  processBilling,
  updateCreditCard,
} from '../services/api';

// The page talks to the backend only through services/api, so mocking that
// module lets these tests drive the real page UI without a server.
jest.mock('../services/api', () => ({
  getCreditCards: jest.fn(),
  createCreditCard: jest.fn(),
  updateCreditCard: jest.fn(),
  deleteCreditCard: jest.fn(),
  getCreditCardTransactions: jest.fn(),
  addCreditCardTransaction: jest.fn(),
  processBilling: jest.fn(),
  exportUserTransactionsExcel: jest.fn(),
  exportUserTransactionsPdf: jest.fn(),
}));

jest.mock('../AuthContext', () => ({
  useAuth: () => ({ user: { id: 1, name: 'tester' } }),
}));

const HDFC = {
  id: 1,
  name: 'HDFC Regalia',
  limit: 100000,
  used: 30000,
  available_limit: 70000,
  billed_unpaid: 20000,
  unbilled_spends: 10000,
  billing_cycle_start: 5,
  total_payable: 20000,
  last_payment_date: '15102026',
  last_payment_amount: 5000,
};

const AXIS = {
  id: 2,
  name: 'Axis Ace',
  limit: 50000,
  used: 0,
  available_limit: 50000,
  billed_unpaid: 0,
  unbilled_spends: 0,
  billing_cycle_start: 1,
  total_payable: 0,
};

const rowFor = name => screen.getByRole('cell', { name }).closest('tr');

const rowValues = name =>
  within(rowFor(name)).getAllByRole('cell').slice(0, 6).map(cell => cell.textContent);

const renderPage = async (waitForCard = 'HDFC Regalia') => {
  const user = userEvent.setup();
  render(<CreditCard />);
  await screen.findByRole('heading', { name: 'Credit Cards' });
  await screen.findByRole('cell', { name: waitForCard });
  return user;
};


const openDetails = async (user, name) => {
  await user.click(within(rowFor(name)).getByRole('button', { name: 'Details' }));
  return screen.getByRole('dialog', { name: `Card Details: ${name}` });
};

describe('Credit card page', () => {
  beforeEach(() => {
    getCreditCards.mockResolvedValue([{ ...HDFC }, { ...AXIS }]);
    getCreditCardTransactions.mockResolvedValue({
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

  describe('card list', () => {
    test('shows limit, used, available, billed and unbilled for each card', async () => {
      await renderPage();

      expect(rowValues('HDFC Regalia')).toEqual([
        'HDFC Regalia',
        '100000.00',
        '30000.00',
        '70000.00',
        '20000.00',
        '10000.00',
      ]);
    });

    test('totals row sums used, billed unpaid and unbilled spends', async () => {
      getCreditCards.mockResolvedValue([
        { ...HDFC },
        { ...AXIS, used: 1500.5, billed_unpaid: 1000, unbilled_spends: 500.5 },
      ]);
      await renderPage();

      const totals = within(rowFor('Totals')).getAllByRole('cell').map(c => c.textContent);
      expect(totals).toEqual(['Totals', '', '31500.50', '', '21000.00', '10500.50', '']);
    });

    test('search filters cards by name and updates the totals', async () => {
      const user = await renderPage();

      await user.type(
        screen.getByRole('searchbox', { name: 'Search credit cards by name' }),
        'axis'
      );

      expect(screen.queryByRole('cell', { name: 'HDFC Regalia' })).not.toBeInTheDocument();
      expect(screen.getByRole('cell', { name: 'Axis Ace' })).toBeInTheDocument();
      expect(within(rowFor('Totals')).getAllByRole('cell')[2]).toHaveTextContent('0.00');
    });

    test('sorting by a numeric column sorts numerically, then reverses', async () => {
      getCreditCards.mockResolvedValue([
        { ...HDFC, name: 'Card A', limit: 9000 },
        { ...AXIS, name: 'Card B', limit: 100000 },
      ]);
      const user = await renderPage('Card A');
      const firstCardName = () =>
        within(screen.getAllByRole('row')[1]).getAllByRole('cell')[0].textContent;

      await user.click(screen.getByRole('columnheader', { name: 'Limit' }));
      // Numeric: 9000 < 100000 (a text sort would put "100000" first).
      expect(firstCardName()).toBe('Card A');

      await user.click(screen.getByRole('columnheader', { name: /Limit/ }));
      expect(firstCardName()).toBe('Card B');
    });

    test('shows the error when cards fail to load', async () => {
      getCreditCards.mockRejectedValue(new Error('Failed to fetch credit cards: boom'));

      render(<CreditCard />);

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Failed to fetch credit cards: boom'
      );
      expect(screen.getByText('No credit cards found')).toBeInTheDocument();
    });
  });

  describe('creating and editing cards', () => {
    test('creates a card with numeric limit and billing day', async () => {
      createCreditCard.mockResolvedValue({
        card: { ...AXIS, id: 3, name: 'ICICI Amazon', limit: 75000 },
      });
      const user = await renderPage();

      await user.click(screen.getByRole('button', { name: 'Add Credit Card' }));
      const dialog = screen.getByRole('dialog', { name: 'Add Credit Card' });

      await user.type(within(dialog).getByLabelText('Card Name'), 'ICICI Amazon');
      await user.type(within(dialog).getByLabelText('Credit Limit'), '75000');
      const billingDay = within(dialog).getByLabelText('Billing Cycle Start Day (1-31)');
      await user.clear(billingDay);
      await user.type(billingDay, '12');
      await user.click(within(dialog).getByRole('button', { name: 'Save' }));

      expect(createCreditCard).toHaveBeenCalledWith({
        name: 'ICICI Amazon',
        limit: 75000,
        billing_cycle_start: 12,
      });
      expect(await screen.findByRole('cell', { name: 'ICICI Amazon' })).toBeInTheDocument();
      expect(screen.getByText('Credit card created successfully.')).toBeInTheDocument();
    });

    test('shows the backend error and keeps the form open when create fails', async () => {
      createCreditCard.mockRejectedValue(
        new Error('Failed to create credit card: Credit card name already exists')
      );
      const user = await renderPage();

      await user.click(screen.getByRole('button', { name: 'Add Credit Card' }));
      const dialog = screen.getByRole('dialog', { name: 'Add Credit Card' });
      await user.type(within(dialog).getByLabelText('Card Name'), 'HDFC Regalia');
      await user.type(within(dialog).getByLabelText('Credit Limit'), '1000');
      await user.click(within(dialog).getByRole('button', { name: 'Save' }));

      expect(await within(dialog).findByRole('alert')).toHaveTextContent(
        'Credit card name already exists'
      );
    });

    test('editing only the limit does not re-run billing', async () => {
      updateCreditCard.mockResolvedValue({ card: { ...HDFC, limit: 150000 } });
      const user = await renderPage();

      const details = await openDetails(user, 'HDFC Regalia');
      await user.click(within(details).getByRole('button', { name: 'Edit Card' }));

      const dialog = screen.getByRole('dialog', { name: 'Edit Credit Card' });
      expect(within(dialog).getByLabelText('Card Name')).toHaveValue('HDFC Regalia');
      expect(within(dialog).getByLabelText('Billing Cycle Start Day (1-31)')).toHaveValue(5);

      const limit = within(dialog).getByLabelText('Credit Limit');
      await user.clear(limit);
      await user.type(limit, '150000');
      await user.click(within(dialog).getByRole('button', { name: 'Update' }));

      expect(updateCreditCard).toHaveBeenCalledWith(1, {
        name: 'HDFC Regalia',
        limit: 150000,
        billing_cycle_start: 5,
      });
      expect(await screen.findByText('Credit card updated successfully.')).toBeInTheDocument();
      expect(processBilling).not.toHaveBeenCalled();
      expect(rowValues('HDFC Regalia')[1]).toBe('150000.00');
    });

    test('changing the billing day automatically re-runs billing', async () => {
      updateCreditCard.mockResolvedValue({ card: { ...HDFC, billing_cycle_start: 20 } });
      // Mirrors the real /process_billing response, which includes the id.
      processBilling.mockResolvedValue({
        message: 'Billing processed successfully',
        transactions_billed: 2,
        total_amount_billed: 25000,
        card: { id: 1, billed_unpaid: 25000, unbilled_spends: 5000 },
      });
      const user = await renderPage();

      const details = await openDetails(user, 'HDFC Regalia');
      await user.click(within(details).getByRole('button', { name: 'Edit Card' }));

      const dialog = screen.getByRole('dialog', { name: 'Edit Credit Card' });
      const billingDay = within(dialog).getByLabelText('Billing Cycle Start Day (1-31)');
      await user.clear(billingDay);
      await user.type(billingDay, '20');
      await user.click(within(dialog).getByRole('button', { name: 'Update' }));

      expect(
        await screen.findByText('Credit card updated and billing recalculated successfully.')
      ).toBeInTheDocument();
      expect(processBilling).toHaveBeenCalledWith(1);
      expect(rowValues('HDFC Regalia').slice(4)).toEqual(['25000.00', '5000.00']);
    });
  });

  describe('adding a transaction', () => {
    const openTransactionForm = async (user, name) => {
      await user.click(within(rowFor(name)).getByRole('button', { name: 'Add Tx' }));
      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveTextContent(`Add Transaction - ${name}`);
      return dialog;
    };

    const fillForm = async (user, dialog, { amount, date, description, category }) => {
      await user.type(within(dialog).getByLabelText('Amount'), amount);
      if (date) {
        const dateInput = within(dialog).getByLabelText('Date');
        await user.clear(dateInput);
        await user.type(dateInput, date);
      }
      if (description) {
        await user.type(within(dialog).getByLabelText('Description'), description);
      }
      if (category) {
        await user.type(within(dialog).getByLabelText('Category'), category);
      }
    };

    test('an expense is sent as a negative amount and updates the card balances', async () => {
      addCreditCardTransaction.mockResolvedValue({
        card: { used: 32500, available_limit: 67500, unbilled_spends: 12500 },
      });
      const user = await renderPage();

      const dialog = await openTransactionForm(user, 'HDFC Regalia');
      await fillForm(user, dialog, {
        amount: '2500',
        date: '2026-11-10',
        description: 'Flight',
        category: 'Travel',
      });
      await user.click(within(dialog).getByRole('radio', { name: 'Expense' }));
      await user.click(within(dialog).getByRole('button', { name: 'Submit' }));

      expect(addCreditCardTransaction).toHaveBeenCalledWith(1, {
        amount: -2500,
        date: '2026-11-10',
        description: 'Flight',
        category: 'Travel',
        is_payment: false,
      });

      expect(await screen.findByText('Transaction added successfully.')).toBeInTheDocument();
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      expect(rowValues('HDFC Regalia')).toEqual([
        'HDFC Regalia',
        '100000.00',
        '32500.00',
        '67500.00',
        '20000.00',
        '12500.00',
      ]);
    });

    test('a payment is sent as a positive amount with is_payment true', async () => {
      addCreditCardTransaction.mockResolvedValue({
        card: { used: 10000, available_limit: 90000, billed_unpaid: 0 },
      });
      const user = await renderPage();

      const dialog = await openTransactionForm(user, 'HDFC Regalia');
      await fillForm(user, dialog, { amount: '20000', date: '2026-11-12' });
      await user.click(within(dialog).getByRole('radio', { name: 'Payment' }));
      await user.click(within(dialog).getByRole('button', { name: 'Submit' }));

      expect(addCreditCardTransaction).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ amount: 20000, is_payment: true })
      );
      await screen.findByText('Transaction added successfully.');
      expect(rowValues('HDFC Regalia')[4]).toBe('0.00');
    });

    test('the date defaults to today', async () => {
      const user = await renderPage();

      const dialog = await openTransactionForm(user, 'Axis Ace');
      const today = new Date();
      const pad = n => String(n).padStart(2, '0');
      const expected = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;

      expect(within(dialog).getByLabelText('Date')).toHaveValue(expected);
    });

    test('requires choosing Payment or Expense before submitting', async () => {
      const user = await renderPage();

      const dialog = await openTransactionForm(user, 'HDFC Regalia');
      await fillForm(user, dialog, { amount: '100' });
      await user.click(within(dialog).getByRole('button', { name: 'Submit' }));

      expect(within(dialog).getByRole('alert')).toHaveTextContent(
        'Please select whether this is a Payment or Expense.'
      );
      expect(addCreditCardTransaction).not.toHaveBeenCalled();

      // Choosing a type clears the message.
      await user.click(within(dialog).getByRole('radio', { name: 'Expense' }));
      expect(within(dialog).queryByRole('alert')).not.toBeInTheDocument();
    });

    test('shows the backend error and leaves balances unchanged on failure', async () => {
      addCreditCardTransaction.mockRejectedValue(
        new Error('Failed to add credit card transaction: Credit limit exceeded')
      );
      const user = await renderPage();

      const dialog = await openTransactionForm(user, 'Axis Ace');
      await fillForm(user, dialog, { amount: '60000' });
      await user.click(within(dialog).getByRole('radio', { name: 'Expense' }));
      await user.click(within(dialog).getByRole('button', { name: 'Submit' }));

      expect(await within(dialog).findByRole('alert')).toHaveTextContent(
        'Credit limit exceeded'
      );
      expect(rowValues('Axis Ace')[2]).toBe('0.00');
    });
  });

  describe('card details and billing', () => {
    test('shows all balances and the formatted last payment', async () => {
      const user = await renderPage();

      const details = await openDetails(user, 'HDFC Regalia');

      expect(details).toHaveTextContent('Limit:Rs.100000.00');
      expect(details).toHaveTextContent('Available:Rs.70000.00');
      expect(details).toHaveTextContent('Billing Cycle Start:5 of month');
      expect(details).toHaveTextContent('Total Payable:Rs.20000.00');
      expect(details).toHaveTextContent('Last Payment:Rs.5000.00 on Oct 15, 2026');
    });

    test('hides the last payment row when there has been no payment', async () => {
      const user = await renderPage();

      const details = await openDetails(user, 'Axis Ace');

      expect(details).not.toHaveTextContent('Last Payment');
    });

    test('Process Billing shows the billing summary and updates the card', async () => {
      // Mirrors the real /process_billing response.
      processBilling.mockResolvedValue({
        message: 'Billing processed successfully',
        transactions_billed: 3,
        total_amount_billed: 10000,
        card: { id: 1, billed_unpaid: 30000, unbilled_spends: 0 },
      });
      const user = await renderPage();

      const details = await openDetails(user, 'HDFC Regalia');
      await user.click(within(details).getByRole('button', { name: 'Process Billing' }));

      // The card-details dialog stays open underneath; each dialog must still
      // be announced with its own title.
      const summary = await screen.findByRole('dialog', {
        name: 'Billing Processed Successfully',
      });
      expect(
        screen.getByRole('dialog', { name: 'Card Details: HDFC Regalia' })
      ).toBeInTheDocument();
      expect(processBilling).toHaveBeenCalledWith(1);
      expect(summary).toHaveTextContent('Transactions Billed: 3');
      expect(summary).toHaveTextContent('Total Amount Billed: Rs.10000.00');
      expect(summary).toHaveTextContent('New Billed Unpaid: Rs.30000.00');
      expect(summary).toHaveTextContent('New Unbilled Spends: Rs.0.00');
      expect(rowValues('HDFC Regalia').slice(4)).toEqual(['30000.00', '0.00']);
    });

    test('a billing failure is shown inside the details dialog', async () => {
      processBilling.mockRejectedValue(
        new Error('Failed to process billing: Billing date not reached')
      );
      const user = await renderPage();

      const details = await openDetails(user, 'HDFC Regalia');
      await user.click(within(details).getByRole('button', { name: 'Process Billing' }));

      expect(await within(details).findByRole('alert')).toHaveTextContent(
        'Billing date not reached'
      );
      expect(
        screen.queryByRole('heading', { name: 'Billing Processed Successfully' })
      ).not.toBeInTheDocument();
    });
  });

  describe('transaction history', () => {
    const openHistory = async user => {
      const details = await openDetails(user, 'HDFC Regalia');
      await user.click(within(details).getByRole('button', { name: 'View Transactions' }));
      return screen.getByRole('dialog');
    };

    test('loads page 1 and shows signed amounts and billed status', async () => {
      getCreditCardTransactions.mockResolvedValue({
        transactions: [
          {
            id: 1,
            date: '2026-11-10',
            amount: -2500,
            description: 'Flight',
            category: 'Travel',
            transaction_type: 'expense',
            is_billed: true,
          },
          {
            id: 2,
            date: '2026-11-12',
            amount: 20000,
            description: '',
            category: '',
            transaction_type: 'payment',
            is_billed: false,
          },
        ],
        total: 2,
        total_pages: 1,
        page: 1,
      });
      const user = await renderPage();

      const dialog = await openHistory(user);
      await within(dialog).findByText('Flight');

      expect(getCreditCardTransactions).toHaveBeenCalledWith(1, {
        page: 1,
        page_size: 25,
        search: '',
        type: '',
      });

      const rows = within(dialog).getAllByRole('row');
      const cells = row => within(row).getAllByRole('cell').map(c => c.textContent);
      expect(cells(rows[1])).toEqual(['2026-11-10', '-2500.00', 'Flight', 'Travel', 'expense', '✓']);
      expect(cells(rows[2])).toEqual(['2026-11-12', '+20000.00', '-', '-', 'payment', '']);
      expect(within(dialog).getByText('Showing 1-2 of 2')).toBeInTheDocument();
    });

    test('offers Expense and Payment as type filters and sends the choice', async () => {
      const user = await renderPage();

      const dialog = await openHistory(user);
      const typeFilter = within(dialog).getByRole('combobox', {
        name: 'Filter transactions by type',
      });

      expect(Array.from(typeFilter.options).map(o => o.value)).toEqual([
        '',
        'expense',
        'payment',
      ]);

      await user.selectOptions(typeFilter, 'payment');

      await waitFor(() => {
        expect(getCreditCardTransactions).toHaveBeenLastCalledWith(
          1,
          expect.objectContaining({ type: 'payment', page: 1 })
        );
      });
    });

    test('Next requests the next page number', async () => {
      getCreditCardTransactions.mockImplementation(async (cardId, params) => ({
        transactions: [
          {
            id: params.page,
            date: '2026-11-01',
            amount: -100,
            description: `Row on page ${params.page}`,
            transaction_type: 'expense',
          },
        ],
        total: 60,
        total_pages: 3,
        page: params.page,
      }));
      const user = await renderPage();

      const dialog = await openHistory(user);
      await within(dialog).findByText('Row on page 1');

      await user.click(within(dialog).getByRole('button', { name: 'Next' }));

      expect(await within(dialog).findByText('Row on page 2')).toBeInTheDocument();
      expect(within(dialog).getByText('Page 2 of 3')).toBeInTheDocument();
      expect(within(dialog).getByText('Showing 26-50 of 60')).toBeInTheDocument();
    });

    test('shows an error inside the dialog when loading fails', async () => {
      getCreditCardTransactions.mockRejectedValue(
        new Error('Failed to fetch credit card transactions: boom')
      );
      const user = await renderPage();

      const dialog = await openHistory(user);

      expect(await within(dialog).findByRole('alert')).toHaveTextContent(
        'Failed to fetch credit card transactions: boom'
      );
    });
  });

  describe('deleting a card', () => {
    const openDelete = async user => {
      const details = await openDetails(user, 'HDFC Regalia');
      await user.click(within(details).getByRole('button', { name: 'Delete Card' }));
      expect(screen.getByRole('heading', { name: 'Delete Credit Card' })).toBeInTheDocument();
    };

    test('shows the total payable and deletes after confirmation', async () => {
      deleteCreditCard.mockResolvedValue({});
      const user = await renderPage();

      await openDelete(user);
      expect(screen.getByText('Current total payable: Rs.20000.00')).toBeInTheDocument();

      await user.click(screen.getByRole('button', { name: 'Delete Without Backup' }));

      expect(deleteCreditCard).toHaveBeenCalledWith(1);
      expect(await screen.findByText('Credit card deleted successfully.')).toBeInTheDocument();
      expect(screen.queryByRole('cell', { name: 'HDFC Regalia' })).not.toBeInTheDocument();
    });

    test('keeps the card and shows the error when deletion fails', async () => {
      deleteCreditCard.mockRejectedValue(
        new Error('Failed to delete credit card: Card has outstanding balance')
      );
      const user = await renderPage();

      await openDelete(user);
      await user.click(screen.getByRole('button', { name: 'Delete Without Backup' }));

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Card has outstanding balance'
      );
      expect(screen.getByRole('cell', { name: 'HDFC Regalia' })).toBeInTheDocument();
    });

    test('downloads an Excel backup of credit card transactions before deleting', async () => {
      exportUserTransactionsExcel.mockResolvedValue({ data: new Blob(['xlsx']) });
      // jsdom does not implement object URLs or file downloads.
      window.URL.createObjectURL = jest.fn(() => 'blob:backup');
      window.URL.revokeObjectURL = jest.fn();
      jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

      const user = await renderPage();
      await openDelete(user);

      await user.click(screen.getByRole('button', { name: 'Download Excel' }));

      expect(exportUserTransactionsExcel).toHaveBeenCalledWith(1, ['credit_cards']);
      expect(
        await screen.findByText('Credit card transaction backup downloaded successfully.')
      ).toBeInTheDocument();
      // After a backup the confirm button no longer says "Without Backup".
      expect(screen.getByRole('button', { name: 'Delete Credit Card' })).toBeInTheDocument();
      expect(deleteCreditCard).not.toHaveBeenCalled();
    });

    test('cancel closes the dialog without deleting', async () => {
      const user = await renderPage();

      await openDelete(user);
      await user.click(screen.getByRole('button', { name: 'Cancel' }));

      expect(
        screen.queryByRole('heading', { name: 'Delete Credit Card' })
      ).not.toBeInTheDocument();
      expect(deleteCreditCard).not.toHaveBeenCalled();
    });
  });
});
