import axios from 'axios';
import { format } from 'date-fns';

//const API_URL = 'https://rs-ppa-backend.onrender.com';
//const API_URL = 'http://localhost:5000';

// Create an axios instance with base URL
const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL,
  withCredentials: true
});

// Attach token from localStorage
api.interceptors.request.use(config => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;

// User API calls
/*
export const createUser = async (userData) => {
  return api.post('/users', userData);
};
*/

export const getCurrentUser = async () => {
  const res = await api.get('/me');
  return res.data;
};

export const getUsers = async () => {
  const response = await api.get('/users');  // now returns only the logged-in user
  return response.data; // already an array with one user
};

export const updateUser = async (id, userData) => {
  return api.put(`/users/${id}`, userData);
};

export const deleteUser = async (id) => {
  return api.delete(`/users/${id}`);
};

export const canDeleteUser = async (id) => {
  return api.get(`/users/${id}/can_delete`);
};

// Bank API calls
export const getBanks = async () => {
  try {
    const response = await api.get('/banks');
    return { data: response.data };
  } catch (error) {
    const errorMsg = error.response?.data?.error || 'Failed to fetch banks';
    console.error('Error fetching banks:', errorMsg);
    throw new Error(errorMsg);
  }
};

export const createBank = async (bankData) => {
  try {
    const response = await api.post('/banks', {
      name: bankData.name,
      balance: 0
    }, {
      headers: { 'Content-Type': 'application/json' }
    });
    return response.data;
  } catch (error) {
    let errorMsg = 'Failed to create bank';
    if (error.response) {
      errorMsg = error.response.data?.error || errorMsg;
      console.error('Response error:', error.response.status, errorMsg);
    } else if (error.request) {
      errorMsg = 'No response received from server';
      console.error('No response received:', error.request);
    } else {
      console.error('Request setup error:', error.message);
    }
    throw new Error(errorMsg);
  }
};

export const updateBank = async (id, bankData) => {
  try {
    const response = await api.put(`/banks/${id}`, {
      name: bankData.name
    });
    return response.data;
  } catch (error) {
    const errorMsg = error.response?.data?.error || 'Failed to update bank';
    console.error('Error updating bank:', errorMsg);
    throw new Error(errorMsg);
  }
};

export const deleteBank = async (id) => {
  try {
    const response = await api.delete(`/banks/${id}`);
    return response.data;
  } catch (error) {
    const errorMsg = error.response?.data?.error || 
      'Cannot delete bank. It may have a non-zero balance or associated accounts.';
    console.error('Error deleting bank:', errorMsg);
    throw new Error(errorMsg);
  }
};

export const addBankTransaction = async (bankId, transactionData) => {
  try {
    const response = await api.post(`/banks/${bankId}/transactions`, {
      amount: transactionData.amount,
      type: transactionData.type || 'income',
      description: transactionData.description,
      category: transactionData.category
    });
    return response.data;
  } catch (error) {
    const errorMsg = error.response?.data?.error || 'Failed to add transaction';
    console.error('Error adding transaction:', errorMsg);
    throw new Error(errorMsg);
  }
};

export const getBankTransactions = async (bankId) => {
  try {
    const response = await api.get(`/banks/${bankId}/transactions`);
    return { data: response.data };
  } catch (error) {
    const errorMsg = error.response?.data?.error || 'Failed to fetch bank transactions';
    console.error('Error fetching bank transactions:', errorMsg);
    throw new Error(errorMsg);
  }
};

export const getBanksForUser = async () => {
  try {
    const response = await api.get('/banks/dropdown');
    return { data: response.data };
  } catch (error) {
    console.error('Error fetching user banks:', error);
    throw error;
  }
};

// Bank Balance API call
export const getBankBalance = async (bankId) => {
  try {
    const response = await api.get('/bank_balance', {
      params: { bank_id: bankId }
    });
    return response.data;
  } catch (error) {
    const errorMsg = error.response?.data?.error || 
      `Failed to fetch balance for bank ${bankId}`;
    console.error('Error fetching bank balance:', errorMsg);
    throw new Error(errorMsg);
  }
};

// Add this new function specifically for Bank page
export const getUsersForBank = async () => {
  try {
    const response = await api.get('/users');
    return { data: response.data };
  } catch (error) {
    console.error('Error fetching users:', error);
    throw error;
  }
};

// Asset API calls
export const createAsset = async (assetData) => {
  try {
    const response = await api.post('/assets', assetData);
    return response.data;
  } catch (error) {
    console.error("Error creating asset:", error.response?.data || error.message);
    throw error;
  }
};

export const getAssets = async () => {
  try {
    const response = await api.get('/assets');
    console.log("Fetched assets:", response.data);
    return response.data;
  } catch (error) {
    console.error("Error fetching assets:", error);
    throw error;
  }
};

export const updateAsset = async (id, assetData) => {
  const { balance, ...safeData } = assetData; 
  try {
    const response = await api.put(`/assets/${id}`, safeData);
    return response.data;
  } catch (error) {
    console.error("Error updating asset:", error.response?.data || error.message);
    throw error;
  }
};

export const deleteAsset = async (id) => {
  try {
    const response = await api.delete(`/assets/${id}`);
    return response.data;
  } catch (error) {
    console.error("Error deleting asset:", error.response?.data || error.message);
    throw error;
  }
};

export const createAssetTransaction = async (assetId, transactionData) => {
  return api.post(`/assets/${assetId}/transactions`, transactionData);
};

export const getAssetTransactions = async (assetId) => {
  return api.get(`/assets/${assetId}/transactions`);
};

// Credit Card API calls
export const createCreditCard = async (cardData) => {
  try {
    const response = await api.post('/credit_cards', cardData);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to create credit card: ${errorMessage}`);
  }
};

export const getCreditCards = async () => {
  try {
    const response = await api.get('/credit_cards');
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to fetch credit cards: ${errorMessage}`);
  }
};

