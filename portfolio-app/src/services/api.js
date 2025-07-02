import axios from 'axios';
import { format } from 'date-fns';

const API_URL = 'https://rs-ppa-backend.onrender.com';
//const API_URL = 'http://localhost:5000';

// User API calls
export const createUser = async (userData) => {
  return axios.post(`${API_URL}/users`, userData);
};

export const getUsers = async () => {
  try {
    const response = await axios.get(`${API_URL}/users`);
    return response.data;// ✅ consistent with rest of your api.js
  } catch (error) {
    console.error('Error fetching users:', error);
    throw error;
  }
};
/*
//new getusers
export const getUsers = async () => {
  try {
    const response = await axios.get(`${API_URL}/users`);
    return { data: response.data }; // Wrap the array in a data property
  } catch (error) {
    console.error('Error fetching users:', error);
    throw error;
  }
};*/

export const updateUser = async (id, userData) => {
  return axios.put(`${API_URL}/users/${id}`, userData);
};

export const deleteUser = async (id) => {
  return axios.delete(`${API_URL}/users/${id}`);
};

export const canDeleteUser = async (id) => {
  return axios.get(`${API_URL}/users/${id}/can_delete`);
};

// Bank API calls
export const getBanks = async () => {
  try {
    const response = await axios.get(`${API_URL}/banks`);
    return { data: response.data };
  } catch (error) {
    const errorMsg = error.response?.data?.error || 'Failed to fetch banks';
    console.error('Error fetching banks:', errorMsg);
    throw new Error(errorMsg);
  }
};

