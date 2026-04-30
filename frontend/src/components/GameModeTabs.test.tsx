import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import GameModeTabs from './GameModeTabs';
import type { GameMode } from '@/types';

const MOCK_MODES: GameMode[] = [
  {
    id: 'mode-30s',
    name: 'Win Go 30s',
    mode_type: 'classic',
    color_options: ['green', 'red', 'violet'],
    odds: { green: '2.0', red: '2.0', violet: '4.8', number: '9.6', big: '2.0', small: '2.0' },
    min_bet: '1',
    max_bet: '10000',
    round_duration_seconds: 30,
    is_active: true,
  },
  {
    id: 'mode-1min',
    name: 'Win Go 1Min',
    mode_type: 'classic',
    color_options: ['green', 'red', 'violet'],
    odds: { green: '2.0', red: '2.0', violet: '4.8', number: '9.6', big: '2.0', small: '2.0' },
    min_bet: '1',
    max_bet: '10000',
    round_duration_seconds: 60,
    is_active: true,
  },
  {
    id: 'mode-3min',
    name: 'Win Go 3Min',
    mode_type: 'classic',
    color_options: ['green', 'red', 'violet'],
    odds: { green: '2.0', red: '2.0', violet: '4.8', number: '9.6', big: '2.0', small: '2.0' },
    min_bet: '1',
    max_bet: '10000',
    round_duration_seconds: 180,
    is_active: true,
  },
  {
    id: 'mode-5min',
    name: 'Win Go 5Min',
    mode_type: 'classic',
    color_options: ['green', 'red', 'violet'],
    odds: { green: '2.0', red: '2.0', violet: '4.8', number: '9.6', big: '2.0', small: '2.0' },
    min_bet: '1',
    max_bet: '10000',
    round_duration_seconds: 300,
    is_active: true,
  },
];

describe('GameModeTabs', () => {
  it('renders all four game mode tabs', () => {
    render(
      <GameModeTabs modes={MOCK_MODES} activeMode="mode-30s" onModeChange={vi.fn()} />,
    );

    expect(screen.getByRole('tab', { name: 'Win Go 30s' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Win Go 1Min' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Win Go 3Min' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Win Go 5Min' })).toBeInTheDocument();
  });

  it('marks the active tab with aria-selected=true', () => {
    render(
      <GameModeTabs modes={MOCK_MODES} activeMode="mode-1min" onModeChange={vi.fn()} />,
    );

    expect(screen.getByRole('tab', { name: 'Win Go 1Min' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    expect(screen.getByRole('tab', { name: 'Win Go 30s' })).toHaveAttribute(
      'aria-selected',
      'false',
    );
    expect(screen.getByRole('tab', { name: 'Win Go 3Min' })).toHaveAttribute(
      'aria-selected',
      'false',
    );
  });

  it('applies active styling to the selected tab', () => {
    render(
      <GameModeTabs modes={MOCK_MODES} activeMode="mode-30s" onModeChange={vi.fn()} />,
    );

    const activeTab = screen.getByRole('tab', { name: 'Win Go 30s' });
    expect(activeTab.className).toContain('bg-casino-green');
    expect(activeTab.className).toContain('text-white');
  });

  it('applies inactive styling to non-selected tabs', () => {
    render(
      <GameModeTabs modes={MOCK_MODES} activeMode="mode-30s" onModeChange={vi.fn()} />,
    );

    const inactiveTab = screen.getByRole('tab', { name: 'Win Go 1Min' });
    expect(inactiveTab.className).toContain('bg-transparent');
    expect(inactiveTab.className).toContain('text-casino-text-muted');
  });

  it('calls onModeChange when an inactive tab is clicked', async () => {
    const user = userEvent.setup();
    const onModeChange = vi.fn();

    render(
      <GameModeTabs modes={MOCK_MODES} activeMode="mode-30s" onModeChange={onModeChange} />,
    );

    await user.click(screen.getByRole('tab', { name: 'Win Go 3Min' }));
    expect(onModeChange).toHaveBeenCalledWith('mode-3min');
    expect(onModeChange).toHaveBeenCalledTimes(1);
  });

  it('does not call onModeChange when the active tab is clicked', async () => {
    const user = userEvent.setup();
    const onModeChange = vi.fn();

    render(
      <GameModeTabs modes={MOCK_MODES} activeMode="mode-30s" onModeChange={onModeChange} />,
    );

    await user.click(screen.getByRole('tab', { name: 'Win Go 30s' }));
    expect(onModeChange).not.toHaveBeenCalled();
  });

  it('renders a tablist with proper ARIA label', () => {
    render(
      <GameModeTabs modes={MOCK_MODES} activeMode="mode-30s" onModeChange={vi.fn()} />,
    );

    expect(screen.getByRole('tablist', { name: 'Game modes' })).toBeInTheDocument();
  });

  it('renders with an empty modes array without crashing', () => {
    render(
      <GameModeTabs modes={[]} activeMode="" onModeChange={vi.fn()} />,
    );

    expect(screen.getByRole('tablist', { name: 'Game modes' })).toBeInTheDocument();
    expect(screen.queryAllByRole('tab')).toHaveLength(0);
  });
});
