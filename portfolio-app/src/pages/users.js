import React, { useState, useEffect } from 'react';
import { getUsers, updateUser, deleteUser, canDeleteUser } from '../services/api';
import './users.css';

const Users = () => {
  const [users, setUsers] = useState([]);
  const [updatedUser, setUpdatedUser] = useState({ 
    id: '', 
    name: '',  
    dob: '', 
    place: '',
    password: '',       
    confirmPassword: '' 
  });
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notification, setNotification] = useState({ show: false, message: '', type: '' });
  const [isDeleting, setIsDeleting] = useState(false);

  const showNotification = (message, type = 'success') => {
    setNotification({ show: true, message, type });
    setTimeout(() => setNotification({ show: false, message: '', type: '' }), 3000);
  };

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        setLoading(true);
        const response = await getUsers();
        console.log('API Response:', response);
        setUsers(response);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch users:', err);
        setError('Failed to load users. Please try again.');
        setUsers([]);
        showNotification('Failed to load users. Please try again.', 'error');
      } finally {
        setLoading(false);
      }
    };

    fetchUsers();
  }, []);

  const handleUpdateUser = async () => {
    // Password validation
    if (updatedUser.password && updatedUser.password !== updatedUser.confirmPassword) {
      showNotification("Passwords do not match", "error");
      return;
    }

    try {
      setLoading(true);
      const updatePayload = {
        name: updatedUser.name,
        dob: updatedUser.dob,
        place: updatedUser.place
      };

      if (updatedUser.password) {
        updatePayload.password = updatedUser.password;
      }

      const response = await updateUser(updatedUser.id, updatePayload);
      
      setUsers(prevUsers => 
        prevUsers.map(user => 
          user.id === updatedUser.id ? response.data : user
        )
      );
      
      setUpdatedUser({ id: '', name: '', dob: '', place: '', password: '', confirmPassword: '' });
      setIsEditing(false);
      showNotification('User updated successfully!');
    } catch (err) {
      console.error('Failed to update user:', err);
      const errorMessage = err.response?.data?.error || 'Failed to update user. Please try again.';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteUser = async (id) => {
  if (isDeleting) return;
  
  try {
    setIsDeleting(true);
    const checkResponse = await canDeleteUser(id);
    
    if (!checkResponse.data.can_delete) {
      // Updated error message handling based on backend response
      const errorDetails = checkResponse.data.details || {};
      const reasons = [];
      
      if (errorDetails.has_bank_balances) reasons.push("bank accounts");
      if (errorDetails.has_asset_balances) reasons.push("assets");
      if (errorDetails.has_saving_balances) reasons.push("savings");
      if (errorDetails.has_credit_balances) reasons.push("credit cards");
      
      const errorMessage = checkResponse.data.message || 
        `Cannot delete user account. Please clear balances from ${reasons.join(', ')} and try again.`;
      
      setError(errorMessage);
      setIsDeleting(false);
      return;
    }

    // Proceed with deletion if no balances
    if (!window.confirm("Are you sure you want to delete this user?")) {
      setIsDeleting(false);
      return;
    }
    
    await deleteUser(id);
    setUsers(prevUsers => prevUsers.filter(user => user.id !== id));
    showNotification('User deleted successfully!');
    
    // Log out after deletion
    localStorage.removeItem('token');
    window.location.href = '/';
  } catch (err) {
    console.error('Failed to delete user:', err);
    const errorMessage = err.response?.data?.error || 
      err.response?.data?.message || 
      'Failed to delete user. Please try again.';
    setError(errorMessage);
  } finally {
    setIsDeleting(false);
  }
};

  const handleEditClick = (user) => {
    // Format the date for the date input field (YYYY-MM-DD)
    const formattedDob = user.dob.split('T')[0];
    setUpdatedUser({
      id: user.id,
      name: user.name,
      dob: formattedDob,
      place: user.place,
      password: '',       // Initialize empty
      confirmPassword: '' // Initialize empty
    });
    setIsEditing(true);
  };

  if (loading && !isEditing) {
    return (
      <div className="loading-overlay">
        <div className="loading-spinner"></div>
      </div>
    );
  }

  
  return (
    <div className="users-container">
      {notification.show && (
        <div className={`notification ${notification.type}`}>
          {notification.message}
        </div>
      )}

      <h2>Edit Profile</h2>
      
      {error && (
        <div className="error">
          <span>{error}</span>
          <button className="error-dismiss" onClick={() => setError(null)} aria-label="Dismiss error">
            &times;
          </button>
        </div>
      )}

      {loading ? (
        <div className="loading">Loading users...</div>
      ) : users && users.length > 0 ? (
        <ul className="user-list">
          {users.map(user => (
            <li key={user.id} className="user-item">
              <div className="user-main-info">
                <span className="user-name">{user.name}</span>
                <div className="user-actions">
                  <button 
                    onClick={() => handleEditClick(user)}
                    disabled={loading}
                    className="edit-btn"
                  >
                    Edit
                  </button>
                  <button 
                    className="delete-button" 
                    onClick={() => handleDeleteUser(user.id)}
                    disabled={loading || isDeleting}
                  >
                    {isDeleting ? 'Deleting...' : 'Delete'}
                  </button>
                </div>
              </div>
              <div className="user-additional-info">
                <span>Age: {user.age}</span>
                <span>Location: {user.place}</span>
                <span>DOB: {new Date(user.dob).toLocaleDateString()}</span>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p>No users found.</p>
      )}

      {isEditing && (
        <div className="form-container">
          <h3>Update User</h3>
          <form onSubmit={(e) => {
            e.preventDefault();
            handleUpdateUser();
          }}>
            <input 
              type="text" 
              placeholder="Name" 
              value={updatedUser.name} 
              onChange={(e) => setUpdatedUser({ ...updatedUser, name: e.target.value })} 
              required
              disabled={loading}
            />
            
            <input 
              type="date" 
              placeholder="Date of Birth" 
              value={updatedUser.dob} 
              onChange={(e) => setUpdatedUser({ ...updatedUser, dob: e.target.value })} 
              required
              disabled={loading}
              max={new Date().toISOString().split('T')[0]}
            />
            <input 
              type="text" 
              placeholder="Place" 
              value={updatedUser.place} 
              onChange={(e) => setUpdatedUser({ ...updatedUser, place: e.target.value })} 
              required
              disabled={loading}
            />
            <input
              type="password"
              placeholder="New Password (optional)"
              value={updatedUser.password}
              onChange={(e) => setUpdatedUser({ ...updatedUser, password: e.target.value })}
              disabled={loading}
            />
            <input
              type="password"
              placeholder="Confirm Password"
              value={updatedUser.confirmPassword}
              onChange={(e) => setUpdatedUser({ ...updatedUser, confirmPassword: e.target.value })}
              disabled={loading}
            />
            <div className="form-buttons">
              <button 
                type="submit" 
                className="create-btn"
                disabled={loading}
              >
                {loading ? 'Updating...' : 'Update'}
              </button>
              <button 
                type="button" 
                className="cancel-btn" 
                onClick={() => setIsEditing(false)}
                disabled={loading}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};

export default Users;