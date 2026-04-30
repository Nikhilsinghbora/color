import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AnnouncementBar from './AnnouncementBar';

describe('AnnouncementBar', () => {
  it('renders speaker icon', () => {
    render(<AnnouncementBar />);
    expect(screen.getByText('📢')).toBeInTheDocument();
  });

  it('renders default announcement text when no text prop is provided', () => {
    render(<AnnouncementBar />);
    expect(
      screen.getByText(/Welcome to WinGo/),
    ).toBeInTheDocument();
  });

  it('renders custom announcement text', () => {
    render(<AnnouncementBar text="Big bonus event today!" />);
    expect(screen.getByText('Big bonus event today!')).toBeInTheDocument();
  });

  it('renders the Detail button', () => {
    render(<AnnouncementBar />);
    expect(
      screen.getByRole('button', { name: /view announcement details/i }),
    ).toBeInTheDocument();
    expect(screen.getByText('Detail')).toBeInTheDocument();
  });

  it('calls onDetailClick when Detail button is clicked', async () => {
    const handleClick = vi.fn();
    const user = userEvent.setup();
    render(<AnnouncementBar onDetailClick={handleClick} />);
    await user.click(screen.getByRole('button', { name: /view announcement details/i }));
    expect(handleClick).toHaveBeenCalledOnce();
  });

  it('does not throw when Detail is clicked without onDetailClick', async () => {
    const user = userEvent.setup();
    render(<AnnouncementBar />);
    // Should not throw
    await user.click(screen.getByRole('button', { name: /view announcement details/i }));
  });

  it('has proper ARIA label on the section', () => {
    render(<AnnouncementBar />);
    expect(screen.getByRole('region', { name: 'Announcements' })).toBeInTheDocument();
  });

  it('applies marquee animation class to the text', () => {
    render(<AnnouncementBar text="Scrolling text" />);
    const textEl = screen.getByText('Scrolling text');
    expect(textEl).toHaveClass('announcement-marquee');
  });

  it('has a marquee role element with aria-label matching the text', () => {
    const text = 'Important announcement';
    render(<AnnouncementBar text={text} />);
    const marquee = screen.getByRole('marquee');
    expect(marquee).toHaveAttribute('aria-label', text);
  });
});
