import { useSyncExternalStore } from 'react';

const listeners = new Set();
const requests = new Map();

let nextRequestId = 0;
let currentSnapshot = {
  phase: 'idle',
};

const notify = () => {
  listeners.forEach(listener => listener());
};

const updateSnapshot = () => {
  let phase = 'idle';

  for (const request of requests.values()) {
    if (request.phase === 'waking') {
      phase = 'waking';
      break;
    }

    if (request.phase === 'connecting') {
      phase = 'connecting';
    }
  }

  if (phase === currentSnapshot.phase) {
    return;
  }

  currentSnapshot = { phase };
  notify();
};

const setRequestPhase = (requestId, phase) => {
  const request = requests.get(requestId);

  if (!request) {
    return;
  }

  request.phase = phase;
  updateSnapshot();
};

export const startBackendRequest = () => {
  const requestId = ++nextRequestId;
  let stopped = false;

  const request = {
    phase: 'pending',
    connectingTimer: null,
    wakingTimer: null,
  };

  requests.set(requestId, request);

  request.connectingTimer = window.setTimeout(() => {
    setRequestPhase(requestId, 'connecting');
  }, 2500);

  request.wakingTimer = window.setTimeout(() => {
    setRequestPhase(requestId, 'waking');
  }, 10000);

  return () => {
    if (stopped) {
      return;
    }

    stopped = true;

    const activeRequest = requests.get(requestId);

    if (activeRequest) {
      window.clearTimeout(activeRequest.connectingTimer);
      window.clearTimeout(activeRequest.wakingTimer);
    }

    requests.delete(requestId);
    updateSnapshot();
  };
};

export const subscribeBackendStatus = listener => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};

const getBackendStatus = () => currentSnapshot;

export const useBackendStatus = () => useSyncExternalStore(
  subscribeBackendStatus,
  getBackendStatus,
  getBackendStatus
);
