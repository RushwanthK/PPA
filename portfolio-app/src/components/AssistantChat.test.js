import { StrictMode } from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import AssistantChat, {
  buildHistory, FormattedText, formatResetTime, formatValue, HELP_DATA_HINT, MY_DATA_NOTICE,
} from './AssistantChat';
import { askAssistant, getAssistantUsage, isAssistantConfigured } from '../services/assistantApi';

jest.mock('../services/assistantApi', () => ({
  askAssistant: jest.fn(),
  getAssistantUsage: jest.fn(),
  isAssistantConfigured: jest.fn(),
}));

const USAGE = {
  requests_used: 3, requests_limit: 50, tokens_used: 900, tokens_limit: 60000,
  resets_at: '2026-11-25T13:30:00+05:30',
  limits_enforced: true, token_budget: 60000, token_budget_used: 45000, token_budget_left_pct: 25,
  token_budget_source: 'ppa_daily_cap',
};

const HELP_ANSWER = {
  answer: 'Open the card and choose **Add payment** [S1].',
  outcome: 'answered',
  citations: [{ id: 'S1', source_path: 'ppa/04-credit-cards.md', title: 'Credit cards in PPA',
                section: 'Credit cards in PPA > Recording a payment' }],
  disclaimer: null, notice: null, provider: 'groq', model: 'openai/gpt-oss-120b',
  usage: { input_tokens: 800, output_tokens: 90 }, data: [],
};

const DATA_ANSWER = {
  answer: 'Your HDFC balance is ₹81,234.50.',
  outcome: 'answered', citations: [], disclaimer: null, notice: null, provider: 'groq',
  model: 'openai/gpt-oss-120b', usage: { input_tokens: 2000, output_tokens: 80 },
  data: [{
    title: 'Accounts (now)',
    facts: { bank_accounts: 1, total_bank_balance: 81234.5 },
    tables: [{ title: 'Bank accounts', columns: ['name', 'balance'], rows: [['HDFC Savings', 81234.5]] }],
  }],
};

const openChat = async user => {
  await user.click(screen.getByRole('button', { name: 'Open PPA Assistant' }));
  return screen.getByRole('dialog', { name: 'PPA Assistant' });
};

const ask = async (user, text) => {
  await user.type(screen.getByRole('textbox', { name: 'Message' }), text);
  await user.click(screen.getByRole('button', { name: 'Send' }));
};

beforeEach(() => {
  jest.clearAllMocks();
  isAssistantConfigured.mockReturnValue(true);
  getAssistantUsage.mockResolvedValue(USAGE);
});

