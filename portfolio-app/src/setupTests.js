// Global test setup for Jest (run automatically by react-scripts before each
// test file).

// jest-dom adds custom matchers such as toBeInTheDocument(),
// toBeDisabled() and toHaveValue().
import '@testing-library/jest-dom';
import { TextDecoder, TextEncoder } from 'util';

// react-router v7 relies on TextEncoder/TextDecoder, which the jsdom version
// bundled with react-scripts does not provide.
if (typeof global.TextEncoder === 'undefined') {
  global.TextEncoder = TextEncoder;
}

if (typeof global.TextDecoder === 'undefined') {
  global.TextDecoder = TextDecoder;
}

// jsdom does not implement matchMedia. App.js uses it to decide whether the
// navigation menu should close after navigation (mobile vs desktop).
if (typeof window.matchMedia !== 'function') {
  window.matchMedia = query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}

// Recharts' ResponsiveContainer uses ResizeObserver, which jsdom lacks.
if (typeof window.ResizeObserver === 'undefined') {
  window.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

// Keep tests isolated: no stored login token leaks between tests.
afterEach(() => {
  window.localStorage.clear();
});
