/** Types for the Punjabi voice booking flow (GET /api/voice/script, POST /api/voice/understand). */

export type VoiceLang = 'pa' | 'en';

export type VoiceStepId = 'phone' | 'village' | 'acres' | 'machine' | 'date';
export type VoiceParseStep = VoiceStepId | 'confirm';

export interface PlayItem {
  clip: string;
  gap_ms?: number;
}

export interface VoiceStepInfo {
  id: VoiceStepId;
  title_pa: string;
  title_en: string;
  ask_clip: string;
  ask_pa: string;
  ask_en: string;
  hint_pa: string;
  hint_en: string;
}

export interface VoiceScript {
  lang: string;
  languages: { id: VoiceLang; speech: string; label: string }[];
  today: string;
  steps: VoiceStepInfo[];
  prompts: Record<string, { pa: string; en: string }>;
  villages: { name: string; name_pa: string }[];
  machines: { id: string; name_pa: string; name_en: string }[];
}

export interface VoiceAlternative {
  value: string;
  display_pa: string;
  display_en: string;
}

export interface VoiceResult {
  step: VoiceParseStep;
  ok: boolean;
  heard: string;
  value: string | number | boolean | null;
  display_pa: string;
  display_en: string;
  readback: PlayItem[];
  prompt: string | null;
  error_code: string | null;
  confidence: number;
  alternatives: VoiceAlternative[];
  partial: string | null;
  correction: VoiceResult | null;
}

export interface VoiceContext {
  partial_phone?: string;
  pending?: 'kal';
  confirm_step?: VoiceStepId;
}

export interface VoiceUnderstandBody {
  step: VoiceParseStep;
  texts: string[];
  context?: VoiceContext;
  lang?: VoiceLang;
}

export interface VoiceManifest {
  version: number;
  lang: string;
  voice: string;
  generated_at: string;
  clips: Record<string, { file: string; text: string; sha: string; bytes?: number }>;
}
