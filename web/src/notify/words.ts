/** Plain words for notification kinds and delivery states. */
import type { OutboxItem } from '../types';

export const KIND_WORDS: Record<string, string> = {
  slot_scheduled: 'Turn booked',
  slot_changed: 'Turn changed',
  will_miss: 'Will miss',
  cancelled: 'Booking cancelled',
  job_started: 'Work started',
  job_done: 'Work done',
  not_served: 'Not served',
  needs_review: 'Needs review',
  machine_inactive: 'Machine off',
  login_locked: 'Account locked',
  farmer_unreachable: 'Farmer not reachable',
  driver_job_added: 'New job',
  driver_job_removed: 'Job removed',
  driver_day_plan: 'Morning job list',
};

const REASON_WORDS: Record<string, string> = {
  out_of_date: 'no longer true, not sent',
  no_consent: 'farmer did not agree to messages',
  no_devices: 'no phone has Vaari alerts on yet',
  quiet_hours: 'phone alert waits for morning (quiet hours)',
  retry_by_operator: 'sending again',
  device_unsubscribed: 'device turned alerts off',
  internal_error: 'server problem',
};

export const STATUS_WORDS: Record<string, string> = {
  queued: 'Waiting',
  sending: 'Sending',
  sent: 'Sent',
  delivered: 'Delivered',
  simulated: 'Simulated',
  skipped: 'Not sent',
  failed: 'Failed',
};

export function reasonWords(reason: string | null): string {
  if (!reason) return '';
  return REASON_WORDS[reason] ?? reason;
}

export function channelWords(item: Pick<OutboxItem, 'channel' | 'provider'>): string {
  if (item.channel === 'webpush') return 'Vaari phone alert';
  if (item.channel === 'inapp') return 'Vaari page';
  return item.channel;
}

export function shortTime(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleString(undefined, { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });
}
