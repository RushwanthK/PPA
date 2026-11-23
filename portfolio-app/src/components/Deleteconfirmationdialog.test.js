import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import DeleteConfirmationDialog from './Deleteconfirmationdialog';

const CATEGORIES = [
  { key: 'banks', label: 'Banks' },
  { key: 'savings', label: 'Savings' },
];

describe('DeleteConfirmationDialog', () => {
  test('renders nothing when closed', () => {
    const { container } = render(
      <DeleteConfirmationDialog isOpen={false} onConfirm={jest.fn()} onClose={jest.fn()} />
    );

    expect(container).toBeEmptyDOMElement();
  });

  test('shows the warning text and calls confirm / cancel', async () => {
    const onConfirm = jest.fn();
    const onClose = jest.fn();
    const user = userEvent.setup();

    render(
      <DeleteConfirmationDialog
        isOpen
        title="Delete Bank Account"
        headline='Delete "HDFC"?'
        description="Current balance: Rs. 0.00"
        detailLines={['This action cannot be undone.']}
        confirmLabel="Delete Bank"
        onConfirm={onConfirm}
        onClose={onClose}
      />
    );

    expect(screen.getByRole('heading', { name: 'Delete Bank Account' })).toBeInTheDocument();
    expect(screen.getByText('Delete "HDFC"?')).toBeInTheDocument();
    expect(screen.getByText('This action cannot be undone.')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Delete Bank' }));
    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test('disables both actions and shows the deleting label while deleting', () => {
    render(
      <DeleteConfirmationDialog
        isOpen
        isDeleting
        onConfirm={jest.fn()}
        onClose={jest.fn()}
      />
    );

    expect(screen.getByRole('button', { name: 'Deleting...' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled();
  });

  test('uses the "without backup" label until a backup is downloaded', () => {
    const props = {
      isOpen: true,
      onConfirm: jest.fn(),
      onClose: jest.fn(),
      showBackupSection: true,
      onDownloadExcel: jest.fn(),
      confirmLabel: 'Delete Bank',
      confirmWithoutBackupLabel: 'Delete Without Backup',
    };

    const { rerender } = render(<DeleteConfirmationDialog {...props} />);
    expect(screen.getByRole('button', { name: 'Delete Without Backup' })).toBeInTheDocument();

    rerender(
      <DeleteConfirmationDialog
        {...props}
        backupDownloaded
        backupConfirmedMessage="Backup downloaded."
      />
    );
    expect(screen.getByRole('button', { name: 'Delete Bank' })).toBeInTheDocument();
    expect(screen.getByText('Backup downloaded.')).toBeInTheDocument();
  });

  test('download buttons are disabled when no backup category is selected', async () => {
    const onDownloadExcel = jest.fn();
    const onDownloadPdf = jest.fn();
    const user = userEvent.setup();

    const props = {
      isOpen: true,
      onConfirm: jest.fn(),
      onClose: jest.fn(),
      showBackupSection: true,
      categories: CATEGORIES,
      onDownloadExcel,
      onDownloadPdf,
      onToggleCategory: jest.fn(),
    };

    const { rerender } = render(
      <DeleteConfirmationDialog {...props} selectedCategories={{}} />
    );

    expect(screen.getByRole('button', { name: 'Download Excel' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Download PDF' })).toBeDisabled();
    expect(
      screen.getByText('Select at least one category to enable download.')
    ).toBeInTheDocument();

    rerender(
      <DeleteConfirmationDialog {...props} selectedCategories={{ banks: true }} />
    );

    await user.click(screen.getByRole('button', { name: 'Download Excel' }));
    await user.click(screen.getByRole('button', { name: 'Download PDF' }));
    expect(onDownloadExcel).toHaveBeenCalledTimes(1);
    expect(onDownloadPdf).toHaveBeenCalledTimes(1);
  });

  test('category checkboxes and shortcuts call their handlers', async () => {
    const onToggleCategory = jest.fn();
    const onSelectAllCategories = jest.fn();
    const onClearAllCategories = jest.fn();
    const user = userEvent.setup();

    render(
      <DeleteConfirmationDialog
        isOpen
        onConfirm={jest.fn()}
        onClose={jest.fn()}
        showBackupSection
        categories={CATEGORIES}
        selectedCategories={{ banks: true }}
        onToggleCategory={onToggleCategory}
        onSelectAllCategories={onSelectAllCategories}
        onClearAllCategories={onClearAllCategories}
      />
    );

    expect(screen.getByRole('checkbox', { name: 'Banks' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Savings' })).not.toBeChecked();

    await user.click(screen.getByRole('checkbox', { name: 'Savings' }));
    await user.click(screen.getByRole('button', { name: 'Select all' }));
    await user.click(screen.getByRole('button', { name: 'Clear' }));

    expect(onToggleCategory).toHaveBeenCalledWith('savings');
    expect(onSelectAllCategories).toHaveBeenCalledTimes(1);
    expect(onClearAllCategories).toHaveBeenCalledTimes(1);
  });

  test('shows a dismissible dialog error', async () => {
    const onDismissDialogError = jest.fn();
    const user = userEvent.setup();

    render(
      <DeleteConfirmationDialog
        isOpen
        onConfirm={jest.fn()}
        onClose={jest.fn()}
        dialogError="Cannot delete bank"
        onDismissDialogError={onDismissDialogError}
      />
    );

    expect(screen.getByRole('alert')).toHaveTextContent('Cannot delete bank');
    await user.click(screen.getByRole('button', { name: 'Dismiss error' }));
    expect(onDismissDialogError).toHaveBeenCalledTimes(1);
  });
});
