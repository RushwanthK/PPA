import api, {
  addCreditCardTransaction,
  createAsset,
  deleteAsset,
  getAssets,
  updateAsset,
  exportUserTransactionsExcel,
  getCreditCardTransactions,
  processBilling,
  updateCreditCard,
  getBankTransactions,
  getBanks,
  addBankTransaction,
  logoutSession,
  logoutAllDevices,
} from './api';
import { onSessionExpired } from './authEvents';

// Instead of hitting the network, every request in this file is answered by
// a fake axios adapter. Each test decides what the "server" returns.
let requests;
let respond;

const originalAdapter = api.defaults.adapter;

beforeEach(() => {
  requests = [];
  respond = () => ({ status: 200, data: {} });

  api.defaults.adapter = async config => {
    requests.push(config);
    const { status, data } = respond(config);

    if (status >= 200 && status < 300) {
      return { status, data, headers: {}, config, statusText: 'OK' };
    }

    const error = new Error(`Request failed with status code ${status}`);
    error.config = config;
    error.response = { status, data, headers: {}, config };
    throw error;
  };

  jest.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
  api.defaults.adapter = originalAdapter;
  jest.restoreAllMocks();
});

describe('api client interceptors', () => {
  test('attaches the stored token as a Bearer Authorization header', async () => {
    localStorage.setItem('token', 'abc123');

    await api.get('/banks');

    expect(requests[0].headers.Authorization).toBe('Bearer abc123');
  });

  test('sends no Authorization header when there is no stored token', async () => {
    await api.get('/banks');

    expect(requests[0].headers.Authorization).toBeUndefined();
  });

  test('raises the session-expired event on a 401 response', async () => {
    const handler = jest.fn();
    const unsubscribe = onSessionExpired(handler);
    respond = () => ({
      status: 401,
      data: { error: 'Your session has expired. Please log in again.' },
    });

    await expect(api.get('/banks')).rejects.toThrow();
    expect(handler).toHaveBeenCalledTimes(1);

    unsubscribe();
  });

  test('does not raise the session-expired event on other errors', async () => {
    const handler = jest.fn();
    const unsubscribe = onSessionExpired(handler);
    respond = () => ({ status: 500, data: { error: 'boom' } });

    await expect(api.get('/banks')).rejects.toThrow();
    expect(handler).not.toHaveBeenCalled();

    unsubscribe();
  });
});

describe('session helpers', () => {
  test('logoutSession revokes the given token even after it left localStorage', async () => {
    // ProfileDialog clears localStorage right after calling this.
    await logoutSession('old-token');

    expect(requests[0].method).toBe('post');
    expect(requests[0].url).toBe('/logout');
    expect(requests[0].headers.Authorization).toBe('Bearer old-token');
  });

  test('logoutAllDevices posts with the stored token', async () => {
    localStorage.setItem('token', 'abc123');

    await logoutAllDevices();

    expect(requests[0].method).toBe('post');
    expect(requests[0].url).toBe('/logout-all');
    expect(requests[0].headers.Authorization).toBe('Bearer abc123');
  });
});

describe('bank API helpers', () => {
  test('getBanks wraps the response array in { data }', async () => {
    respond = () => ({ status: 200, data: [{ id: 1, name: 'HDFC', balance: 10 }] });

    await expect(getBanks()).resolves.toEqual({
      data: [{ id: 1, name: 'HDFC', balance: 10 }],
    });
  });

  test('getBankTransactions sends cursor and filter params to the bank endpoint', async () => {
    respond = () => ({
      status: 200,
      data: { transactions: [], has_more: false, next_cursor: null },
    });

    await getBankTransactions(7, {
      cursor: 'abc',
      page_size: 25,
      search: 'rent',
      type: 'expense',
    });

    expect(requests[0].url).toBe('/banks/7/transactions');
    expect(requests[0].params).toEqual({
      cursor: 'abc',
      page_size: 25,
      search: 'rent',
      type: 'expense',
    });
  });

  test('getBankTransactions surfaces the backend error message', async () => {
    respond = () => ({ status: 400, data: { error: 'Invalid cursor' } });

    await expect(getBankTransactions(7)).rejects.toThrow('Invalid cursor');
  });

  test('addBankTransaction posts only the expected fields', async () => {
    respond = () => ({ status: 201, data: { balance: 900, transaction: { id: 1 } } });

    await addBankTransaction(3, {
      amount: 100,
      type: 'expense',
      description: 'Groceries',
      category: 'Food',
      unexpected: 'should not be sent',
    });

    expect(requests[0].method).toBe('post');
    expect(requests[0].url).toBe('/banks/3/transactions');
    expect(JSON.parse(requests[0].data)).toEqual({
      amount: 100,
      type: 'expense',
      description: 'Groceries',
      category: 'Food',
    });
  });

  test('addBankTransaction defaults the type to income', async () => {
    respond = () => ({ status: 201, data: {} });

    await addBankTransaction(3, { amount: 50 });

    expect(JSON.parse(requests[0].data).type).toBe('income');
  });

  test('addBankTransaction falls back to a generic error message', async () => {
    respond = () => ({ status: 500, data: {} });

    await expect(addBankTransaction(3, { amount: 50 })).rejects.toThrow(
      'Failed to add transaction'
    );
  });
});

