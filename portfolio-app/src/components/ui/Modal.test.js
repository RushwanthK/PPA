import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import Modal from './Modal';

describe('Modal', () => {
  test('renders nothing when closed', () => {
    render(<Modal open={false} title="Hidden">content</Modal>);

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  test('renders an accessible dialog with title and content when open', () => {
    render(<Modal open title="My Dialog">Hello</Modal>);

    const dialog = screen.getByRole('dialog', { name: 'My Dialog' });
    expect(dialog).toHaveTextContent('Hello');
    expect(dialog).toHaveFocus();
  });

  test('closes via the close button and the Escape key', async () => {
    const onClose = jest.fn();
    const user = userEvent.setup();

    render(<Modal open title="My Dialog" onClose={onClose}>Hello</Modal>);

    await user.click(screen.getByRole('button', { name: 'Close dialog' }));
    await user.keyboard('{Escape}');

    expect(onClose).toHaveBeenCalledTimes(2);
  });

  test('closes on overlay click but not on clicks inside the dialog', () => {
    const onClose = jest.fn();

    render(<Modal open title="My Dialog" onClose={onClose}>Hello</Modal>);

    fireEvent.mouseDown(screen.getByRole('dialog'));
    expect(onClose).not.toHaveBeenCalled();

    fireEvent.mouseDown(screen.getByRole('presentation'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test('respects closeOnOverlayClick and closeOnEscape being disabled', async () => {
    const onClose = jest.fn();
    const user = userEvent.setup();

    render(
      <Modal
        open
        title="Locked"
        onClose={onClose}
        closeOnOverlayClick={false}
        closeOnEscape={false}
      >
        Busy
      </Modal>
    );

    fireEvent.mouseDown(screen.getByRole('presentation'));
    await user.keyboard('{Escape}');

    expect(onClose).not.toHaveBeenCalled();
  });

  test('two open modals each keep their own accessible title', () => {
    render(
      <>
        <Modal open title="First">One</Modal>
        <Modal open title="Second">Two</Modal>
      </>
    );

    expect(screen.getByRole('dialog', { name: 'First' })).toHaveTextContent('One');
    expect(screen.getByRole('dialog', { name: 'Second' })).toHaveTextContent('Two');
  });
});