export const createBank = async (bankData) => {
  try {
    const response = await axios.post(`${API_URL}/banks`, {
      name: bankData.name,
      user_id: bankData.userId,
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
    const response = await axios.put(`${API_URL}/banks/${id}`, {
      name: bankData.name,
      user_id: bankData.user_id
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
    const response = await axios.delete(`${API_URL}/banks/${id}`);
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
    const response = await axios.post(`${API_URL}/banks/${bankId}/transactions`, {
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
    const response = await axios.get(`${API_URL}/banks/${bankId}/transactions`);
    return { data: response.data };
  } catch (error) {
    const errorMsg = error.response?.data?.error || 'Failed to fetch bank transactions';
    console.error('Error fetching bank transactions:', errorMsg);
    throw new Error(errorMsg);
  }
};

export const getBanksForUser = async (userId) => {
  try {
    const response = await axios.get(`${API_URL}/banks_dropdown`, {
      params: { user_id: userId }
    });
    return { data: response.data }; // Wrap in data property
  } catch (error) {
    console.error('Error fetching user banks:', error);
    throw error;
  }
};

// Bank Balance API call
export const getBankBalance = async (bankId) => {
  try {
    const response = await axios.get(`${API_URL}/bank_balance`, {
      params: { bank_id: bankId }
    });
    return response.data; // Returns { id, name, balance }
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
    const response = await axios.get(`${API_URL}/users`);
    return { data: response.data }; // Wrap the array in a data property
  } catch (error) {
    console.error('Error fetching users:', error);
    throw error;
  }
};

// Asset API calls
export const createAsset = async (assetData) => {
  try {
    const response = await axios.post(`${API_URL}/assets`, assetData);
    return response.data;
  } catch (error) {
    console.error("Error creating asset:", error.response?.data || error.message);
    throw error;
  }
};

export const getAssets = async () => {
  try {
    const response = await axios.get(`${API_URL}/assets`);
    console.log("Fetched assets:", response.data); // Debugging line
    return response.data;
  } catch (error) {
    console.error("Error fetching assets:", error);
    throw error;
  }
};

export const updateAsset = async (id, assetData) => {
  // Explicitly remove balance if included
  const { balance, ...safeData } = assetData; 
  try {
    const response = await axios.put(`${API_URL}/assets/${id}`, safeData);
    return response.data;
  } catch (error) {
    console.error("Error updating asset:", error.response?.data || error.message);
    throw error;
  }
};

export const deleteAsset = async (id) => {
  try {
    const response = await axios.delete(`${API_URL}/assets/${id}`);
    return response.data;
  } catch (error) {
    console.error("Error deleting asset:", error.response?.data || error.message);
    throw error;
  }
};

export const createAssetTransaction = async (assetId, transactionData) => {
  return axios.post(`${API_URL}/assets/${assetId}/transactions`, transactionData);
};

export const getAssetTransactions = async (assetId) => {
  return axios.get(`${API_URL}/assets/${assetId}/transactions`);
};

// Credit Card API calls
export const createCreditCard = async (cardData) => {
  try {
    const response = await axios.post(`${API_URL}/credit_cards`, cardData);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to create credit card: ${errorMessage}`);
  }
};

export const getCreditCards = async () => {
  try {
    const response = await axios.get(`${API_URL}/credit_cards`);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to fetch credit cards: ${errorMessage}`);
  }
};

export const getCreditCard = async (cardId) => {
  try {
    const response = await axios.get(`${API_URL}/credit_cards/${cardId}`);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to fetch credit card: ${errorMessage}`);
  }
};

export const getUserCreditCards = async (userId) => {
  try {
    const response = await axios.get(`${API_URL}/users/${userId}/credit_cards`);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to fetch user credit cards: ${errorMessage}`);
  }
};

export const updateCreditCard = async (cardId, updateData) => {
  try {
    // Client-side validation for calculated fields
    const forbiddenFields = ['used', 'available_limit', 'billed_unpaid', 'unbilled_spends'];
    for (const field of forbiddenFields) {
      if (field in updateData) {
        throw new Error(`Cannot update calculated field: ${field}`);
      }
    }

    const response = await axios.put(`${API_URL}/credit_cards/${cardId}`, updateData);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to update credit card: ${errorMessage}`);
  }
};

export const deleteCreditCard = async (cardId) => {
  try {
    const response = await axios.delete(`${API_URL}/credit_cards/${cardId}`);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to delete credit card: ${errorMessage}`);
  }
};

export const getCreditCardTransactions = async (cardId) => {
  try {
    const response = await axios.get(`${API_URL}/credit_cards/${cardId}/transactions`);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to fetch credit card transactions: ${errorMessage}`);
  }
};

export const addCreditCardTransaction = async (cardId, transactionData) => {
  try {
    // Validate required fields
    if (!transactionData.amount || !transactionData.date) {
      throw new Error('Amount and transaction date are required');
    }

    // Format date to DDMMYYYY if not already formatted
    if (typeof transactionData.date === 'object') {
      transactionData.date = format(transactionData.date, 'ddMMyyyy');
    }

    const response = await axios.post(
      `${API_URL}/credit_cards/${cardId}/transactions`,
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
    const response = await axios.post(`${API_URL}/credit_cards/${cardId}/process_billing`);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to process billing: ${errorMessage}`);
  }
};

// Saving API calls
export const createSaving = async (savingData) => {
  try {
    const response = await axios.post(`${API_URL}/savings`, savingData);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to create saving: ${errorMessage}`);
  }
};

export const getSavings = async () => {
  try {
    const response = await axios.get(`${API_URL}/savings`);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to fetch savings: ${errorMessage}`);
  }
};

export const updateSaving = async (savingId, updateData) => {
  try {
    // Client-side validation to prevent direct balance updates
    if ('balance' in updateData) {
      throw new Error('Cannot update balance directly. Use transactions instead.');
    }

    const response = await axios.put(`${API_URL}/savings/${savingId}`, updateData);
    
    // Handle the case where bank balance might be included in response
    if (response.data.bank_balance !== undefined) {
      return {
        ...response.data,
        message: response.data.message || 'Saving updated with bank balance adjustment'
      };
    }
    
    return response.data;
  } catch (error) {
    // Handle specific error cases from the new backend logic
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
    const response = await axios.delete(`${API_URL}/savings/${savingId}`);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to delete saving: ${errorMessage}`);
  }
};

export const getSavingTransactions = async (savingId) => {
  try {
    const response = await axios.get(`${API_URL}/savings/${savingId}/transactions`);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.error || error.message;
    throw new Error(`Failed to fetch saving transactions: ${errorMessage}`);
  }
};

export const addSavingTransaction = async (savingId, transactionData) => {
  try {
    // Validate required fields
    if (!transactionData.amount || !transactionData.type) {
      throw new Error('Amount and transaction type are required');
    }
    
    const response = await axios.post(
      `${API_URL}/savings/${savingId}/transactions`,
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
  return axios.post(`${API_URL}/transfers`, transferData);
};

export const getBanksByUser = async (userId) => {
  try {
    const response = await axios.get(`${API_URL}/banks_dropdown?user_id=${userId}`);
    return response.data;
  } catch (error) {
    throw error.response?.data || error.message;
  }
};