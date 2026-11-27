// src/components/AssistantChat.js
//
// The PPA Assistant chat panel (RAG/AI phase, step 5). It replaces the earlier
// frontend-only DummyChatbot preview and keeps its look.
//
// Two modes:
// - Help (default): answers from PPA's help articles and finance notes, with sources.
// - My data: answers about the user's own PPA data. Off by default, with a notice
//   that the question and the needed figures go to the AI provider (Groq). Every
//   answer shows the figures it was based on, so the user can check it.
//   Follow-ups work: the last 3 questions and answers of this mode go with each new
//   question (fine-tuning phase, Nov 26), and the server keeps nothing.
//
// "Click here" links (help mode, Nov 27): the AI service sends action names, never URLs;
// services/assistantLinks.js maps them to PPA's own pages. When an action needs an account,
// the user's accounts are fetched live with their own login and they pick one here.
//
// Security: model output is shown as plain text. A tiny formatter turns **bold**
// and "- " bullets into React elements; nothing is ever rendered as HTML, so text
// from the model (or from transaction descriptions it repeats) cannot inject markup.
import React, { useCallback, useEffect, useId, useRef, useState } from 'react';
import { askAssistant, getAssistantUsage, isAssistantConfigured } from '../services/assistantApi';
import {
  ACCOUNT_KINDS, LINK_ACTIONS, accountNamedIn, fetchAccounts, linkUrl,
} from '../services/assistantLinks';
import './AssistantChat.css';

const MAX_CHARS = 500; // matches the AI service's QUESTION_MAX_CHARS

const WELCOME = {
  help: "Hi! Ask me how to use PPA or about personal-finance basics, like how SIPs or credit card billing work.",
  my_data: 'Ask about your own data, like "How much did I spend on food last month?" or "What are my card dues?"',
};

export const MY_DATA_NOTICE =
  'With "My data" on, your question and the figures needed to answer it are sent to Groq, ' +
  'the AI provider. Groq says it does not keep or train on this data by default. ' +
  'The assistant can only read your data; it cannot change anything.';

let messageCounter = 0;
const nextId = () => `msg-${Date.now()}-${messageCounter++}`;

// ---- Formatting -------------------------------------------------------------------

const MONEY_KEY = /(amount|balance|total|average|largest|smallest|limit|used|payable|value|net_worth|assets|debt|savings|spends|unpaid)/;
const COUNT_KEY = /(count|_pct|accounts|cards|found|matched|categories_listed|categories_total|groups_total)/;

// "My data" follow-ups: the last few turns of this mode go with each question, so
// "what about all time?" makes sense. Matches the AI service's limits.
const HISTORY_TURNS = 3;
const HISTORY_ANSWER_CHARS = 450;

// Row ids are for the assistant's "add up these rows" step, not for people.
const HIDDEN_COLUMNS = new Set(['id']);

export const HELP_DATA_HINT = 'Asking about your own figures? Turn on "My data" above.';

// Each answer is followed by the search it used ("Searched: money out · words: goa · all time"),
// so a follow-up like "how much of it was on the card?" can keep the same search.
const searchedLine = message => {
  const query = (message.result?.data || []).map(block => block.facts?.query).find(Boolean);
  return query ? `\nSearched: ${String(query).slice(0, 300)}` : '';
};

export const buildHistory = (messages, mode) =>
  messages
    .filter(m => m.from === 'bot' && m.question && m.mode === mode && !m.error)
    .slice(-HISTORY_TURNS)
    .map(m => ({
      question: m.question,
      answer: String(m.text || '').slice(0, HISTORY_ANSWER_CHARS) + searchedLine(m),
    }));

const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 });

export const formatValue = (key, value) => {
  if (typeof value !== 'number') return value === null || value === undefined ? '—' : String(value);
  const k = String(key).toLowerCase();
  if (k.includes('pct')) return `${value}%`;
  if (MONEY_KEY.test(k) && !COUNT_KEY.test(k)) return inr.format(value);
  return value.toLocaleString('en-IN');
};

const humanize = key => {
  const text = String(key).replace(/_/g, ' ');
  return text.charAt(0).toUpperCase() + text.slice(1);
};

// "**bold**" -> <strong>, everything else as text.
const renderInline = (text, keyPrefix) =>
  text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') && part.length > 4
      ? <strong key={`${keyPrefix}-${i}`}>{part.slice(2, -2)}</strong>
      : <React.Fragment key={`${keyPrefix}-${i}`}>{part}</React.Fragment>
  );

