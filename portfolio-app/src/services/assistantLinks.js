// src/services/assistantLinks.js
//
// "Click here" links under PPA Assistant help answers (Nov 27).
//
// The AI service sends only ACTION NAMES (e.g. "creditcard.add_transaction"), chosen by its
// own code from the help sections an answer cited; never URLs. This file is the only place
// that turns an action name into an address, so a link can only ever go to one of these
// pages and forms. Unknown names are ignored.
//
// When an action needs an account ("add a transaction to which card?"), the chat fetches
// the user's accounts LIVE from PPA with their own login (Flask returns only that user's
// accounts), so the list is always current and never stored here or seen by the AI model.
import { getAssets, getBanks, getCreditCards, getSavings } from './api';

const asList = response => {
  if (Array.isArray(response)) return response;
  if (Array.isArray(response?.data)) return response.data;
  return [];
};

export const ACCOUNT_KINDS = {
  creditcard: { fetch: getCreditCards, noun: 'card', plural: 'cards' },
  bank: { fetch: getBanks, noun: 'bank account', plural: 'bank accounts' },
  savings: { fetch: getSavings, noun: 'savings account', plural: 'savings accounts' },
  assets: { fetch: getAssets, noun: 'asset', plural: 'assets' },
};

const PAGES = {
  creditcard: { path: '/creditcard', name: 'Credit Cards', add: 'Add a credit card' },
  bank: { path: '/bank', name: 'Banks', add: 'Add a bank account' },
  savings: { path: '/savings', name: 'Savings', add: 'Add a savings account' },
  assets: { path: '/assets', name: 'Assets', add: 'Add an asset' },
  dashboard: { path: '/dashboard', name: 'Overview' },
};

// action name -> { page, path, open (the form to open, if any), label, needsAccount }
export const LINK_ACTIONS = Object.fromEntries(
  Object.entries(PAGES).flatMap(([page, info]) => {
    const entries = [[`${page}.open`, { page, path: info.path, label: `Open ${info.name}` }]];
    if (ACCOUNT_KINDS[page]) {
      const { noun } = ACCOUNT_KINDS[page];
      entries.push(
        [`${page}.add`, { page, path: info.path, open: 'add', label: info.add }],
        [`${page}.add_transaction`, { page, path: info.path, open: 'add-transaction', needsAccount: true,
          label: `Add a transaction to a ${noun}` }],
        [`${page}.view_transactions`, { page, path: info.path, open: 'view-transactions', needsAccount: true,
          label: `View a ${noun}'s transactions` }],
        [`${page}.delete`, { page, path: info.path, open: 'delete', needsAccount: true,
          label: `Delete a ${noun}` }],
      );
    }
    if (page === 'creditcard') {
      // Process Billing changes data, so a link only opens Card Details, where its button is.
      entries.push([`${page}.details`, { page, path: info.path, open: 'details', needsAccount: true,
        label: "Open a card's details (View Transactions, Process Billing, Edit, Delete)" }]);
    }
    return entries;
  }),
);

// Only the forms the pages know how to open from an address.
export const OPEN_FORMS = ['add', 'add-transaction', 'view-transactions', 'delete', 'details'];

export const linkUrl = (action, accountId) => {
  const def = LINK_ACTIONS[action];
  if (!def) return null;
  const params = new URLSearchParams();
  if (def.open) params.set('open', def.open);
  if (def.needsAccount && accountId != null) params.set('id', String(accountId));
  const query = params.toString();
  return query ? `${def.path}?${query}` : def.path;
};

export const fetchAccounts = async page => asList(await ACCOUNT_KINDS[page].fetch())
  .filter(account => account && account.id != null);

// Words that say what kind of account it is, not which one.
const GENERIC_WORDS = new Set(['card', 'cards', 'credit', 'debit', 'bank', 'banks', 'account', 'accounts',
  'savings', 'saving', 'asset', 'assets', 'fund', 'funds', 'the', 'and', 'my']);

const escapeRegExp = text => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const hasWord = (text, word) => new RegExp(`(^|[^a-z0-9])${escapeRegExp(word)}([^a-z0-9]|$)`).test(text);

// The one account the question names: "...my Slice card" (full name) or "...axis credit card"
// for "Axis Ace" (a distinctive word of its name). Used only when exactly one account matches.
export const accountNamedIn = (accounts, question) => {
  const text = String(question || '').toLowerCase();
  const unique = list => (list.length === 1 ? list[0] : null);
  const nameOf = account => String(account.name || '').trim().toLowerCase();
  const full = accounts.filter(account => nameOf(account).length >= 2 && hasWord(text, nameOf(account)));
  if (full.length) return unique(full);
  return unique(accounts.filter(account => nameOf(account).split(/[^a-z0-9]+/)
    .some(word => word.length >= 3 && !GENERIC_WORDS.has(word) && hasWord(text, word))));
};
