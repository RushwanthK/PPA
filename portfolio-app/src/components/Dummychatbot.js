// src/components/DummyChatbot.js
//
// Frontend-only placeholder for a future LLM-powered financial assistant.
// Everything here is local component state — there is NO network call,
// no API integration, and nothing is wired to a backend. It exists purely
// so the UI/UX for the feature can be reviewed before the real
// integration is built. Swap the `getCannedReply` function for a real
// API call later and the rest of this component keeps working as-is.
import React, { useState, useCallback, useRef, useEffect, useId } from 'react';
import './Dummychatbot.css';

const INITIAL_MESSAGES = [
  {
    id: 'welcome',
    from: 'bot',
    text: "Hi! I'm your finance assistant (preview). Once connected, I'll be able to analyze your spending, assets, and savings trends."
  }
];

// Small fixed pool of canned responses, cycled through deterministically
// so the demo behaves predictably rather than relying on Math.random().
const CANNED_REPLIES = [
  "This is just a preview — I can't analyze real data yet, but soon I will!",
  "Great question! Once I'm connected to your financial data, I'll be able to help with things like this.",
  "Noted! This chat is a UI placeholder for now — full analysis is coming in a future update.",
];

let messageCounter = 0;
const nextId = () => `msg-${Date.now()}-${messageCounter++}`;

export default function DummyChatbot() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState(INITIAL_MESSAGES);
  const [draft, setDraft] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const replyIndexRef = useRef(0);
  const typingTimeoutRef = useRef(null);
  const inputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const panelId = useId();

  // Clean up any pending "typing" timeout on unmount so it never fires
  // setState after the component (or the whole Dashboard page) is gone.
  useEffect(() => {
    return () => {
      if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
    };
  }, []);

  useEffect(() => {
    if (open) {
      inputRef.current?.focus();
    }
  }, [open]);

  // Auto-scroll to the latest message when the log grows.
  useEffect(() => {
    if (open) {
      messagesEndRef.current?.scrollIntoView({ block: 'nearest' });
    }
  }, [messages, isTyping, open]);

  const toggleOpen = useCallback(() => {
    setOpen(prev => !prev);
  }, []);

  const handleSend = useCallback((e) => {
    e.preventDefault();
    const trimmed = draft.trim();
    if (!trimmed) return;

    const userMessage = { id: nextId(), from: 'user', text: trimmed };
    setMessages(prev => [...prev, userMessage]);
    setDraft('');
    setIsTyping(true);

    // Simulated "thinking" delay purely for UI feel — no request is made.
    typingTimeoutRef.current = setTimeout(() => {
      const reply = CANNED_REPLIES[replyIndexRef.current % CANNED_REPLIES.length];
      replyIndexRef.current += 1;
      setMessages(prev => [...prev, { id: nextId(), from: 'bot', text: reply }]);
      setIsTyping(false);
    }, 600);
  }, [draft]);

  return (
    <div className="chatbot-root">
      {open && (
        <div className="chatbot-panel" role="dialog" aria-label="Finance assistant preview" id={panelId}>
          <div className="chatbot-header">
            <div className="chatbot-header-title">
              <span className="chatbot-status-dot" />
              Finance Assistant
              <span className="chatbot-badge">Preview</span>
            </div>
            <button
              type="button"
              className="chatbot-close"
              aria-label="Close chat"
              onClick={toggleOpen}
            >
              ×
            </button>
          </div>

          <div className="chatbot-messages">
            {messages.map(msg => (
              <div key={msg.id} className={`chatbot-bubble-row ${msg.from}`}>
                <div className={`chatbot-bubble ${msg.from}`}>{msg.text}</div>
              </div>
            ))}
            {isTyping && (
              <div className="chatbot-bubble-row bot">
                <div className="chatbot-bubble bot chatbot-typing" aria-label="Assistant is typing">
                  <span /><span /><span />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <form className="chatbot-input-row" onSubmit={handleSend}>
            <input
              ref={inputRef}
              type="text"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask about your finances…"
              aria-label="Message"
            />
            <button type="submit" className="chatbot-send" disabled={!draft.trim()}>
              Send
            </button>
          </form>
        </div>
      )}

      <button
        type="button"
        className="chatbot-fab"
        onClick={toggleOpen}
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={open ? 'Close finance assistant' : 'Open finance assistant'}
      >
        {open ? '×' : '💬'}
      </button>
    </div>
  );
}