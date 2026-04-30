'use client';

import { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth-store';
import { useWalletStore } from '@/stores/wallet-store';

const NAV_LINKS = [
  { href: '/game', label: 'Game' },
  { href: '/wallet', label: 'Wallet' },
  { href: '/leaderboard', label: 'Leaderboard' },
  { href: '/social', label: 'Social' },
  { href: '/settings', label: 'Settings' },
] as const;

export function NavBar() {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, player, clearTokens } = useAuthStore();
  const balance = useWalletStore((s) => s.balance);
  const [menuOpen, setMenuOpen] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  if (!isAuthenticated) return null;

  const handleLogout = () => {
    clearTokens();
    setMenuOpen(false);
    router.push('/login');
  };

  return (
    <nav
      className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60"
      aria-label="Main navigation"
    >
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
        {/* Logo / Brand */}
        <Link href="/game" className="text-lg font-semibold text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded">
          ColorPredict
        </Link>

        {/* Desktop nav links */}
        <ul className="hidden md:flex items-center gap-1" role="menubar">
          {NAV_LINKS.map(({ href, label }) => (
            <li key={href} role="none">
              <Link
                href={href}
                role="menuitem"
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                  pathname?.startsWith(href)
                    ? 'bg-accent text-accent-foreground'
                    : 'text-muted-foreground hover:text-foreground hover:bg-secondary'
                }`}
              >
                {label}
              </Link>
            </li>
          ))}
        </ul>

        {/* Right side: balance + account dropdown */}
        <div className="flex items-center gap-3">
          {balance !== null && (
            <span className="hidden sm:inline text-sm font-medium text-foreground" aria-label={`Wallet balance: ${balance}`}>
              ${balance}
            </span>
          )}

          {/* Account dropdown */}
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setMenuOpen((o) => !o)}
              onKeyDown={(e) => { if (e.key === 'Escape') setMenuOpen(false); }}
              className="flex items-center gap-1 rounded-md px-2 py-1.5 text-sm font-medium text-foreground hover:bg-secondary focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-haspopup="true"
              aria-expanded={menuOpen}
              aria-label="Account menu"
            >
              {player?.username ?? 'Account'}
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {menuOpen && (
              <div
                className="absolute right-0 mt-1 w-48 rounded-md border border-border bg-card shadow-lg py-1 z-50"
                role="menu"
                aria-label="Account options"
              >
                <Link
                  href="/settings"
                  role="menuitem"
                  className="block px-4 py-2 text-sm text-card-foreground hover:bg-secondary focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  onClick={() => setMenuOpen(false)}
                >
                  Profile Settings
                </Link>
                <Link
                  href="/settings/responsible-gambling"
                  role="menuitem"
                  className="block px-4 py-2 text-sm text-card-foreground hover:bg-secondary focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  onClick={() => setMenuOpen(false)}
                >
                  Responsible Gambling
                </Link>
                <button
                  role="menuitem"
                  onClick={handleLogout}
                  className="block w-full text-left px-4 py-2 text-sm text-destructive hover:bg-secondary focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  Logout
                </button>
              </div>
            )}
          </div>

          {/* Mobile hamburger */}
          <button
            className="md:hidden rounded-md p-1.5 text-foreground hover:bg-secondary focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onClick={() => setMobileNavOpen((o) => !o)}
            aria-label="Toggle mobile navigation"
            aria-expanded={mobileNavOpen}
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              {mobileNavOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>
      </div>

      {/* Mobile nav */}
      {mobileNavOpen && (
        <ul className="md:hidden border-t border-border px-4 py-2 space-y-1" role="menu">
          {NAV_LINKS.map(({ href, label }) => (
            <li key={href} role="none">
              <Link
                href={href}
                role="menuitem"
                className={`block px-3 py-2 rounded-md text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                  pathname?.startsWith(href)
                    ? 'bg-accent text-accent-foreground'
                    : 'text-muted-foreground hover:text-foreground hover:bg-secondary'
                }`}
                onClick={() => setMobileNavOpen(false)}
              >
                {label}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </nav>
  );
}
