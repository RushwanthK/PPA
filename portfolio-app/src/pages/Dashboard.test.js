import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import Dashboard from './Dashboard';
import {
  getDashboardAssetAllocation,
  getDashboardSpending,
  getDashboardSummary,
} from '../services/api';

jest.mock('../services/api', () => ({
  getDashboardSummary: jest.fn(),
  getDashboardSpending: jest.fn(),
  getDashboardAssetAllocation: jest.fn(),
}));

const SUMMARY = {
  net_worth: 150000,
  total_assets: 100000,
  total_bank_balance: 40000,
  total_savings: 25000,
  total_credit_card_debt: 15000,
};

const cardValue = title =>
  screen.getByRole('heading', { name: title }).nextElementSibling.textContent;

describe('Dashboard', () => {
  beforeEach(() => {
    getDashboardSummary.mockResolvedValue(SUMMARY);
    getDashboardSpending.mockResolvedValue([{ name: 'Food', value: 1200 }]);
    getDashboardAssetAllocation.mockResolvedValue([{ name: 'Stocks', value: 100000 }]);
  });

  afterEach(() => {
    jest.clearAllMocks();
    jest.restoreAllMocks();
  });

  test('shows a loading state, then the summary cards in INR', async () => {
    render(<Dashboard />);

    expect(screen.getByText('Loading financial data...')).toBeInTheDocument();

    expect(
      await screen.findByRole('heading', { name: 'Financial Overview' })
    ).toBeInTheDocument();

    expect(cardValue('Net Worth')).toBe('₹1,50,000');
    expect(cardValue('Total Assets')).toBe('₹1,00,000');
    expect(cardValue('Bank Balances')).toBe('₹40,000');
    expect(cardValue('Savings')).toBe('₹25,000');
    expect(cardValue('Credit Card Debt')).toBe('₹15,000');
  });

  test('loads spending for the last 30 days by default and reloads on range change', async () => {
    const user = userEvent.setup();

    render(<Dashboard />);
    await screen.findByRole('heading', { name: 'Financial Overview' });

    expect(getDashboardSpending).toHaveBeenCalledWith('30d');
    expect(getDashboardAssetAllocation).toHaveBeenCalledTimes(1);

    await user.selectOptions(screen.getByRole('combobox'), '3m');

    await waitFor(() => {
      expect(getDashboardSpending).toHaveBeenLastCalledWith('3m');
    });
  });

  test('still renders (with zero values) when the summary request fails', async () => {
    getDashboardSummary.mockRejectedValue(new Error('Server down'));
    jest.spyOn(console, 'error').mockImplementation(() => {});

    render(<Dashboard />);

    expect(
      await screen.findByRole('heading', { name: 'Financial Overview' })
    ).toBeInTheDocument();
    expect(cardValue('Net Worth')).toBe('₹0');
  });
});
