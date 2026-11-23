import { act, render, screen } from '@testing-library/react';

import { startBackendRequest, useBackendStatus } from './backendStatus';

function StatusProbe() {
  const { phase } = useBackendStatus();
  return <span data-testid="phase">{phase}</span>;
}

const phase = () => screen.getByTestId('phase').textContent;

describe('backend status tracking', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test('moves from idle to connecting (2.5s) to waking (10s) for a slow request', () => {
    render(<StatusProbe />);
    expect(phase()).toBe('idle');

    let stop;
    act(() => {
      stop = startBackendRequest();
    });
    expect(phase()).toBe('idle');

    act(() => {
      jest.advanceTimersByTime(2500);
    });
    expect(phase()).toBe('connecting');

    act(() => {
      jest.advanceTimersByTime(7500);
    });
    expect(phase()).toBe('waking');

    act(() => {
      stop();
    });
    expect(phase()).toBe('idle');
  });

  test('a fast request never shows a status message', () => {
    render(<StatusProbe />);

    act(() => {
      const stop = startBackendRequest();
      jest.advanceTimersByTime(1000);
      stop();
      jest.advanceTimersByTime(20000);
    });

    expect(phase()).toBe('idle');
  });

  test('stays "waking" while any slow request is still in flight', () => {
    render(<StatusProbe />);

    let stopSlow;
    let stopFast;
    act(() => {
      stopSlow = startBackendRequest();
      jest.advanceTimersByTime(10000);
      stopFast = startBackendRequest();
    });
    expect(phase()).toBe('waking');

    act(() => {
      stopFast();
    });
    expect(phase()).toBe('waking');

    act(() => {
      stopSlow();
    });
    expect(phase()).toBe('idle');
  });

  test('calling stop twice is harmless', () => {
    render(<StatusProbe />);

    act(() => {
      const stop = startBackendRequest();
      stop();
      stop();
    });

    expect(phase()).toBe('idle');
  });
});
