// src/hooks/useAssistantLink.js
//
// Opens the form a PPA Assistant "Click here" link asked for (Nov 27), e.g.
// /creditcard?open=add-transaction&id=7, once the page has loaded the user's accounts.
//
// - The account is looked up ONLY among the accounts this page loaded for the logged-in
//   user. Another user's id (or a deleted account) is simply not found: nothing opens,
//   and the page shows a short message. The server checks ownership again on any action.
// - The instruction is removed from the address straight away (replace, not push), so a
//   refresh or the Back button does not open the form again.
// - It only opens a form. Nothing is saved or deleted without the user's own click.
import { useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { OPEN_FORMS } from '../services/assistantLinks';

export const ACCOUNT_NOT_FOUND = "That account wasn't found. It may have been deleted.";

export default function useAssistantLink({ ready, items, actions, onMissing }) {
  const [params, setParams] = useSearchParams();
  const latest = useRef({});
  latest.current = { items, actions, onMissing };

  const open = params.get('open');
  const id = params.get('id');

  useEffect(() => {
    if (!open || !ready) return;
    setParams(prev => {
      const next = new URLSearchParams(prev);
      next.delete('open');
      next.delete('id');
      return next;
    }, { replace: true });

    const { items: list, actions: handlers, onMissing: missing } = latest.current;
    const run = OPEN_FORMS.includes(open) ? handlers?.[open] : null;
    if (!run) return;
    if (open === 'add') {
      run();
      return;
    }
    const account = (list || []).find(item => String(item.id) === String(id));
    if (account) run(account);
    else missing?.(ACCOUNT_NOT_FOUND);
  }, [open, id, ready, setParams]);
}
