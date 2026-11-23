import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import ProfileDialog from './ProfileDialog';
import {
  canDeleteUser,
  deleteUser,
  exportUserTransactionsExcel,
  exportUserTransactionsPdf,
  logoutAllDevices,
  logoutSession,
  updateUser,
} from '../../services/api';

jest.mock('../../services/api', () => ({
  updateUser: jest.fn(),
  deleteUser: jest.fn(),
  canDeleteUser: jest.fn(),
  exportUserTransactionsExcel: jest.fn(),
  exportUserTransactionsPdf: jest.fn(),
  logoutSession: jest.fn(),
  logoutAllDevices: jest.fn(),
}));

const mockAuth = {
  user: null,
  setUser: jest.fn(),
  logout: jest.fn(),
};

jest.mock('../../AuthContext', () => ({
  useAuth: () => mockAuth,
}));

const USER = {
  id: 1,
  name: 'Rahul',
  dob: '1990-05-20',
  age: 36,
  place: 'Chennai',
};

// Shapes below mirror the real Flask responses in app/users/users_routes.py.
const canDeleteResponse = overrides => ({
  data: {
    can_delete: true,
    message: 'User can be deleted.',
    has_transaction_history: true,
    transaction_count: 42,
    details: {
      has_bank_balances: false,
      has_asset_balances: false,
      has_saving_balances: false,
      has_credit_balances: false,
    },
    ...overrides,
  },
});

const renderProfile = ({ open = true } = {}) => {
  const onClose = jest.fn();
  const user = userEvent.setup();

  render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <Routes>
        <Route
          path="/dashboard"
          element={<ProfileDialog open={open} onClose={onClose} />}
        />
        <Route path="/" element={<h1>Login page</h1>} />
      </Routes>
    </MemoryRouter>
  );

  return { onClose, user };
};

const openEdit = async user => {
  await user.click(screen.getByRole('button', { name: 'Edit profile' }));
  return screen.getByRole('dialog', { name: 'Edit Profile' });
};

const startDelete = async (user, response = canDeleteResponse()) => {
  canDeleteUser.mockResolvedValue(response);
  const edit = await openEdit(user);
  await user.click(within(edit).getByRole('button', { name: 'Delete Account' }));
};

