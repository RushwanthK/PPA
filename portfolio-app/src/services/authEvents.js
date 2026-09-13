const SESSION_EXPIRED_EVENT = 'ppa:session-expired';

export const notifySessionExpired = () => {
  window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
};

export const onSessionExpired = handler => {
  window.addEventListener(SESSION_EXPIRED_EVENT, handler);

  return () => {
    window.removeEventListener(SESSION_EXPIRED_EVENT, handler);
  };
};