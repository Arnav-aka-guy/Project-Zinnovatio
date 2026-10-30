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
  delivery_failed: 'Message failed',
  driver_job_added: 'New job',
  driver_job_removed: 'Job removed',
  driver_day_plan: 'Morning job list',
};

const REASON_WORDS: Record<string, string> = {
  simulate_mode: 'demo mode, not sent',
  demo_data: 'demo data, not sent',
  no_provider: 'no SMS/WhatsApp service set up',
  out_of_date: 'no longer true, not sent',
  not_a_test_number: 'not a test number, not sent',
  no_consent: 'farmer did not agree to messages',
  notifications_off: 'messages turned off',
  no_devices: 'no device has alerts on',
  quiet_hours: 'waiting for morning (quiet hours)',
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
  if (item.channel === 'sms') return 'SMS';
  if (item.channel === 'whatsapp') return 'WhatsApp';
  if (item.channel === 'webpush') return 'Phone alert';
  return item.channel;
}

export function shortTime(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleString(undefined, { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });
}
