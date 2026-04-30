import { describe, it, expect, vi } from 'vitest';
import { render, screen, act, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ToastProvider, useToast } from './Toast';

function TestTrigger() {
  const { addToast } = useToast();
  return (
    <div>
      <button onClick={() => addToast('success', 'Success message')}>Add Success</button>
      <button onClick={() => addToast('error', 'Error message')}>Add Error</button>
      <button onClick={() => addToast('warning', 'Warning message')}>Add Warning</button>
      <button onClick={() => addToast('info', 'Info message')}>Add Info</button>
      <button onClick={() => addToast('success', 'Short toast', 100)}>Add Short</button>
    </div>
  );
}

describe('Toast', () => {
  it('renders a success toast', async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <TestTrigger />
      </ToastProvider>,
    );
    await user.click(screen.getByText('Add Success'));
    expect(screen.getByText('Success message')).toBeInTheDocument();
  });

  it('renders different toast types', async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <TestTrigger />
      </ToastProvider>,
    );
    await user.click(screen.getByText('Add Error'));
    expect(screen.getByText('Error message')).toBeInTheDocument();

    await user.click(screen.getByText('Add Warning'));
    expect(screen.getByText('Warning message')).toBeInTheDocument();

    await user.click(screen.getByText('Add Info'));
    expect(screen.getByText('Info message')).toBeInTheDocument();
  });

  it('auto-dismisses after duration', async () => {
    vi.useFakeTimers();
    // Render with a direct addToast call to avoid userEvent + fakeTimers conflict
    let triggerToast: (() => void) | undefined;
    function DirectTrigger() {
      const { addToast } = useToast();
      triggerToast = () => addToast('success', 'Short toast', 100);
      return null;
    }

    render(
      <ToastProvider>
        <DirectTrigger />
      </ToastProvider>,
    );

    act(() => { triggerToast!(); });
    expect(screen.getByText('Short toast')).toBeInTheDocument();

    act(() => { vi.advanceTimersByTime(150); });
    expect(screen.queryByText('Short toast')).not.toBeInTheDocument();

    vi.useRealTimers();
  });

  it('dismisses on close button click', async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <TestTrigger />
      </ToastProvider>,
    );
    await user.click(screen.getByText('Add Success'));
    expect(screen.getByText('Success message')).toBeInTheDocument();

    await user.click(screen.getByLabelText('Dismiss notification'));
    expect(screen.queryByText('Success message')).not.toBeInTheDocument();
  });

  it('has role=alert on toast items', async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <TestTrigger />
      </ToastProvider>,
    );
    await user.click(screen.getByText('Add Success'));
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });
});
