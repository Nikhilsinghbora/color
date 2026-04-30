import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import BigSmallButtons from './BigSmallButtons';

describe('BigSmallButtons', () => {
  it('renders Big and Small buttons with labels, ranges, and multipliers', () => {
    render(<BigSmallButtons onSelectBigSmall={vi.fn()} disabled={false} />);

    expect(screen.getByText('Big 5-9')).toBeInTheDocument();
    expect(screen.getByText('Small 0-4')).toBeInTheDocument();
    // Both buttons show x2.0 multiplier
    const multipliers = screen.getAllByText('x2.0');
    expect(multipliers).toHaveLength(2);
  });

  it('calls onSelectBigSmall with "big" when Big button is clicked', async () => {
    const user = userEvent.setup();
    const onSelectBigSmall = vi.fn();

    render(<BigSmallButtons onSelectBigSmall={onSelectBigSmall} disabled={false} />);

    await user.click(screen.getByRole('button', { name: /bet on big/i }));
    expect(onSelectBigSmall).toHaveBeenCalledWith('big');
    expect(onSelectBigSmall).toHaveBeenCalledTimes(1);
  });

  it('calls onSelectBigSmall with "small" when Small button is clicked', async () => {
    const user = userEvent.setup();
    const onSelectBigSmall = vi.fn();

    render(<BigSmallButtons onSelectBigSmall={onSelectBigSmall} disabled={false} />);

    await user.click(screen.getByRole('button', { name: /bet on small/i }));
    expect(onSelectBigSmall).toHaveBeenCalledWith('small');
    expect(onSelectBigSmall).toHaveBeenCalledTimes(1);
  });

  it('disables buttons when disabled prop is true', () => {
    render(<BigSmallButtons onSelectBigSmall={vi.fn()} disabled={true} />);

    const bigButton = screen.getByRole('button', { name: /bet on big/i });
    const smallButton = screen.getByRole('button', { name: /bet on small/i });

    expect(bigButton).toBeDisabled();
    expect(smallButton).toBeDisabled();
  });

  it('does not call onSelectBigSmall when disabled buttons are clicked', async () => {
    const user = userEvent.setup();
    const onSelectBigSmall = vi.fn();

    render(<BigSmallButtons onSelectBigSmall={onSelectBigSmall} disabled={true} />);

    await user.click(screen.getByRole('button', { name: /bet on big/i }));
    await user.click(screen.getByRole('button', { name: /bet on small/i }));
    expect(onSelectBigSmall).not.toHaveBeenCalled();
  });

  it('shows checkmark badge when bet is placed on big', () => {
    render(
      <BigSmallButtons
        onSelectBigSmall={vi.fn()}
        disabled={false}
        placedBigSmall={new Set(['big'])}
      />,
    );

    expect(screen.getByLabelText('Bet placed on Big')).toBeInTheDocument();
    expect(screen.queryByLabelText('Bet placed on Small')).not.toBeInTheDocument();
  });

  it('shows checkmark badge when bet is placed on small', () => {
    render(
      <BigSmallButtons
        onSelectBigSmall={vi.fn()}
        disabled={false}
        placedBigSmall={new Set(['small'])}
      />,
    );

    expect(screen.getByLabelText('Bet placed on Small')).toBeInTheDocument();
    expect(screen.queryByLabelText('Bet placed on Big')).not.toBeInTheDocument();
  });

  it('shows checkmark badges on both buttons when bets placed on both', () => {
    render(
      <BigSmallButtons
        onSelectBigSmall={vi.fn()}
        disabled={false}
        placedBigSmall={new Set(['big', 'small'])}
      />,
    );

    expect(screen.getByLabelText('Bet placed on Big')).toBeInTheDocument();
    expect(screen.getByLabelText('Bet placed on Small')).toBeInTheDocument();
  });

  it('shows no checkmark badges when no bets are placed', () => {
    render(<BigSmallButtons onSelectBigSmall={vi.fn()} disabled={false} />);

    expect(screen.queryByLabelText('Bet placed on Big')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Bet placed on Small')).not.toBeInTheDocument();
  });

  it('has proper ARIA label on the section', () => {
    render(<BigSmallButtons onSelectBigSmall={vi.fn()} disabled={false} />);

    expect(
      screen.getByRole('region', { name: 'Big/Small betting buttons' }),
    ).toBeInTheDocument();
  });

  it('buttons have proper ARIA labels with odds info', () => {
    render(<BigSmallButtons onSelectBigSmall={vi.fn()} disabled={false} />);

    expect(
      screen.getByRole('button', { name: 'Bet on Big 5-9 at x2.0 odds' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Bet on Small 0-4 at x2.0 odds' }),
    ).toBeInTheDocument();
  });
});
