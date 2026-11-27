// Client for the PPA AI service (FastAPI, ai_service/), separate from the Flask API.
//
// - Base URL comes from REACT_APP_AI_API_URL. When it is not set (for example in a
//   build where the AI service is not deployed), the chat panel is hidden.
// - Auth is the same login token as the Flask API, sent in the Authorization header.
//   The AI service checks it with Flask; no cookies are used.
// - A 401 means the login expired or was revoked: the app's normal session-expiry
//   handling logs the user out, exactly as for Flask calls.
import axios from 'axios';
import { notifySessionExpired } from './authEvents';

export const getAssistantUrl = () => (process.env.REACT_APP_AI_API_URL || '').replace(/\/+$/, '');

export const isAssistantConfigured = () => Boolean(getAssistantUrl());

const client = axios.create({ timeout: 60000 });

client.interceptors.request.use(config => {
  config.baseURL = getAssistantUrl();
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Turns any failure into an Error with a message that is safe to show the user.
const toUserError = error => {
  const status = error.response?.status;
  if (status === 401) {
    notifySessionExpired();
  }
  const serverMessage = error.response?.data?.error;
  let message;
  if (typeof serverMessage === 'string' && serverMessage) {
    message = serverMessage;
  } else if (status === 422) {
    message = 'Please check your question and try again.';
  } else if (error.code === 'ECONNABORTED') {
    message = 'The assistant took too long to answer. Please try again.';
  } else if (!error.response) {
    message = 'The assistant is not reachable right now. Please try again later.';
  } else {
    message = 'Something went wrong. Please try again.';
  }
  const err = new Error(message);
  err.status = status;
  return err;
};

// mode: 'help' (PPA help and finance notes) or 'my_data' (the user's own PPA data).
// history: earlier turns of this chat ({question, answer}, at most 3), sent in "My data"
// mode only so follow-ups like "what about all time?" make sense. The AI service uses them
// for this request only and never stores them.
export const askAssistant = async (question, mode = 'help', history = []) => {
  try {
    const body = { question, mode };
    if (mode === 'my_data' && history.length) body.history = history;
    const response = await client.post('/v1/ask', body);
    return response.data;
  } catch (error) {
    throw toUserError(error);
  }
};

export const getAssistantUsage = async () => {
  try {
    const response = await client.get('/v1/usage');
    return response.data;
  } catch (error) {
    throw toUserError(error);
  }
};
