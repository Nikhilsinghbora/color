'use client';

/** Default announcement text shown when no custom text is provided. */
const DEFAULT_ANNOUNCEMENT =
  'Welcome to WinGo! Enjoy exciting color prediction games with multiple modes. Play responsibly.';

interface AnnouncementBarProps {
  /** The announcement text to scroll across the bar. */
  text?: string;
  /** Callback fired when the "Detail" button is clicked. */
  onDetailClick?: () => void;
}

export default function AnnouncementBar({
  text = DEFAULT_ANNOUNCEMENT,
  onDetailClick,
}: AnnouncementBarProps) {
  return (
    <section aria-label="Announcements" className="mx-4 mt-2">
      <div className="casino-card flex items-center gap-2 px-3 py-2 overflow-hidden">
        {/* Speaker icon */}
        <span className="shrink-0 text-lg" aria-hidden="true">
          📢
        </span>

        {/* Scrolling marquee text */}
        <div
          className="flex-1 overflow-hidden"
          role="marquee"
          aria-live="off"
          aria-label={text}
        >
          <p className="announcement-marquee whitespace-nowrap text-xs text-casino-text-secondary">
            {text}
          </p>
        </div>

        {/* Detail button */}
        <button
          type="button"
          onClick={onDetailClick}
          className="casino-transition shrink-0 rounded-md bg-casino-card px-2.5 py-1 text-[10px] font-semibold text-casino-text-secondary border border-casino-card-border"
          aria-label="View announcement details"
        >
          Detail
        </button>
      </div>
    </section>
  );
}
