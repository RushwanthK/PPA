let mockHandlers;
let mockRequestInterceptor;

jest.mock('axios', () => ({
  // A plain function, not jest.fn: CRA resets mock implementations before each test.
  create: () => ({
    interceptors: { request: { use: fn => { mockRequestInterceptor = fn; } } },
    post: (...args) => mockHandlers.post(...args),
    get: (...args) => mockHandlers.get(...args),
  }),
}));

jest.mock('./authEvents', () => ({ notifySessionExpired: jest.fn() }));

const loadApi = () => {
  let api;
  jest.isolateModules(() => { api = require('./assistantApi'); });
  return api;
};

describe('assistantApi', () => {
  const OLD_ENV = process.env;

  beforeEach(() => {
    process.env = { ...OLD_ENV, REACT_APP_AI_API_URL: 'http://localhost:8001/' };
    mockHandlers = { post: jest.fn(), get: jest.fn() };
    localStorage.setItem('token', 'tok');
  });

  afterEach(() => {
    process.env = OLD_ENV;
    localStorage.clear();
  });

  test('is configured only when the URL is set', () => {
    expect(loadApi().isAssistantConfigured()).toBe(true);
    process.env.REACT_APP_AI_API_URL = '';
    expect(loadApi().isAssistantConfigured()).toBe(false);
  });

  test('sends the login token and the trimmed base URL', () => {
    loadApi();
    const config = mockRequestInterceptor({ headers: {} });
    expect(config.baseURL).toBe('http://localhost:8001');
    expect(config.headers.Authorization).toBe('Bearer tok');
  });

  test('askAssistant posts the question and mode', async () => {
    mockHandlers.post.mockResolvedValue({ data: { answer: 'hi' } });
    await expect(loadApi().askAssistant('q?', 'my_data')).resolves.toEqual({ answer: 'hi' });
    expect(mockHandlers.post).toHaveBeenCalledWith('/v1/ask', { question: 'q?', mode: 'my_data' });
  });

  test('history is sent in my data mode only', async () => {
    mockHandlers.post.mockResolvedValue({ data: { answer: 'hi' } });
    const history = [{ question: 'goa trip?', answer: '₹4,300' }];
    const api = loadApi();
    await api.askAssistant('and January?', 'my_data', history);
    await api.askAssistant('how do I add a card?', 'help', history);
    expect(mockHandlers.post).toHaveBeenNthCalledWith(1, '/v1/ask', { question: 'and January?', mode: 'my_data', history });
    expect(mockHandlers.post).toHaveBeenNthCalledWith(2, '/v1/ask', { question: 'how do I add a card?', mode: 'help' });
  });

  test('server error messages are passed through and 401 ends the session', async () => {
    const { notifySessionExpired } = require('./authEvents');
    mockHandlers.post.mockRejectedValue({ response: { status: 401, data: { error: 'Please log in to continue.' } } });
    await expect(loadApi().askAssistant('q?')).rejects.toThrow('Please log in to continue.');
    expect(notifySessionExpired).toHaveBeenCalled();
  });

  test('network failures get a friendly message', async () => {
    mockHandlers.get.mockRejectedValue({ message: 'Network Error' });
    await expect(loadApi().getAssistantUsage()).rejects.toThrow('not reachable');
  });
});
