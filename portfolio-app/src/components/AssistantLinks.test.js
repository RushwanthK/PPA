import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { PageLinks } from './AssistantChat';
import { getAssets, getBanks, getCreditCards } from '../services/api';
import { LINK_ACTIONS, accountNamedIn, linkUrl } from '../services/assistantLinks';

jest.mock('../services/api', () => ({
  getCreditCards: jest.fn(),
  getBanks: jest.fn(),
  getSavings: jest.fn(),
  getAssets: jest.fn(),
}));

const CARDS = [{ id: 1, name: 'HDFC Regalia' }, { id: 2, name: 'Slice' }];

const helpAnswer = (links, question = 'how do I add a credit card transaction?') => ({
  id: 'm1', from: 'bot', mode: 'help', question, text: 'Use Add Transaction [S1].',
  result: { outcome: 'answered', links },
});

const renderLinks = (message, onNavigate = jest.fn()) => {
  render(<PageLinks message={message} onNavigate={onNavigate} />);
  return { onNavigate, user: userEvent.setup() };
};

describe('assistant link addresses', () => {
  test('only known actions become addresses, built from a fixed list', () => {
    expect(linkUrl('creditcard.add_transaction', 7)).toBe('/creditcard?open=add-transaction&id=7');
    expect(linkUrl('assets.add')).toBe('/assets?open=add');
    expect(linkUrl('dashboard.open')).toBe('/dashboard');
    expect(linkUrl('https://evil.example')).toBeNull();
    expect(Object.values(LINK_ACTIONS).every(a => a.path.startsWith('/'))).toBe(true);
  });

  test('an account named in the question is used only when exactly one matches', () => {
    expect(accountNamedIn(CARDS, 'add a transaction to my slice card')).toEqual(CARDS[1]);
    expect(accountNamedIn(CARDS, 'add a card transaction')).toBeNull();
  });

  test('a distinctive word of the name is enough ("axis" for "Axis Ace"), generic words are not', () => {
    const cards = [{ id: 1, name: 'HDFC Regalia' }, { id: 2, name: 'Axis Ace' }, { id: 3, name: 'Axis Neo' }];
    expect(accountNamedIn(cards.slice(0, 2), 'i want to view transactions of axis credit card')).toEqual(cards[1]);
    expect(accountNamedIn(cards, 'view transactions of axis credit card')).toBeNull();      // two Axis cards
    expect(accountNamedIn(cards, 'view transactions of axis ace')).toEqual(cards[1]);       // full name wins
    expect(accountNamedIn([{ id: 9, name: 'Credit Card' }], 'my credit card')).toEqual({ id: 9, name: 'Credit Card' });
    expect(accountNamedIn(cards, 'view my credit card')).toBeNull();
  });

  test('card details is a link (Process Billing is never run by a link)', () => {
    expect(linkUrl('creditcard.details', 2)).toBe('/creditcard?open=details&id=2');
    expect(linkUrl('bank.details', 2)).toBeNull();
    expect(Object.values(LINK_ACTIONS).some(a => /billing/i.test(a.open || ''))).toBe(false);
  });
});

describe('PageLinks', () => {
  beforeEach(() => jest.clearAllMocks());

  test('nothing is shown without links, for unknown actions or in My data mode', () => {
    const { container } = render(<PageLinks message={helpAnswer(['evil.action'])} />);
    expect(container).toBeEmptyDOMElement();
    const myData = { ...helpAnswer(['creditcard.add']), mode: 'my_data' };
    const { container: second } = render(<PageLinks message={myData} />);
    expect(second).toBeEmptyDOMElement();
  });

  test('a page link goes straight there', async () => {
    const { onNavigate, user } = renderLinks(helpAnswer(['creditcard.add']));
    await user.click(screen.getByRole('button', { name: 'Click here: Add a credit card' }));
    expect(onNavigate).toHaveBeenCalledWith('/creditcard?open=add');
    expect(getCreditCards).not.toHaveBeenCalled();
  });

  test("several cards: asks which one, from the user's live list", async () => {
    getCreditCards.mockResolvedValue(CARDS);
    const { onNavigate, user } = renderLinks(helpAnswer(['creditcard.add_transaction']));
    await user.click(screen.getByRole('button', { name: 'Click here: Add a transaction to a card' }));
    const picker = await screen.findByRole('group', { name: 'Which card?' });
    expect(picker).toHaveTextContent('HDFC Regalia');
    await user.click(screen.getByRole('button', { name: 'Slice' }));
    expect(onNavigate).toHaveBeenCalledWith('/creditcard?open=add-transaction&id=2');
    expect(getCreditCards).toHaveBeenCalledTimes(1);
  });

  test('a card named in the question is used without asking', async () => {
    getCreditCards.mockResolvedValue(CARDS);
    const { onNavigate, user } = renderLinks(
      helpAnswer(['creditcard.add_transaction'], 'how do I add a transaction to my HDFC Regalia card'));
    await user.click(screen.getByRole('button', { name: /Click here/ }));
    expect(onNavigate).toHaveBeenCalledWith('/creditcard?open=add-transaction&id=1');
    expect(screen.queryByRole('group')).not.toBeInTheDocument();
  });

  test('one account: no question', async () => {
    getBanks.mockResolvedValue({ data: [{ id: 5, name: 'Canara' }] });
    const { onNavigate, user } = renderLinks(helpAnswer(['bank.delete'], 'how to delete a bank'));
    await user.click(screen.getByRole('button', { name: 'Click here: Delete a bank account' }));
    expect(onNavigate).toHaveBeenCalledWith('/bank?open=delete&id=5');
  });

  test('no accounts yet: opens the add form instead and says so', async () => {
    getAssets.mockResolvedValue([]);
    const { onNavigate, user } = renderLinks(helpAnswer(['assets.add_transaction'], 'add an asset transaction'));
    await user.click(screen.getByRole('button', { name: /Click here/ }));
    expect(onNavigate).toHaveBeenCalledWith('/assets?open=add');
    expect(await screen.findByText(/You have no assets yet/)).toBeInTheDocument();
  });

  test('a failed account list is reported, not navigated', async () => {
    getCreditCards.mockRejectedValue(new Error('down'));
    const { onNavigate, user } = renderLinks(helpAnswer(['creditcard.delete']));
    await user.click(screen.getByRole('button', { name: /Click here/ }));
    expect(await screen.findByText(/Couldn't load your cards/)).toBeInTheDocument();
    expect(onNavigate).not.toHaveBeenCalled();
  });
});