export const getCreditCard = async (cardId) => {
  try {
    const response = await api.get(`/credit_cards/${cardId}`);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to fetch credit card: ${errorMessage}`);
  }
};

export const getUserCreditCards = async (userId) => {
  try {
    const response = await api.get(`/users/${userId}/credit_cards`);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to fetch user credit cards: ${errorMessage}`);
  }
};

export const updateCreditCard = async (cardId, updateData) => {
  try {
    const forbiddenFields = ['used', 'available_limit', 'billed_unpaid', 'unbilled_spends'];
    for (const field of forbiddenFields) {
      if (field in updateData) {
        throw new Error(`Cannot update calculated field: ${field}`);
      }
    }

    const response = await api.put(`/credit_cards/${cardId}`, updateData);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to update credit card: ${errorMessage}`);
  }
};

export const deleteCreditCard = async (cardId) => {
  try {
    const response = await api.delete(`/credit_cards/${cardId}`);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to delete credit card: ${errorMessage}`);
  }
};

export const getCreditCardTransactions = async (cardId) => {
  try {
    const response = await api.get(`/credit_cards/${cardId}/transactions`);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to fetch credit card transactions: ${errorMessage}`);
  }
};

export const addCreditCardTransaction = async (cardId, transactionData) => {
  try {
    if (!transactionData.amount || !transactionData.date) {
      throw new Error('Amount and transaction date are required');
    }

    if (typeof transactionData.date === 'object') {
      transactionData.date = format(transactionData.date, 'ddMMyyyy');
    }

    const response = await api.post(
      `/credit_cards/${cardId}/transactions`,
      transactionData
    );
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to add credit card transaction: ${errorMessage}`);
  }
};

export const processBilling = async (cardId) => {
  try {
    const response = await api.post(`/credit_cards/${cardId}/process_billing`);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to process billing: ${errorMessage}`);
  }
};

// Saving API calls
export const createSaving = async (savingData) => {
  try {
    const response = await api.post('/savings', savingData);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to create saving: ${errorMessage}`);
  }
};

export const getSavings = async () => {
  try {
    const response = await api.get('/savings');
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to fetch savings: ${errorMessage}`);
  }
};

export const updateSaving = async (savingId, updateData) => {
  try {
    if ('balance' in updateData) {
      throw new Error('Cannot update balance directly. Use transactions instead.');
    }

    const response = await api.put(`/savings/${savingId}`, updateData);
    
    if (response.data.bank_balance !== undefined) {
      return {
        ...response.data,
        message: response.data.message || 'Saving updated with bank balance adjustment'
      };
    }
    
    return response.data;
  } catch (error) {
    if (error.response?.data?.error?.includes('insufficient funds')) {
      throw new Error(
        `Bank change failed: ${error.response.data.error}. ` +
        'The new bank does not have enough funds to cover this saving account balance.'
      );
    }
    
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to update saving: ${errorMessage}`);
  }
};

export const deleteSaving = async (savingId) => {
  try {
    const response = await api.delete(`/savings/${savingId}`);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to delete saving: ${errorMessage}`);
  }
};

export const getSavingTransactions = async (savingId) => {
  try {
    const response = await api.get(`/savings/${savingId}/transactions`);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to fetch saving transactions: ${errorMessage}`);
  }
};

export const addSavingTransaction = async (savingId, transactionData) => {
  try {
    if (!transactionData.amount || !transactionData.type) {
      throw new Error('Amount and transaction type are required');
    }
    
    const response = await api.post(
      `/savings/${savingId}/transactions`,
      transactionData
    );
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to add saving transaction: ${errorMessage}`);
  }
};

// Transfer API calls
export const createTransfer = async (transferData) => {
  return api.post('/transfers', transferData);
};

export const getBanksByUser = async () => {
  try {
    const response = await api.get('/banks/dropdown');
    return response.data;
  } catch (error) {
    throw error.response?.data || error.message;
  }
};