describe('transaction export helpers', () => {
  test('requests a blob and joins selected categories', async () => {
    await exportUserTransactionsExcel(5, ['banks', 'savings']);

    expect(requests[0].url).toBe('/users/5/transactions/export/excel');
    expect(requests[0].responseType).toBe('blob');
    expect(requests[0].params).toEqual({ categories: 'banks,savings' });
  });

  test('omits the categories param when none are given (export everything)', async () => {
    await exportUserTransactionsExcel(5);

    expect(requests[0].params).toEqual({});
  });
});

describe('credit card API helpers', () => {
  test('updateCreditCard refuses to send backend-calculated balance fields', async () => {
    await expect(
      updateCreditCard(1, { name: 'HDFC', used: 500 })
    ).rejects.toThrow('Cannot update calculated field: used');

    expect(requests).toHaveLength(0);
  });

  test('updateCreditCard sends editable fields with PUT', async () => {
    respond = () => ({ status: 200, data: { card: { id: 1 } } });

    await updateCreditCard(1, { name: 'HDFC', limit: 1000, billing_cycle_start: 5 });

    expect(requests[0].method).toBe('put');
    expect(requests[0].url).toBe('/credit_cards/1');
  });

  test('addCreditCardTransaction requires an amount and a date', async () => {
    await expect(
      addCreditCardTransaction(1, { amount: -100 })
    ).rejects.toThrow('Amount and transaction date are required');

    expect(requests).toHaveLength(0);
  });

  test('addCreditCardTransaction converts a Date object to ddMMyyyy', async () => {
    respond = () => ({ status: 201, data: { card: {} } });

    await addCreditCardTransaction(1, {
      amount: -100,
      date: new Date(2026, 10, 9),
      is_payment: false,
    });

    expect(JSON.parse(requests[0].data)).toEqual({
      amount: -100,
      date: '09112026',
      is_payment: false,
    });
  });

  test('addCreditCardTransaction passes a yyyy-MM-dd string through unchanged', async () => {
    respond = () => ({ status: 201, data: { card: {} } });

    await addCreditCardTransaction(1, { amount: -100, date: '2026-11-09' });

    expect(JSON.parse(requests[0].data).date).toBe('2026-11-09');
  });

  test('getCreditCardTransactions sends page-number params', async () => {
    respond = () => ({ status: 200, data: { transactions: [] } });

    await getCreditCardTransactions(4, { page: 2, page_size: 25, type: 'payment' });

    expect(requests[0].url).toBe('/credit_cards/4/transactions');
    expect(requests[0].params).toEqual({ page: 2, page_size: 25, type: 'payment' });
  });

  test('processBilling posts to the billing endpoint and prefixes errors', async () => {
    respond = () => ({ status: 404, data: { error: 'Credit card not found' } });

    await expect(processBilling(9)).rejects.toThrow(
      'Failed to process billing: Credit card not found'
    );
    expect(requests[0].method).toBe('post');
    expect(requests[0].url).toBe('/credit_cards/9/process_billing');
  });
});

describe('asset API helpers', () => {
  test('getAssets returns the list without printing it to the console', async () => {
    const logSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
    respond = () => ({ status: 200, data: [{ id: 1, name: 'EPF', balance: 1000 }] });

    await expect(getAssets()).resolves.toEqual([{ id: 1, name: 'EPF', balance: 1000 }]);
    expect(logSpy).not.toHaveBeenCalled();
  });

  test.each([
    ['createAsset', () => createAsset({ name: 'EPF' }), 'Asset name already exists'],
    ['updateAsset', () => updateAsset(1, { name: 'EPF' }), 'Asset not found'],
    ['deleteAsset', () => deleteAsset(1), 'Asset balance must be zero'],
    ['getAssets', () => getAssets(), 'Database unavailable'],
  ])('%s throws the backend error message', async (name, call, backendError) => {
    respond = () => ({ status: 400, data: { error: backendError } });

    await expect(call()).rejects.toThrow(backendError);
  });

  test('falls back to a readable message when the backend sends none', async () => {
    respond = () => ({ status: 500, data: {} });

    await expect(deleteAsset(1)).rejects.toThrow('Failed to delete asset');
  });

  test('updateAsset never sends the balance field', async () => {
    respond = () => ({ status: 200, data: { asset: { id: 1 } } });

    await updateAsset(1, { name: 'EPF', balance: 999, category: 'Other' });

    expect(JSON.parse(requests[0].data)).toEqual({ name: 'EPF', category: 'Other' });
  });
});