describe('AssistantChat', () => {
  test('is hidden when the AI service URL is not configured', () => {
    isAssistantConfigured.mockReturnValue(false);
    render(<AssistantChat />);
    expect(screen.queryByRole('button', { name: /PPA Assistant/ })).not.toBeInTheDocument();
  });

  test('shows the remaining daily questions and reset time in IST', async () => {
    const user = userEvent.setup();
    render(<AssistantChat />);
    await openChat(user);
    expect(await screen.findByText('47 of 50 questions · 25% tokens left · resets 1:30 PM IST')).toBeInTheDocument();
  });

  test('help mode sends the question and shows the answer with its sources', async () => {
    askAssistant.mockResolvedValue(HELP_ANSWER);
    const user = userEvent.setup();
    render(<AssistantChat />);
    const dialog = await openChat(user);

    await ask(user, 'How do I pay my card?');

    expect(askAssistant).toHaveBeenCalledWith('How do I pay my card?', 'help', []);
    expect(await within(dialog).findByText('Add payment')).toBeInTheDocument();
    expect(within(dialog).getByText('Add payment').tagName).toBe('STRONG');
    expect(within(dialog).getByText(/\[S1\] Credit cards in PPA — Recording a payment/)).toBeInTheDocument();
    expect(getAssistantUsage).toHaveBeenCalledTimes(2); // on open and after the answer
  });

  test('my data mode shows the privacy notice, sends mode my_data and shows the figures', async () => {
    askAssistant.mockResolvedValue(DATA_ANSWER);
    const user = userEvent.setup();
    render(<AssistantChat />);
    const dialog = await openChat(user);

    expect(within(dialog).queryByText(MY_DATA_NOTICE)).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole('switch', { name: 'My data' }));
    expect(within(dialog).getByText(MY_DATA_NOTICE)).toBeInTheDocument();

    await ask(user, 'What is my bank balance?');
    expect(askAssistant).toHaveBeenCalledWith('What is my bank balance?', 'my_data', []);

    expect(await within(dialog).findByText('Your HDFC balance is ₹81,234.50.')).toBeInTheDocument();
    await user.click(within(dialog).getByText('Figures used (1)'));
    const table = within(dialog).getByRole('table', { name: 'Bank accounts' });
    expect(within(table).getByText('HDFC Savings')).toBeInTheDocument();
    expect(within(table).getByText('₹81,234.50')).toBeInTheDocument();
  });

  test('shows the server message on errors and lets the user ask again', async () => {
    askAssistant.mockRejectedValueOnce(new Error('The assistant is busy right now. Please try again in about 40 seconds.'));
    const user = userEvent.setup();
    render(<AssistantChat />);
    const dialog = await openChat(user);

    await ask(user, 'How do I pay my card?');
    expect(await within(dialog).findByText(/busy right now/)).toBeInTheDocument();
    await waitFor(() => expect(within(dialog).getByRole('textbox', { name: 'Message' })).toBeEnabled());
  });

  test('blocks a second question while one is being answered', async () => {
    let resolve;
    askAssistant.mockReturnValue(new Promise(r => { resolve = r; }));
    const user = userEvent.setup();
    render(<AssistantChat />);
    const dialog = await openChat(user);

    await ask(user, 'first question');
    await user.type(within(dialog).getByRole('textbox', { name: 'Message' }), 'second');
    expect(within(dialog).getByRole('button', { name: 'Send' })).toBeDisabled();
    expect(within(dialog).getByRole('switch', { name: 'My data' })).toBeDisabled();
    resolve(HELP_ANSWER);
    await within(dialog).findByText('Add payment');
    expect(askAssistant).toHaveBeenCalledTimes(1);
  });

  test('works under React StrictMode (double mount in development)', async () => {
    // Regression: the "still mounted" flag stayed false after StrictMode's test unmount,
    // so usage and answers were silently dropped. Found in the end-to-end test.
    askAssistant.mockResolvedValue(HELP_ANSWER);
    const user = userEvent.setup();
    render(<StrictMode><AssistantChat /></StrictMode>);
    const dialog = await openChat(user);
    expect(await within(dialog).findByText(/47 of 50 questions/)).toBeInTheDocument();
    await ask(user, 'How do I pay my card?');
    expect(await within(dialog).findByText('Add payment')).toBeInTheDocument();
  });

  test('my data follow-ups carry the earlier turns of that mode', async () => {
    askAssistant.mockResolvedValueOnce(HELP_ANSWER).mockResolvedValue(DATA_ANSWER);
    const user = userEvent.setup();
    render(<AssistantChat />);
    const dialog = await openChat(user);

    await ask(user, 'How do I pay my card?');                   // help mode: not part of data history
    await within(dialog).findByText('Add payment');
    await user.click(within(dialog).getByRole('switch', { name: 'My data' }));
    await ask(user, 'What is my bank balance?');
    await within(dialog).findByText(DATA_ANSWER.answer);
    await ask(user, 'and last month?');
    await waitFor(() => expect(askAssistant).toHaveBeenCalledTimes(3));

    expect(askAssistant.mock.calls[1]).toEqual(['What is my bank balance?', 'my_data', []]);
    expect(askAssistant.mock.calls[2]).toEqual(['and last month?', 'my_data',
      [{ question: 'What is my bank balance?', answer: DATA_ANSWER.answer }]]);
  });

  test('switching mode adds its welcome message once, even under StrictMode', async () => {
    const user = userEvent.setup();
    render(<StrictMode><AssistantChat /></StrictMode>);
    const dialog = await openChat(user);
    await user.click(within(dialog).getByRole('switch', { name: 'My data' }));
    expect(within(dialog).getAllByText(/Ask about your own data/)).toHaveLength(1);
  });

  test('help mode suggests My data when it finds nothing', async () => {
    askAssistant.mockResolvedValue({ ...HELP_ANSWER, answer: "I couldn't find this.", outcome: 'insufficient_context',
                                     citations: [] });
    const user = userEvent.setup();
    render(<AssistantChat />);
    const dialog = await openChat(user);
    await ask(user, 'what is my last transaction');
    expect(await within(dialog).findByText(HELP_DATA_HINT)).toBeInTheDocument();
  });

  test('row ids are not shown in the figures', async () => {
    askAssistant.mockResolvedValue({ ...DATA_ANSWER, answer: 'You spent ₹910 on food.', data: [{
      title: 'Picked by meaning: food', facts: { picked_total: 910 },
      tables: [{ title: 'Counted', columns: ['id', 'date', 'description', 'amount'],
                 rows: [[301, '2026-01-03', 'goa trip 31st bf', 620]] }],
    }] });
    const user = userEvent.setup();
    render(<AssistantChat />);
    const dialog = await openChat(user);
    await user.click(within(dialog).getByRole('switch', { name: 'My data' }));
    await ask(user, 'food in goa trip?');
    await user.click(await within(dialog).findByText('Figures used (1)'));
    const table = within(dialog).getByRole('table', { name: 'Counted' });
    expect(within(table).queryByText('Id')).not.toBeInTheDocument();
    expect(within(table).queryByText('301')).not.toBeInTheDocument();
    expect(within(table).getByText('goa trip 31st bf')).toBeInTheDocument();
    expect(within(table).getByText('₹620.00')).toBeInTheDocument();
  });

  test('the message box takes several lines: Shift+Enter adds a line, Enter sends', async () => {
    askAssistant.mockResolvedValue(HELP_ANSWER);
    const user = userEvent.setup();
    render(<AssistantChat />);
    await openChat(user);
    const box = screen.getByRole('textbox', { name: 'Message' });
    expect(box.tagName).toBe('TEXTAREA');
    await user.type(box, 'first line{Shift>}{Enter}{/Shift}second line');
    expect(box).toHaveValue('first line' + String.fromCharCode(10) + 'second line');
    expect(askAssistant).not.toHaveBeenCalled();
    await user.type(box, '{Enter}');
    expect(askAssistant).toHaveBeenCalledWith('first line' + String.fromCharCode(10) + 'second line', 'help', []);
  });

  test('limits questions to 500 characters', async () => {
    const user = userEvent.setup();
    render(<AssistantChat />);
    await openChat(user);
    expect(screen.getByRole('textbox', { name: 'Message' })).toHaveAttribute('maxLength', '500');
  });
});

