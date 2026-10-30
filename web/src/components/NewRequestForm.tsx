import { useState, useRef, type FormEvent, type ChangeEvent } from 'react';
import { createRequest, ApiError } from '../api';
import { friendlyError } from '../errors';
import Badge from './Badge';
import type { RequestOut } from '../types';

interface Props {
  villages: string[];
  onSuccess: (newReq: RequestOut) => void;
  /** Focus the phone field on open (off on phones until the form is opened, so the keyboard does not pop up). */
  autoFocus?: boolean;
  /** Phones: the form opens from a button and can be closed again. */
  onClose?: () => void;
}

const SERVICE_TYPES = [
  { id: 'super_seeder', label: 'Super Seeder' },
  { id: 'happy_seeder', label: 'Happy Seeder' },
  { id: 'baler', label: 'Baler' },
  { id: 'mulcher', label: 'Mulcher' },
];

export default function NewRequestForm({ villages, onSuccess, autoFocus = true, onClose }: Props) {
  const [phone, setPhone] = useState('');
  const [name, setName] = useState('');
  const [village, setVillage] = useState('');
  const [acres, setAcres] = useState('');
  const [serviceType, setServiceType] = useState('super_seeder');
  const [harvestDate, setHarvestDate] = useState('');
  const [notCutYet, setNotCutYet] = useState(false);

  // Consents
  const [consentService, setConsentService] = useState(true);
  const [consentEvidence, setConsentEvidence] = useState(true);
  const [consentShare, setConsentShare] = useState(true);

  // Status & validation states
  const [submitting, setSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [outcomeMessage, setOutcomeMessage] = useState<string | null>(null);
  const [outcomeType, setOutcomeType] = useState<'success' | 'warning' | 'info'>('success');

  const phoneInputRef = useRef<HTMLInputElement>(null);

  const handlePhoneChange = (e: ChangeEvent<HTMLInputElement>) => {
    // Digits only, max 10
    const val = e.target.value.replace(/\D/g, '').slice(0, 10);
    setPhone(val);
    if (fieldErrors.phone) {
      setFieldErrors(prev => ({ ...prev, phone: '' }));
    }
  };

  const handleNotCutYetChange = (e: ChangeEvent<HTMLInputElement>) => {
    const checked = e.target.checked;
    setNotCutYet(checked);
    if (checked) {
      setHarvestDate('');
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setFieldErrors({});
    setGlobalError(null);
    setOutcomeMessage(null);

    const parsedAcres = parseFloat(acres);
    if (isNaN(parsedAcres)) {
      setFieldErrors({ acres: 'Please enter a valid acreage.' });
      setSubmitting(false);
      return;
    }

    try {
      const created = await createRequest({
        phone: phone.trim(),
        name: name.trim() || undefined,
        village: village.trim(),
        acres: parsedAcres,
        service_type: serviceType,
        harvest_date: notCutYet ? undefined : (harvestDate || undefined),
        consent_service: consentService,
        consent_evidence: consentEvidence,
        consent_share: consentShare,
      });

      // Construct outcome line
      if (created.status === 'scheduled' && created.slot) {
        setOutcomeType('success');
        setOutcomeMessage(`✓ Scheduled on ${created.slot.service_date} on ${created.slot.machine_name}`);
      } else if (created.status === 'will_miss') {
        setOutcomeType('warning');
        setOutcomeMessage(`⚠ Will miss: ${created.explanation?.reason || 'Capacity or deadline constraint'}`);
      } else if (created.status === 'needs_info') {
        setOutcomeType('info');
        setOutcomeMessage('ℹ Need info: no harvest date yet (scheduled once harvest date is provided)');
      } else {
        setOutcomeType('success');
        setOutcomeMessage(`✓ Request VR-${created.id} created (${created.status})`);
      }

      // Reset fields
      setPhone('');
      setName('');
      setVillage('');
      setAcres('');
      setHarvestDate('');
      setNotCutYet(false);

      onSuccess(created);

      // Re-focus phone
      phoneInputRef.current?.focus();
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.error_code === 'VALIDATION_ERROR' && err.details?.field) {
          const f = String(err.details.field);
          setFieldErrors({ [f]: err.message || 'Invalid value' });
        } else {
          setGlobalError(friendlyError(err.error_code) || err.message);
        }
      } else {
        setGlobalError('Failed to submit request.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="new-request-card" id="new-request-form">
      <div className="card-header">
        <div>
          <h2>New Request</h2>
          <span className="card-subtitle">Quick intake — fill in 15 seconds during a call</span>
        </div>
        {onClose && (
          <button type="button" className="icon-btn" id="btn-close-new-request" aria-label="Close new request" onClick={onClose}>
            ✕
          </button>
        )}
      </div>

      {outcomeMessage && (
        <div className={`outcome-banner outcome-${outcomeType}`} id="request-outcome-banner">
          {outcomeMessage}
        </div>
      )}

      {globalError && (
        <div className="outcome-banner outcome-error" id="request-global-error">
          {globalError}
        </div>
      )}

      <form onSubmit={handleSubmit} className="quick-form">
        <div className="form-grid">
          {/* Phone */}
          <div className="form-group">
            <label htmlFor="req-phone">Farmer Phone *</label>
            <input
              ref={phoneInputRef}
              id="req-phone"
              type="tel"
              inputMode="numeric"
              placeholder="10-digit number"
              value={phone}
              onChange={handlePhoneChange}
              autoFocus={autoFocus}
              required
              className={fieldErrors.phone ? 'input-error' : ''}
            />
            {fieldErrors.phone && <span className="field-error-msg">{fieldErrors.phone}</span>}
          </div>

          {/* Name */}
          <div className="form-group">
            <label htmlFor="req-name">Farmer Name (optional)</label>
            <input
              id="req-name"
              type="text"
              placeholder="e.g. Gurpreet Singh"
              value={name}
              onChange={e => setName(e.target.value)}
            />
          </div>

          {/* Village */}
          <div className="form-group">
            <label htmlFor="req-village">Village *</label>
            <input
              id="req-village"
              type="text"
              list="villages-list"
              placeholder="Type village name"
              value={village}
              onChange={e => setVillage(e.target.value)}
              required
              className={fieldErrors.village ? 'input-error' : ''}
            />
            <datalist id="villages-list">
              {villages.map(v => (
                <option key={v} value={v} />
              ))}
            </datalist>
            {fieldErrors.village && <span className="field-error-msg">{fieldErrors.village}</span>}
          </div>

          {/* Acres */}
          <div className="form-group">
            <label htmlFor="req-acres">Acres *</label>
            <input
              id="req-acres"
              type="number"
              inputMode="decimal"
              step="any"
              min="0.25"
              max="200"
              placeholder="e.g. 3.2"
              value={acres}
              onChange={e => setAcres(e.target.value)}
              required
              className={fieldErrors.acres ? 'input-error' : ''}
            />
            {fieldErrors.acres && <span className="field-error-msg">{fieldErrors.acres}</span>}
          </div>
        </div>

        {/* Service Type Selection: 4 big buttons */}
        <div className="form-group full-width">
          <label>Service Type *</label>
          <div className="service-buttons-grid">
            {SERVICE_TYPES.map(st => (
              <button
                key={st.id}
                type="button"
                id={`btn-service-${st.id}`}
                className={`service-btn ${serviceType === st.id ? 'selected' : ''}`}
                onClick={() => setServiceType(st.id)}
              >
                {st.label}
              </button>
            ))}
          </div>
        </div>

        {/* Harvest Date & Not cut yet */}
        <div className="form-grid align-center">
          <div className="form-group">
            <label htmlFor="req-harvest">Harvest Date (optional)</label>
            <input
              id="req-harvest"
              type="date"
              value={harvestDate}
              onChange={e => setHarvestDate(e.target.value)}
              disabled={notCutYet}
              className={fieldErrors.harvest_date ? 'input-error' : ''}
            />
            {fieldErrors.harvest_date && (
              <span className="field-error-msg">{fieldErrors.harvest_date}</span>
            )}
          </div>

          <div className="form-group checkbox-group not-cut-group">
            <label className="checkbox-label" htmlFor="req-not-cut">
              <input
                id="req-not-cut"
                type="checkbox"
                checked={notCutYet}
                onChange={handleNotCutYetChange}
              />
              <span>Not cut yet (request marked Need Info)</span>
            </label>
          </div>
        </div>

        {/* Consents & simulation notice */}
        <div className="consent-row">
          <div className="consent-checkboxes">
            <label className="checkbox-label" htmlFor="consent-service">
              <input
                id="consent-service"
                type="checkbox"
                checked={consentService}
                onChange={e => setConsentService(e.target.checked)}
                required
              />
              <span>Service consent *</span>
            </label>

            <label className="checkbox-label" htmlFor="consent-evidence">
              <input
                id="consent-evidence"
                type="checkbox"
                checked={consentEvidence}
                onChange={e => setConsentEvidence(e.target.checked)}
              />
              <span>Photo evidence consent</span>
            </label>

            <label className="checkbox-label" htmlFor="consent-share">
              <input
                id="consent-share"
                type="checkbox"
                checked={consentShare}
                onChange={e => setConsentShare(e.target.checked)}
              />
              <span>Data sharing consent</span>
            </label>
          </div>
          <Badge name="consent simulated" detail="demo" />
        </div>

        {/* Submit */}
        <div className="form-actions">
          <button
            id="btn-submit-request"
            type="submit"
            className="btn btn-primary btn-large"
            disabled={submitting}
          >
            {submitting ? 'Scheduling…' : 'Submit Request (Enter)'}
          </button>
        </div>
      </form>
    </div>
  );
}
