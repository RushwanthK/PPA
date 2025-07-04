import React, { useState, useEffect } from 'react';
import { getUsers, createUser, updateUser, deleteUser, canDeleteUser } from '../services/api';
import './users.css';

const Users = () => {
  const [users, setUsers] = useState([]);
  const [newUser, setNewUser] = useState({ 
    name: '',  
    dob: '', 
    place: '' 
  });
  const [updatedUser, setUpdatedUser] = useState({ 
    id: '', 
    name: '',  
    dob: '', 
    place: '' 
  });
  const [isEditing, setIsEditing] = useState(false);
  const [isAddingUser, setIsAddingUser] = useState(false);
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

  const handleCreateUser = async () => {
    try {
      setLoading(true);
      const response = await createUser(newUser);
      
      setUsers(prevUsers => [...prevUsers, response.data]);
      setNewUser({ name: '', dob: '', place: '' }); // Removed age from reset
      setIsAddingUser(false);
      showNotification('User created successfully!');
    } catch (err) {
      console.error('Failed to create user:', err);
      const errorMessage = err.response?.data?.error || 'Failed to create user. Please try again.';
      showNotification(errorMessage, 'error');
    } finally {
      setLoading(false);
    }
  };
  

  const handleUpdateUser = async () => {
    try {
      setLoading(true);
      const response = await updateUser(updatedUser.id, {
        name: updatedUser.name,
        dob: updatedUser.dob,
        place: updatedUser.place
      });
      
      setUsers(prevUsers => 
        prevUsers.map(user => 
          user.id === updatedUser.id ? response.data : user
        )
      );
      
      setUpdatedUser({ id: '', name: '', dob: '', place: '' }); // Removed age from reset
      setIsEditing(false);
      showNotification('User updated successfully!');
    } catch (err) {
      console.error('Failed to update user:', err);
      const errorMessage = err.response?.data?.error || 'Failed to update user. Please try again.';
      showNotification(errorMessage, 'error');
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
        const warnings = [];
        if (checkResponse.data.has_bank_balances) warnings.push("bank accounts with balance");
        if (checkResponse.data.has_asset_balances) warnings.push("assets with balance");
        if (checkResponse.data.has_saving_balances) warnings.push("savings accounts with balance");
        if (checkResponse.data.has_credit_balances) warnings.push("credit cards with balance");
        
        const confirmMessage = `This user has ${warnings.join(', ')}.\n\n` +
          `Deleting will permanently remove all associated data.\n\n` +
          `Are you sure you want to proceed?`;
        
        if (!window.confirm(confirmMessage)) {
          setIsDeleting(false);
          return;
        }
      } else {
        if (!window.confirm("Are you sure you want to delete this user?")) {
          setIsDeleting(false);
          return;
        }
      }
      
      await deleteUser(id);
      setUsers(prevUsers => prevUsers.filter(user => user.id !== id));
      showNotification('User deleted successfully!');
    } catch (err) {
      console.error('Failed to delete user:', err);
      showNotification('Failed to delete user. Please try again.', 'error');
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
      place: user.place
    });
    setIsEditing(true);
  };

  if (loading && !isEditing && !isAddingUser) {
    return (
      <div className="loading-overlay">
        <div className="loading-spinner"></div>
      </div>
    );
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div className="users-container">
      {notification.show && (
        <div className={`notification ${notification.type}`}>
          {notification.message}
        </div>
      )}

      <h2>Users</h2>
      
      <button 
        className="add-user-btn" 
        onClick={() => setIsAddingUser(!isAddingUser)}
        disabled={loading}
      >
        {isAddingUser ? 'Cancel' : 'Add User'}
      </button>

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

      {isAddingUser && (
        <div className="form-container">
          <h3>Create User</h3>
          <form onSubmit={(e) => {
            e.preventDefault();
            handleCreateUser();
          }}>
            <input 
              type="text" 
              placeholder="Name" 
              value={newUser.name} 
              onChange={(e) => setNewUser({ ...newUser, name: e.target.value })} 
              required
              disabled={loading}
            />
            
            <input 
              type="date" 
              placeholder="Date of Birth" 
              value={newUser.dob} 
              onChange={(e) => setNewUser({ ...newUser, dob: e.target.value })} 
              required
              disabled={loading}
              max={new Date().toISOString().split('T')[0]} // Prevent future dates
            />
            <input 
              type="text" 
              placeholder="Place" 
              value={newUser.place} 
              onChange={(e) => setNewUser({ ...newUser, place: e.target.value })} 
              required
              disabled={loading}
            />
            <div className="form-buttons">
              <button 
                type="submit" 
                className="create-btn"
                disabled={loading}
              >
                {loading ? 'Creating...' : 'Create'}
              </button>
              <button 
                type="button" 
                className="cancel-btn" 
                onClick={() => setIsAddingUser(false)}
                disabled={loading}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
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
              max={new Date().toISOString().split('T')[0]} // Prevent future dates
            />
            <input 
              type="text" 
              placeholder="Place" 
              value={updatedUser.place} 
              onChange={(e) => setUpdatedUser({ ...updatedUser, place: e.target.value })} 
              required
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