// "| a | b |" -> ['a', 'b']
const tableCells = line => line.replace(/^\|/, '').replace(/\|$/, '').split('|').map(cell => cell.trim());
const TABLE_SEPARATOR = /^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$/;

export function FormattedText({ text }) {
  const blocks = [];
  let bullets = [];
  let tableRows = [];
  const flush = () => {
    if (bullets.length) {
      blocks.push(<ul key={`ul-${blocks.length}`}>{bullets}</ul>);
      bullets = [];
    }
    if (tableRows.length) {
      // Model tables (seen live: raw "| Date | Type |" text). Built from React elements like
      // everything else here, so cell text can never become markup.
      const [head, ...body] = tableRows;
      const key = `table-${blocks.length}`;
      blocks.push(
        <div key={key} className="assistant-table-wrap">
          <table className="assistant-table">
            <thead><tr>{head.map((cell, c) => <th key={c} scope="col">{renderInline(cell, `${key}-h${c}`)}</th>)}</tr></thead>
            <tbody>
              {body.map((row, r) => (
                <tr key={r}>{row.map((cell, c) => <td key={c}>{renderInline(cell, `${key}-${r}-${c}`)}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      tableRows = [];
    }
  };
  String(text || '').split('\n').forEach((raw, i) => {
    const line = raw.trim();
    if (line.startsWith('|') && line.indexOf('|', 1) > 0) {
      if (bullets.length) flush();
      if (!TABLE_SEPARATOR.test(line)) tableRows.push(tableCells(line));
      return;
    }
    if (tableRows.length) flush();
    const bullet = line.match(/^[-*•]\s+(.*)$/);
    if (bullet) {
      bullets.push(<li key={`li-${i}`}>{renderInline(bullet[1], `li-${i}`)}</li>);
    } else {
      flush();
      if (line) blocks.push(<p key={`p-${i}`}>{renderInline(line, `p-${i}`)}</p>);
    }
  });
  flush();
  return <>{blocks}</>;
}

function Figures({ blocks }) {
  if (!blocks?.length) return null;
  return (
    <details className="assistant-figures">
      <summary>Figures used ({blocks.length})</summary>
      {blocks.map((block, b) => (
        <div key={`block-${b}`} className="assistant-figure-block">
          <div className="assistant-figure-title">{block.title}</div>
          <dl className="assistant-facts">
            {Object.entries(block.facts || {}).map(([key, value]) => (
              <React.Fragment key={key}>
                <dt>{humanize(key)}</dt>
                <dd>
                  {value && typeof value === 'object'
                    ? Object.entries(value).map(([k, v]) => `${humanize(k)}: ${v}`).join(', ') || '—'
                    : formatValue(key, value)}
                </dd>
              </React.Fragment>
            ))}
          </dl>
          {(block.tables || []).map((table, t) => (
            <div key={`table-${t}`} className="assistant-table-wrap">
              <table className="assistant-table">
                <caption>{table.title}</caption>
                <thead>
                  <tr>{table.columns.map(col => (HIDDEN_COLUMNS.has(col) ? null
                    : <th key={col} scope="col">{humanize(col)}</th>))}</tr>
                </thead>
                <tbody>
                  {table.rows.map((row, r) => (
                    <tr key={`row-${r}`}>
                      {row.map((cell, c) => (HIDDEN_COLUMNS.has(table.columns[c]) ? null
                        : <td key={`cell-${c}`}>{formatValue(table.columns[c], cell)}</td>))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      ))}
    </details>
  );
}

const NO_PICK = { action: null, accounts: [], note: null, loading: false };

// "Click here" buttons under a help answer, and the "Which card?" picker when needed.
export function PageLinks({ message, onNavigate }) {
  const [state, setState] = useState(NO_PICK);
  const actions = (message.result?.links || []).filter(action => LINK_ACTIONS[action]);
  if (message.mode !== 'help' || !actions.length) return null;

  const go = url => {
    if (url && onNavigate) onNavigate(url);
  };

  const choose = async action => {
    const def = LINK_ACTIONS[action];
    if (!def.needsAccount) {
      go(linkUrl(action));
      return;
    }
    const kind = ACCOUNT_KINDS[def.page];
    setState({ ...NO_PICK, loading: true });
    try {
      // Fetched now, every time: the list is always current and only this user's.
      const accounts = await fetchAccounts(def.page);
      if (!accounts.length) {
        const add = `${def.page}.add`;
        setState({ ...NO_PICK, note: `You have no ${kind.plural} yet, so this opens "${LINK_ACTIONS[add].label}".` });
        go(linkUrl(add));
        return;
      }
      const account = accounts.length === 1 ? accounts[0] : accountNamedIn(accounts, message.question);
      if (account) {
        setState(NO_PICK);
        go(linkUrl(action, account.id));
        return;
      }
      setState({ ...NO_PICK, action, accounts });
    } catch {
      setState({ ...NO_PICK, note: `Couldn't load your ${kind.plural} right now. Try again, or open the page from the menu.` });
    }
  };

  const picking = state.action ? ACCOUNT_KINDS[LINK_ACTIONS[state.action].page] : null;
  return (
    <div className="assistant-links">
      {actions.map(action => (
        <button key={action} type="button" className="assistant-link" disabled={state.loading}
                onClick={() => choose(action)}>
          Click here: {LINK_ACTIONS[action].label}
        </button>
      ))}
      {picking && (
        <div className="assistant-picker" role="group" aria-label={`Which ${picking.noun}?`}>
          <span>Which {picking.noun}?</span>
          {state.accounts.map(account => (
            <button key={account.id} type="button" className="assistant-pick"
                    onClick={() => { const action = state.action; setState(NO_PICK); go(linkUrl(action, account.id)); }}>
              {String(account.name ?? `#${account.id}`)}
            </button>
          ))}
        </div>
      )}
      {state.note && <p className="assistant-notice">{state.note}</p>}
    </div>
  );
}

function BotMessage({ message, onNavigate }) {
  const result = message.result;
  return (
    <div className={`chatbot-bubble bot ${message.error ? 'assistant-error' : ''}`}>
      <FormattedText text={message.text} />
      {result?.notice && <p className="assistant-notice">{result.notice}</p>}
      {message.mode === 'help' && result?.outcome === 'insufficient_context' && (
        <p className="assistant-notice">{HELP_DATA_HINT}</p>
      )}
      {result?.citations?.length > 0 && (
        <div className="assistant-sources">
          <span>Sources:</span>
          <ul>
            {result.citations.map(c => (
              <li key={c.id}>[{c.id}] {c.title}{c.section && c.section !== c.title ? ` — ${c.section.split(' > ').pop()}` : ''}</li>
            ))}
          </ul>
        </div>
      )}
      <PageLinks message={message} onNavigate={onNavigate} />
      <Figures blocks={result?.data} />
      {result?.disclaimer && <p className="assistant-disclaimer">{result.disclaimer}</p>}
    </div>
  );
}

// "2026-11-25T13:30:00+05:30" -> "1:30 PM IST"
export const formatResetTime = iso => {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return `${date.toLocaleTimeString('en-IN', {
    timeZone: 'Asia/Kolkata', hour: 'numeric', minute: '2-digit', hour12: true,
  }).toUpperCase()} IST`;
};

// The header line. Questions and tokens are both daily limits, and the tokens usually run
// out first (a "My data" question can use 3,000-9,000), so both are shown. With the per-user
// caps switched off (testing), the percentage is of Groq's free daily tokens, shared by all users.
export const usageLine = (usage, left) => {
  const resets = `resets ${formatResetTime(usage.resets_at)}`;
  const hasBudget = typeof usage.token_budget_left_pct === 'number' && usage.token_budget;
  if (usage.limits_enforced === false) {
    return `${usage.requests_used} today · ${usage.token_budget_left_pct}% of Groq's free tokens left · ${resets}`;
  }
  const tokens = hasBudget ? ` · ${usage.token_budget_left_pct}% tokens left` : '';
  return `${left} of ${usage.requests_limit} questions${tokens} · ${resets}`;
};

const usageTitle = usage => (usage.limits_enforced === false
  ? `Per-user daily limits are off (testing). ${usage.token_budget_used.toLocaleString('en-IN')} of ` +
    `${usage.token_budget.toLocaleString('en-IN')} free Groq tokens used today, by all users.`
  : 'Your daily assistant limit: questions and tokens');

// ---- Component ------------------------------------------------------------------------

// onNavigate: the app's router navigate (App.js), used by "Click here" links.
export default function AssistantChat({ onNavigate } = {}) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState('help');
  const [messages, setMessages] = useState([{ id: 'welcome', from: 'bot', text: WELCOME.help }]);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [usage, setUsage] = useState(null);
  const inputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const mountedRef = useRef(true);
  const panelId = useId();

  // Set on every mount, not only at creation: React StrictMode (development) mounts,
  // unmounts and mounts again, and a flag left false would silently drop every reply.
  // Found in the step 5 end-to-end test.
  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const refreshUsage = useCallback(async () => {
    try {
      const data = await getAssistantUsage();
      if (mountedRef.current) setUsage(data);
    } catch {
      // Usage is informational; the chat still works without it.
    }
  }, []);

  useEffect(() => {
    if (open) {
      inputRef.current?.focus();
      refreshUsage();
    }
  }, [open, refreshUsage]);

  useEffect(() => {
    if (open) messagesEndRef.current?.scrollIntoView?.({ block: 'nearest' });
  }, [messages, busy, open]);

  // The message box grows with the text (up to the CSS max-height, then scrolls), so a long
  // question is visible without moving the cursor sideways.
  useEffect(() => {
    const box = inputRef.current;
    if (!box) return;
    box.style.height = 'auto';
    box.style.height = `${box.scrollHeight}px`;
  }, [draft, open]);

  // State updaters must not set other state: StrictMode runs them twice in development,
  // which added the welcome message twice (seen in the fine-tuning test).
  const toggleMode = useCallback(() => {
    const next = mode === 'help' ? 'my_data' : 'help';
    setMode(next);
    setMessages(list => [...list, { id: nextId(), from: 'bot', text: WELCOME[next] }]);
  }, [mode]);

  const handleSend = useCallback(async (e) => {
    e.preventDefault();
    const question = draft.trim();
    if (!question || busy) return;

    const history = buildHistory(messages, mode);
    setMessages(prev => [...prev, { id: nextId(), from: 'user', text: question }]);
    setDraft('');
    setBusy(true);
    try {
      const result = await askAssistant(question, mode, history);
      if (!mountedRef.current) return;
      setMessages(prev => [...prev, { id: nextId(), from: 'bot', text: result.answer, result, question, mode }]);
    } catch (error) {
      if (!mountedRef.current) return;
      setMessages(prev => [...prev, { id: nextId(), from: 'bot', text: error.message, error: true }]);
    } finally {
      if (mountedRef.current) {
        setBusy(false);
        refreshUsage();
      }
    }
  }, [draft, busy, mode, messages, refreshUsage]);

  if (!isAssistantConfigured()) return null;

  const left = usage ? Math.max(0, usage.requests_limit - usage.requests_used) : null;

  return (
    <div className="chatbot-root">
      {open && (
        <div className="chatbot-panel" role="dialog" aria-label="PPA Assistant" id={panelId}>
          <div className="chatbot-header">
            <div className="chatbot-header-title">
              <span className="chatbot-status-dot" />
              PPA Assistant
            </div>
            <button type="button" className="chatbot-close" aria-label="Close chat" onClick={() => setOpen(false)}>
              ×
            </button>
          </div>

          <div className="assistant-mode-row">
            <label className="assistant-switch">
              <input
                type="checkbox"
                role="switch"
                checked={mode === 'my_data'}
                onChange={toggleMode}
                disabled={busy}
                aria-describedby={mode === 'my_data' ? `${panelId}-notice` : undefined}
              />
              <span>My data</span>
            </label>
            {usage && (
              <span className="assistant-usage" title={usageTitle(usage)}>
                {usageLine(usage, left)}
              </span>
            )}
          </div>
          {mode === 'my_data' && (
            <p className="assistant-privacy" id={`${panelId}-notice`}>{MY_DATA_NOTICE}</p>
          )}

          <div className="chatbot-messages" aria-live="polite">
            {messages.map(msg => (
              <div key={msg.id} className={`chatbot-bubble-row ${msg.from}`}>
                {msg.from === 'bot'
                  ? <BotMessage message={msg} onNavigate={onNavigate} />
                  : <div className="chatbot-bubble user">{msg.text}</div>}
              </div>
            ))}
            {busy && (
              <div className="chatbot-bubble-row bot">
                <div className="chatbot-bubble bot chatbot-typing" aria-label="Assistant is typing">
                  <span /><span /><span />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <form className="chatbot-input-row" onSubmit={handleSend}>
            <textarea
              ref={inputRef}
              rows={1}
              value={draft}
              maxLength={MAX_CHARS}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                // Enter sends; Shift+Enter starts a new line.
                if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  e.currentTarget.form?.requestSubmit?.();
                }
              }}
              placeholder={mode === 'my_data' ? 'Ask about your data…' : 'Ask about PPA or finance…'}
              aria-label="Message"
            />
            <button type="submit" className="chatbot-send" disabled={!draft.trim() || busy}>
              Send
            </button>
          </form>
        </div>
      )}

      <button
        type="button"
        className="chatbot-fab"
        onClick={() => setOpen(prev => !prev)}
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={open ? 'Close PPA Assistant' : 'Open PPA Assistant'}
      >
        {open ? '×' : '💬'}
      </button>
    </div>
  );
}
