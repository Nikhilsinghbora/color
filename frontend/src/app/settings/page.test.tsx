import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SettingsPage from './page';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn() }),
}));

// Mock auth guard
vi.mock('@/hooks/useAuthGuard', () => ({
  useAuthGuard: vi.fn(),
}));

// Track theme state
let currentTheme = 'light';
const mockSetTheme = vi.fn((t: string) => { currentTheme = t; });

vi.mock('@/stores/ui-store', () => ({
  useUIStore: (selector: (s: { theme: string; setTheme: typeof mockSetTheme }) => unknown) =>
    selector({ theme: currentTheme, setTheme: mockSetTheme }),
}));

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    currentTheme = 'light';
  });

  it('renders the settings heading', () => {
    render(<SettingsPage />);
    expect(screen.getByRole('heading', { name: 'Settings' })).toBeInTheDocument();
  });

  it('renders the theme toggle switch', () => {
    render(<SettingsPage />);
    const toggle = screen.getByRole('switch', { name: 'Dark mode' });
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveAttribute('aria-checked', 'false');
  });

  it('calls setTheme to dark when toggled from light', async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);
    await user.click(screen.getByRole('switch', { name: 'Dark mode' }));
    expect(mockSetTheme).toHaveBeenCalledWith('dark');
  });

  it('calls setTheme to light when toggled from dark', async () => {
    currentTheme = 'dark';
    const user = userEvent.setup();
    render(<SettingsPage />);
    const toggle = screen.getByRole('switch', { name: 'Dark mode' });
    expect(toggle).toHaveAttribute('aria-checked', 'true');
    await user.click(toggle);
    expect(mockSetTheme).toHaveBeenCalledWith('light');
  });
});