describe('ProfileDialog', () => {
  beforeEach(() => {
    mockAuth.user = { ...USER };
    logoutSession.mockResolvedValue({ data: { message: 'Logged out' } });
    jest.spyOn(console, 'error').mockImplementation(() => {});
    jest.spyOn(console, 'info').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.clearAllMocks();
    jest.restoreAllMocks();
  });

  test('renders nothing when closed or when nobody is logged in', () => {
    const { unmount } = render(
      <MemoryRouter>
        <ProfileDialog open={false} onClose={jest.fn()} />
      </MemoryRouter>
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    unmount();

    mockAuth.user = null;
    renderProfile();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  test('shows the profile details', () => {
    renderProfile();

    const details = screen.getByLabelText('Profile details');
    const expectedDob = new Date('1990-05-20T00:00:00').toLocaleDateString();

    expect(details).toHaveTextContent('NameRahul');
    expect(details).toHaveTextContent(`Date of Birth${expectedDob}`);
    expect(details).toHaveTextContent('Age36');
    expect(details).toHaveTextContent('PlaceChennai');
  });

  test('Logout logs out, closes the dialog and returns to the login page', async () => {
    localStorage.setItem('token', 'current-token');
    const { onClose, user } = renderProfile();

    await user.click(screen.getByRole('button', { name: 'Logout' }));

    // The token is revoked on the backend (not awaited) and cleared locally.
    expect(logoutSession).toHaveBeenCalledWith('current-token');
    expect(mockAuth.logout).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('heading', { name: 'Login page' })).toBeInTheDocument();
  });

  test('Logout still logs out locally when the backend call fails', async () => {
    localStorage.setItem('token', 'current-token');
    logoutSession.mockRejectedValue(new Error('backend asleep'));
    const { user } = renderProfile();

    await user.click(screen.getByRole('button', { name: 'Logout' }));

    expect(mockAuth.logout).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('heading', { name: 'Login page' })).toBeInTheDocument();
  });

  test('Log out of all devices ends every session, then logs out here', async () => {
    logoutAllDevices.mockResolvedValue({ data: {} });
    const { onClose, user } = renderProfile();

    await user.click(screen.getByRole('button', { name: 'Log out of all devices' }));

    expect(logoutAllDevices).toHaveBeenCalledTimes(1);
    expect(mockAuth.logout).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(
      await screen.findByRole('heading', { name: 'Login page' })
    ).toBeInTheDocument();
  });

  test('Log out of all devices shows an error and stays logged in when it fails', async () => {
    logoutAllDevices.mockRejectedValue({ response: { status: 500 } });
    const { user } = renderProfile();

    await user.click(screen.getByRole('button', { name: 'Log out of all devices' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Could not log out of all devices. Please try again.'
    );
    expect(mockAuth.logout).not.toHaveBeenCalled();
    expect(
      screen.getByRole('button', { name: 'Log out of all devices' })
    ).toBeEnabled();
  });

  describe('editing the profile', () => {
    test('pre-fills the form with the current details', async () => {
      const { user } = renderProfile();

      const edit = await openEdit(user);

      expect(within(edit).getByLabelText('Name')).toHaveValue('Rahul');
      expect(within(edit).getByLabelText('Date of Birth')).toHaveValue('1990-05-20');
      expect(within(edit).getByLabelText('Place')).toHaveValue('Chennai');
      expect(within(edit).getByLabelText('New Password')).toHaveValue('');
    });

    test('saves without sending a password when it is left blank', async () => {
      const saved = { ...USER, place: 'Bengaluru' };
      updateUser.mockResolvedValue({ data: saved });
      const { user } = renderProfile();

      const edit = await openEdit(user);
      const place = within(edit).getByLabelText('Place');
      await user.clear(place);
      await user.type(place, 'Bengaluru');
      await user.click(within(edit).getByRole('button', { name: 'Save Changes' }));

      expect(updateUser).toHaveBeenCalledWith(1, {
        name: 'Rahul',
        dob: '1990-05-20',
        place: 'Bengaluru',
      });
      expect(mockAuth.setUser).toHaveBeenCalledWith(saved);
      expect(await screen.findByRole('dialog', { name: 'Profile' })).toBeInTheDocument();
    });

    test('sends the new and current password, and stores the fresh token', async () => {
      localStorage.setItem('token', 'old-token');
      updateUser.mockResolvedValue({ data: { ...USER, token: 'new-token' } });
      const { user } = renderProfile();

      const edit = await openEdit(user);
      await user.type(within(edit).getByLabelText('Current Password'), 'old-pass');
      await user.type(within(edit).getByLabelText('New Password'), 'n3w-pass');
      await user.type(within(edit).getByLabelText('Confirm Password'), 'n3w-pass');
      await user.click(within(edit).getByRole('button', { name: 'Save Changes' }));

      expect(updateUser).toHaveBeenCalledWith(
        1,
        expect.objectContaining({
          password: 'n3w-pass',
          current_password: 'old-pass',
        })
      );
      // The old token was revoked by the password change; keep this device
      // logged in with the new one, and keep the token out of the user object.
      expect(localStorage.getItem('token')).toBe('new-token');
      expect(mockAuth.setUser).toHaveBeenCalledWith(USER);
    });

    test('requires the current password before sending a new one', async () => {
      const { user } = renderProfile();

      const edit = await openEdit(user);
      await user.type(within(edit).getByLabelText('New Password'), 'n3w-pass');
      await user.type(within(edit).getByLabelText('Confirm Password'), 'n3w-pass');
      await user.click(within(edit).getByRole('button', { name: 'Save Changes' }));

      expect(within(edit).getByRole('alert')).toHaveTextContent(
        'Enter your current password to set a new one.'
      );
      expect(updateUser).not.toHaveBeenCalled();
    });

    test('shows the backend error when the current password is wrong', async () => {
      updateUser.mockRejectedValue({
        response: { status: 403, data: { error: 'Current password is incorrect.' } },
      });
      const { user } = renderProfile();

      const edit = await openEdit(user);
      await user.type(within(edit).getByLabelText('Current Password'), 'wrong');
      await user.type(within(edit).getByLabelText('New Password'), 'n3w-pass');
      await user.type(within(edit).getByLabelText('Confirm Password'), 'n3w-pass');
      await user.click(within(edit).getByRole('button', { name: 'Save Changes' }));

      expect(await within(edit).findByRole('alert')).toHaveTextContent(
        'Current password is incorrect.'
      );
      expect(mockAuth.logout).not.toHaveBeenCalled();
    });

    test('blocks saving when the passwords do not match', async () => {
      const { user } = renderProfile();

      const edit = await openEdit(user);
      await user.type(within(edit).getByLabelText('New Password'), 'one');
      await user.type(within(edit).getByLabelText('Confirm Password'), 'two');
      await user.click(within(edit).getByRole('button', { name: 'Save Changes' }));

      expect(within(edit).getByRole('alert')).toHaveTextContent('Passwords do not match.');
      expect(updateUser).not.toHaveBeenCalled();
    });

    test('shows the backend error when saving fails', async () => {
      updateUser.mockRejectedValue({
        response: { data: { error: 'Username already exists' } },
      });
      const { user } = renderProfile();

      const edit = await openEdit(user);
      await user.click(within(edit).getByRole('button', { name: 'Save Changes' }));

      expect(await within(edit).findByRole('alert')).toHaveTextContent(
        'Username already exists'
      );
      expect(mockAuth.setUser).not.toHaveBeenCalled();
    });

    test('Cancel returns to the profile view without saving', async () => {
      const { user } = renderProfile();

      const edit = await openEdit(user);
      await user.click(within(edit).getByRole('button', { name: 'Cancel' }));

      expect(screen.getByRole('dialog', { name: 'Profile' })).toBeInTheDocument();
      expect(updateUser).not.toHaveBeenCalled();
    });
  });

  describe('deleting the account', () => {
    test('is blocked with the backend message while balances remain', async () => {
      const { user } = renderProfile();

      await startDelete(
        user,
        canDeleteResponse({
          can_delete: false,
          message: 'Cannot delete user. Clear all balances first.',
        })
      );

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Cannot delete user. Clear all balances first.'
      );
      expect(screen.queryByText('Please review before continuing.')).not.toBeInTheDocument();
      expect(deleteUser).not.toHaveBeenCalled();
    });

    test('lists which balances block deletion when there is no message', async () => {
      const { user } = renderProfile();

      await startDelete(
        user,
        canDeleteResponse({
          can_delete: false,
          message: null,
          details: {
            has_bank_balances: true,
            has_asset_balances: false,
            has_saving_balances: false,
            has_credit_balances: true,
          },
        })
      );

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Please clear balances from bank accounts, credit cards and try again.'
      );
    });

    test('shows the transaction count and offers a backup with all categories selected', async () => {
      const { user } = renderProfile();

      await startDelete(user);

      expect(
        await screen.findByRole('heading', { name: 'Delete Account' })
      ).toBeInTheDocument();
      expect(
        screen.getByText(/transaction records in your account history/)
      ).toHaveTextContent('You have 42 transaction records');

      ['Banks', 'Savings', 'Assets', 'Credit Cards'].forEach(label => {
        expect(screen.getByRole('checkbox', { name: label })).toBeChecked();
      });
      expect(
        screen.getByRole('button', { name: 'Delete Without Backup' })
      ).toBeInTheDocument();
    });

    test('downloads a backup of only the selected categories', async () => {
      exportUserTransactionsExcel.mockResolvedValue({ data: new Blob(['xlsx']) });
      exportUserTransactionsPdf.mockResolvedValue({ data: new Blob(['pdf']) });
      // jsdom does not implement object URLs or file downloads.
      window.URL.createObjectURL = jest.fn(() => 'blob:backup');
      window.URL.revokeObjectURL = jest.fn();
      jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

      const { user } = renderProfile();
      await startDelete(user);
      await screen.findByRole('heading', { name: 'Delete Account' });

      await user.click(screen.getByRole('checkbox', { name: 'Assets' }));
      await user.click(screen.getByRole('button', { name: 'Download Excel' }));
      await screen.findByText('A backup has been downloaded to your device.');
      await user.click(screen.getByRole('button', { name: 'Download PDF' }));

      expect(exportUserTransactionsExcel).toHaveBeenCalledWith(1, [
        'banks',
        'savings',
        'credit_cards',
      ]);
      expect(exportUserTransactionsPdf).toHaveBeenCalledWith(1, [
        'banks',
        'savings',
        'credit_cards',
      ]);
      expect(
        await screen.findByRole('button', { name: 'Delete Account' })
      ).toBeInTheDocument();
      expect(deleteUser).not.toHaveBeenCalled();
    });

    test('download buttons are disabled when every category is cleared', async () => {
      const { user } = renderProfile();
      await startDelete(user);
      await screen.findByRole('heading', { name: 'Delete Account' });

      await user.click(screen.getByRole('button', { name: 'Clear' }));

      expect(screen.getByRole('button', { name: 'Download Excel' })).toBeDisabled();
      expect(screen.getByRole('button', { name: 'Download PDF' })).toBeDisabled();
    });

    test('a failed backup keeps the account and explains nothing was deleted', async () => {
      exportUserTransactionsExcel.mockRejectedValue(new Error('Network Error'));
      const { user } = renderProfile();
      await startDelete(user);
      await screen.findByRole('heading', { name: 'Delete Account' });

      await user.click(screen.getByRole('button', { name: 'Download Excel' }));

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Unable to download the Excel backup. Your transaction data has not been deleted.'
      );
      expect(deleteUser).not.toHaveBeenCalled();
    });

    test('confirming deletes the account, logs out and goes to the login page', async () => {
      deleteUser.mockResolvedValue({ data: { message: 'User deleted successfully' } });
      const { onClose, user } = renderProfile();
      await startDelete(user);
      await screen.findByRole('heading', { name: 'Delete Account' });

      await user.click(screen.getByRole('button', { name: 'Delete Without Backup' }));

      expect(deleteUser).toHaveBeenCalledWith(1);
      expect(mockAuth.logout).toHaveBeenCalledTimes(1);
      expect(onClose).toHaveBeenCalled();
      expect(
        await screen.findByRole('heading', { name: 'Login page' })
      ).toBeInTheDocument();
    });

    test('with no transaction history there is no backup step', async () => {
      deleteUser.mockResolvedValue({ data: {} });
      const { user } = renderProfile();

      await startDelete(
        user,
        canDeleteResponse({ has_transaction_history: false, transaction_count: 0 })
      );

      expect(await screen.findByText('No transaction history was found.')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Download Excel' })).not.toBeInTheDocument();

      await user.click(screen.getByRole('button', { name: 'Delete Account' }));
      expect(deleteUser).toHaveBeenCalledWith(1);
    });

    test('a failed delete shows the error and keeps the user logged in', async () => {
      deleteUser.mockRejectedValue({
        response: { data: { error: 'Server error: database unavailable' } },
      });
      const { user } = renderProfile();
      await startDelete(user);
      await screen.findByRole('heading', { name: 'Delete Account' });

      await user.click(screen.getByRole('button', { name: 'Delete Without Backup' }));

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Server error: database unavailable'
      );
      expect(mockAuth.logout).not.toHaveBeenCalled();
    });

    test('Cancel closes the confirmation without deleting', async () => {
      const { user } = renderProfile();
      await startDelete(user);
      await screen.findByRole('heading', { name: 'Delete Account' });

      await user.click(screen.getByRole('button', { name: 'Cancel' }));

      expect(screen.queryByText('Please review before continuing.')).not.toBeInTheDocument();
      expect(deleteUser).not.toHaveBeenCalled();
    });

    test('shows a fallback message when the deletion check fails', async () => {
      canDeleteUser.mockRejectedValue(new Error('Network Error'));
      const { user } = renderProfile();

      const edit = await openEdit(user);
      await user.click(within(edit).getByRole('button', { name: 'Delete Account' }));

      expect(await within(edit).findByRole('alert')).toHaveTextContent(
        'Unable to check whether your account can be deleted.'
      );
    });
  });
});
