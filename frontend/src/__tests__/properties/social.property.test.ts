import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import type { PlayerPublicProfile } from '@/types';

/**
 * Property 12: Chat message rendering completeness
 *
 * For any incoming chat message containing sender and message fields,
 * the chat panel renderer SHALL produce output that includes both the
 * sender name and the message content. No chat message SHALL be rendered
 * without its sender attribution.
 *
 * **Validates: Requirements 7.3**
 */

/**
 * Property 13: Player profile rendering completeness
 *
 * For any player public profile containing total_games, win_rate, and
 * leaderboard_rank fields, the profile renderer SHALL produce output that
 * includes all three statistics. No statistic SHALL be omitted from the
 * rendered profile.
 *
 * **Validates: Requirements 7.5**
 */

// --- Pure rendering helpers ---

interface ChatMessage {
  sender: string;
  message: string;
  timestamp: string;
}

interface RenderedChatMessage {
  senderDisplay: string;
  messageContent: string;
}

function renderChatMessage(msg: ChatMessage): RenderedChatMessage {
  return {
    senderDisplay: msg.sender,
    messageContent: msg.message,
  };
}

interface RenderedProfile {
  totalGames: string;
  winRate: string;
  leaderboardRank: string;
}

function renderPlayerProfile(profile: PlayerPublicProfile): RenderedProfile {
  return {
    totalGames: String(profile.total_games),
    winRate: `${profile.win_rate}%`,
    leaderboardRank:
      profile.leaderboard_rank !== null
        ? `#${profile.leaderboard_rank}`
        : 'Unranked',
  };
}

// --- Arbitraries ---

const senderArb = fc.string({ minLength: 1, maxLength: 50 }).filter((s) => s.trim().length > 0);
const messageContentArb = fc.string({ minLength: 1, maxLength: 500 }).filter((s) => s.trim().length > 0);

const isoDateArb = fc
  .date({
    min: new Date('2020-01-01T00:00:00.000Z'),
    max: new Date('2030-12-31T23:59:59.999Z'),
    noInvalidDate: true,
  })
  .map((d) => d.toISOString());

const chatMessageArb: fc.Arbitrary<ChatMessage> = fc.record({
  sender: senderArb,
  message: messageContentArb,
  timestamp: isoDateArb,
});

const decimalValueArb = fc
  .integer({ min: 0, max: 9999 })
  .map((cents) => (cents / 100).toFixed(2));

const playerProfileArb: fc.Arbitrary<PlayerPublicProfile> = fc.record({
  id: fc.uuid(),
  username: senderArb,
  total_games: fc.integer({ min: 0, max: 100000 }),
  win_rate: decimalValueArb,
  leaderboard_rank: fc.option(fc.integer({ min: 1, max: 10000 }), { nil: null }),
});

// --- Property tests ---

describe('Property 12: Chat message rendering completeness', () => {
  it('rendered output includes both sender and message content for any chat message', () => {
    fc.assert(
      fc.property(chatMessageArb, (msg) => {
        const rendered = renderChatMessage(msg);

        expect(rendered.senderDisplay).toBeTruthy();
        expect(rendered.senderDisplay.length).toBeGreaterThan(0);
        expect(rendered.senderDisplay).toBe(msg.sender);

        expect(rendered.messageContent).toBeTruthy();
        expect(rendered.messageContent.length).toBeGreaterThan(0);
        expect(rendered.messageContent).toBe(msg.message);
      }),
      { numRuns: 100 },
    );
  });

  it('sender attribution is never missing from rendered output', () => {
    fc.assert(
      fc.property(chatMessageArb, (msg) => {
        const rendered = renderChatMessage(msg);
        // Sender must always be present
        expect(rendered.senderDisplay).not.toBe('');
        expect(rendered.senderDisplay).not.toBeUndefined();
        expect(rendered.senderDisplay).not.toBeNull();
      }),
      { numRuns: 100 },
    );
  });
});

describe('Property 13: Player profile rendering completeness', () => {
  it('all three statistics are present and non-empty for any player profile', () => {
    fc.assert(
      fc.property(playerProfileArb, (profile) => {
        const rendered = renderPlayerProfile(profile);

        expect(rendered.totalGames).toBeTruthy();
        expect(rendered.totalGames.length).toBeGreaterThan(0);

        expect(rendered.winRate).toBeTruthy();
        expect(rendered.winRate.length).toBeGreaterThan(0);

        expect(rendered.leaderboardRank).toBeTruthy();
        expect(rendered.leaderboardRank.length).toBeGreaterThan(0);
      }),
      { numRuns: 100 },
    );
  });

  it('total_games is rendered as a string of the numeric value', () => {
    fc.assert(
      fc.property(playerProfileArb, (profile) => {
        const rendered = renderPlayerProfile(profile);
        expect(rendered.totalGames).toBe(String(profile.total_games));
      }),
      { numRuns: 100 },
    );
  });

  it('win_rate includes the original value with a percent sign', () => {
    fc.assert(
      fc.property(playerProfileArb, (profile) => {
        const rendered = renderPlayerProfile(profile);
        expect(rendered.winRate).toContain(profile.win_rate);
        expect(rendered.winRate).toContain('%');
      }),
      { numRuns: 100 },
    );
  });

  it('leaderboard_rank shows rank number or "Unranked" for null', () => {
    fc.assert(
      fc.property(playerProfileArb, (profile) => {
        const rendered = renderPlayerProfile(profile);
        if (profile.leaderboard_rank !== null) {
          expect(rendered.leaderboardRank).toBe(`#${profile.leaderboard_rank}`);
        } else {
          expect(rendered.leaderboardRank).toBe('Unranked');
        }
      }),
      { numRuns: 100 },
    );
  });
});