describe('formatting helpers', () => {
  test('model text is never rendered as HTML', () => {
    const { container } = render(<FormattedText text={'<img src=x onerror="alert(1)"> **bold**\n- item'} />);
    expect(container.querySelector('img')).toBeNull();
    expect(container).toHaveTextContent('<img src=x onerror="alert(1)">');
    expect(container.querySelector('strong')).toHaveTextContent('bold');
    expect(container.querySelector('li')).toHaveTextContent('item');
  });

  test('model tables become real tables, still never HTML', () => {
    const text = [
      'Two rows:', '| Date | Amount |', '|------|-------:|', '| 2026-02-18 | **₹87.50** |', '| <b>x</b> | ₹305 |', 'Done.',
    ].join('\n');
    const { container } = render(<FormattedText text={text} />);
    const table = container.querySelector('table');
    expect(table).not.toBeNull();
    expect([...table.querySelectorAll('th')].map(th => th.textContent)).toEqual(['Date', 'Amount']);
    expect(table.querySelectorAll('tbody tr')).toHaveLength(2);           // separator line dropped
    expect(table.querySelector('strong')).toHaveTextContent('₹87.50');
    expect(table.querySelector('b')).toBeNull();                          // cell text stays text
    expect(container).toHaveTextContent('<b>x</b>');
    expect(container.querySelectorAll('p')).toHaveLength(2);              // text before and after
  });

  test('values are formatted by column meaning', () => {
    expect(formatValue('total_bank_balance', 123456.5)).toBe('₹1,23,456.50');
    expect(formatValue('share_pct', 37.5)).toBe('37.5%');
    expect(formatValue('expense_count', 1234)).toBe('1,234');
    expect(formatValue('categories_total', 9)).toBe('9');
    expect(formatValue('savings_accounts', 2)).toBe('2');
    expect(formatValue('note', null)).toBe('—');
    expect(formatValue('expense_largest', 2500)).toBe('₹2,500.00');
    expect(formatValue('groups_total', 6)).toBe('6');
    expect(formatValue('matched', 23)).toBe('23');
    expect(formatValue('left_out_money_movement_total', 23000)).toBe('₹23,000.00');
  });

  test('history keeps the last 3 answered turns of one mode, shortened', () => {
    const bot = (i, mode, extra = {}) => ({ from: 'bot', question: `q${i}`, text: `a${i}`, mode, ...extra });
    const messages = [
      { from: 'bot', text: 'welcome' }, bot(1, 'my_data'), bot(2, 'help'), bot(3, 'my_data', { error: true }),
      bot(4, 'my_data'), bot(5, 'my_data'), bot(6, 'my_data', { text: 'x'.repeat(700) }),
    ];
    const history = buildHistory(messages, 'my_data');
    expect(history.map(h => h.question)).toEqual(['q4', 'q5', 'q6']);
    expect(history[2].answer).toHaveLength(450);
  });

  test('history answers end with the search they used', () => {
    const result = { data: [{ facts: { query: 'money out (expenses) · words: goa · all time (no date filter)' } }] };
    const [turn] = buildHistory([{ from: 'bot', question: 'goa trip?', text: '₹39,893', mode: 'my_data', result }],
      'my_data');
    expect(turn.answer).toBe('₹39,893\nSearched: money out (expenses) · words: goa · all time (no date filter)');
  });

  test('usage line: questions and token percentage, or the free tier when caps are off', () => {
    const { usageLine } = require('./AssistantChat');
    expect(usageLine(USAGE, 47)).toBe('47 of 50 questions · 25% tokens left · resets 1:30 PM IST');
    const off = { ...USAGE, requests_used: 64, limits_enforced: false, token_budget: 200000,
                  token_budget_used: 170000, token_budget_left_pct: 15, token_budget_source: 'groq_free_tier' };
    expect(usageLine(off, 0)).toBe("64 today · 15% of Groq's free tokens left · resets 1:30 PM IST");
    const old = { requests_used: 3, requests_limit: 50, resets_at: USAGE.resets_at };   // older service
    expect(usageLine(old, 47)).toBe('47 of 50 questions · resets 1:30 PM IST');
  });

  test('reset time is shown in India time', () => {
    expect(formatResetTime('2026-11-25T08:00:00Z')).toBe('1:30 PM IST');
    expect(formatResetTime('not a date')).toBe('');
  });
});
