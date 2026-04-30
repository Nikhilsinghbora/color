import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import SoundToggle from './SoundToggle';

// Mock the soundManager singleton
vi.mock('@/lib/sound-manager', () => {
  const mockManager = {
    getIsMuted: vi.fn(() => false),
    setMuted: vi.fn(),
    initialize: vi.fn(),
  };
  return { soundManager: mockManager };
});

import { soundManager } from '@/lib/sound-manager';

const mockedSoundManager = soundManager as unknown as {
  getIsMuted: ReturnType<typeof vi.fn>;
  setMuted: ReturnType<typeof vi.fn>;
  initialize: ReturnType<typeof vi.fn>;
};

describe('SoundToggle', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedSoundManager.getIsMuted.mockReturnValue(false);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the unmuted icon when not muted', () => {
    render(<SoundToggle />);
    const btn = screen.getByTestId('sound-toggle');
    expect(btn).toHaveTextContent('🔊');
  });

  it('renders the muted icon when muted', () => {
    mockedSoundManager.getIsMuted.mockReturnValue(true);
    render(<SoundToggle />);
    const btn = screen.getByTestId('sound-toggle');
    expect(btn).toHaveTextContent('🔇');
  });

  it('has correct aria-label when unmuted', () => {
    render(<SoundToggle />);
    expect(screen.getByRole('button', { name: /mute sounds/i })).toBeInTheDocument();
  });

  it('has correct aria-label when muted', () => {
    mockedSoundManager.getIsMuted.mockReturnValue(true);
    render(<SoundToggle />);
    expect(screen.getByRole('button', { name: /unmute sounds/i })).toBeInTheDocument();
  });

  it('toggles from unmuted to muted on click', () => {
    render(<SoundToggle />);
    const btn = screen.getByTestId('sound-toggle');

    fireEvent.click(btn);

    expect(mockedSoundManager.setMuted).toHaveBeenCalledWith(true);
    expect(btn).toHaveTextContent('🔇');
  });

  it('toggles from muted to unmuted on click', () => {
    mockedSoundManager.getIsMuted.mockReturnValue(true);
    render(<SoundToggle />);
    const btn = screen.getByTestId('sound-toggle');

    fireEvent.click(btn);

    expect(mockedSoundManager.setMuted).toHaveBeenCalledWith(false);
    expect(btn).toHaveTextContent('🔊');
  });

  it('calls soundManager.initialize() on click for autoplay compliance', () => {
    render(<SoundToggle />);
    fireEvent.click(screen.getByTestId('sound-toggle'));

    expect(mockedSoundManager.initialize).toHaveBeenCalled();
  });

  it('renders as a button element', () => {
    render(<SoundToggle />);
    const btn = screen.getByTestId('sound-toggle');
    expect(btn.tagName).toBe('BUTTON');
    expect(btn).toHaveAttribute('type', 'button');
  });
});
