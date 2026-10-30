import { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getRecord, verifyRecord, ApiError } from '../api';
import { friendlyError } from '../errors';
import { formatIST } from '../utils/image';
import Badge from '../components/Badge';
import type { RecordOut, RecordVerify } from '../types';

export default function RecordPage() {
  const { token } = useParams<{ token: string }>();

  const [record, setRecord] = useState<RecordOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);

  // Verification state
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<RecordVerify | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);

  const loadRecord = useCallback(async (recToken: string) => {
    setLoading(true);
    setError(null);
    setIsNotFound(false);
    setVerifyResult(null);
    setVerifyError(null);
    try {
      const data = await getRecord(recToken);
      setRecord(data);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 404 || err.error_code === 'NOT_FOUND') {
          setIsNotFound(true);
        } else {
          setError(friendlyError(err.error_code) || err.message);
        }
      } else {
        setError('Failed to load service record.');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (token) {
      loadRecord(token);
    } else {
      setIsNotFound(true);
      setLoading(false);
    }
  }, [token, loadRecord]);

  const handleVerify = async () => {
    if (!token) return;
    setVerifying(true);
    setVerifyError(null);
    try {
      const res = await verifyRecord(token);
      setVerifyResult(res);
    } catch (err) {
      if (err instanceof ApiError) {
        setVerifyError(friendlyError(err.error_code) || err.message);
      } else {
        setVerifyError('Verification check failed.');
      }
    } finally {
      setVerifying(false);
    }
  };

  const handlePrint = () => {
    window.print();
  };

  // Flag translator into plain words
  const formatFlag = (flag: string): string => {
    switch (flag) {
      case 'too_fast':
        return 'Too fast: job completed under 25 min/acre';
      case 'position_mismatch':
        return 'Position mismatch: reported fix outside plot boundary';
      case 'exact_duplicate_photo':
        return 'Exact duplicate photo detected';
      case 'code_missing':
        return 'Farmer code not provided';
      case 'code_wrong':
        return 'Farmer code did not match record';
      default:
        return flag.replace('_', ' ');
    }
  };

  if (loading) {
    return (
      <div className="receipt-container" id="record-page">
        <div className="loading-state">Loading service record…</div>
      </div>
    );
  }

  if (isNotFound) {
    return (
      <div className="receipt-container" id="record-page">
        <div className="record-not-found-card" id="record-not-found">
          <h2>Service Record Not Found</h2>
          <p>
            No completion record exists for token: <code>{token}</code>.
          </p>
          <p className="text-muted mt-2">
            Please check the link provided in the message or contact your custom hiring centre.
          </p>
          <div className="mt-3">
            <Link to="/desk" className="btn btn-secondary">
              Back to Desk
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (error || !record) {
    return (
      <div className="receipt-container" id="record-page">
        <div className="outcome-banner outcome-error">
          {error || 'Unable to display record'}
          <button type="button" className="btn btn-secondary btn-sm ml-2" onClick={() => token && loadRecord(token)}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="receipt-container" id="record-page">
      {/* Printable Receipt Card */}
      <article className="receipt-sheet" id="receipt-sheet">
        {/* Receipt Header */}
        <header className="receipt-header">
          <div className="receipt-brand">
            <span className="receipt-icon">🌾</span>
            <div>
              <h1 className="receipt-title">Service Completion Record</h1>
              <span className="receipt-punjabi-title">ਸੇਵਾ ਪੂਰੀ ਹੋਣ ਦਾ ਰਿਕਾਰਡ</span>
            </div>
          </div>
          <div className="receipt-actions no-print">
            <button
              id="btn-print-receipt"
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={handlePrint}
            >
              🖨️ Print Receipt / PDF
            </button>
            {typeof navigator !== 'undefined' && 'share' in navigator && (
              <button
                id="btn-share-record"
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() =>
                  void navigator
                    .share({ title: 'Service Completion Record', text: 'ਸੇਵਾ ਪੂਰੀ ਹੋਣ ਦਾ ਰਿਕਾਰਡ / Service record', url: window.location.href })
                    .catch(() => undefined)
                }
              >
                ↗ Share
              </button>
            )}
          </div>
        </header>

        {/* Badges Bar */}
        {record.badges && record.badges.length > 0 && (
          <div className="receipt-badges-row" id="receipt-badges">
            {record.badges.map((b) => (
              <Badge key={b} name={b} />
            ))}
          </div>
        )}

        {/* Evidence Note Banner if present */}
        {record.evidence_note && (
          <div className="evidence-note-banner" id="evidence-note-banner">
            ℹ️ {record.evidence_note}
          </div>
        )}

        {/* Vertical Timeline */}
        <div className="vertical-timeline" id="record-timeline">
          {/* Step 1: Request */}
          <div className="timeline-node">
            <div className="timeline-marker step-1">1</div>
            <div className="timeline-content">
              <span className="timeline-step-label">Step 1 • Request Intake</span>
              <div className="timeline-grid">
                <div>
                  <span className="attr-label">Request ID</span>
                  <strong className="timeline-id">{record.request_id}</strong>
                </div>
                <div>
                  <span className="attr-label">Village</span>
                  <p>{record.village}</p>
                </div>
                <div>
                  <span className="attr-label">Acreage</span>
                  <p>{record.acres} acres</p>
                </div>
                <div>
                  <span className="attr-label">Service Type</span>
                  <p className="text-capitalize">{record.service_type.replace('_', ' ')}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Step 2: Assignment */}
          <div className="timeline-node">
            <div className="timeline-marker step-2">2</div>
            <div className="timeline-content">
              <span className="timeline-step-label">Step 2 • Machine Assignment</span>
              <div className="timeline-grid">
                <div>
                  <span className="attr-label">Assigned Machine</span>
                  <strong>{record.machine}</strong>
                </div>
                <div>
                  <span className="attr-label">Scheduled Date</span>
                  <p>{record.scheduled}</p>
                </div>
                <div>
                  <span className="attr-label">Sowing Deadline</span>
                  <p>{record.deadline_date || '—'}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Step 3: Start Evidence */}
          <div className="timeline-node">
            <div className="timeline-marker step-3">3</div>
            <div className="timeline-content">
              <span className="timeline-step-label">Step 3 • Start Evidence</span>
              <div className="timeline-grid">
                <div>
                  <span className="attr-label">Start Time (IST)</span>
                  <p>{formatIST(record.started_at)}</p>
                </div>
                <div>
                  <span className="attr-label">Position State</span>
                  <div className="mt-1">
                    {record.start_position === 'not_checked' ? (
                      <Badge name="position not checked" />
                    ) : record.start_position === 'not_given' ? (
                      <Badge name="position self-reported" />
                    ) : (
                      <p className="text-capitalize">{record.start_position.replace('_', ' ')}</p>
                    )}
                  </div>
                </div>
                <div>
                  <span className="attr-label">Field Photo</span>
                  <p>{record.start_photo === 'present' ? '✓ Photo present' : 'None'}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Step 4: Completion Evidence */}
          <div className="timeline-node">
            <div className="timeline-marker step-4">4</div>
            <div className="timeline-content">
              <span className="timeline-step-label">Step 4 • Completion Evidence</span>
              <div className="timeline-grid">
                <div>
                  <span className="attr-label">Completion Time (IST)</span>
                  <p>{formatIST(record.done_at)}</p>
                </div>
                <div>
                  <span className="attr-label">Position State</span>
                  <div className="mt-1">
                    {record.done_position === 'not_checked' ? (
                      <Badge name="position not checked" />
                    ) : record.done_position === 'not_given' ? (
                      <Badge name="position self-reported" />
                    ) : (
                      <p className="text-capitalize">{record.done_position.replace('_', ' ')}</p>
                    )}
                  </div>
                </div>
                <div>
                  <span className="attr-label">Field Photo</span>
                  <p>{record.done_photo === 'present' ? '✓ Photo present' : 'None'}</p>
                </div>
                <div>
                  <span className="attr-label">Farmer Confirmation</span>
                  <p>
                    {record.farmer_confirmed === true
                      ? '✓ Code confirmed'
                      : record.farmer_confirmed === false
                      ? 'Code mismatch'
                      : 'Code not entered'}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Step 5: Outcome */}
          <div className="timeline-node">
            <div className="timeline-marker step-5">✓</div>
            <div className="timeline-content outcome-content">
              <span className="timeline-step-label">Step 5 • Final Service Outcome</span>
              <div className="outcome-row">
                <span className="outcome-pill pill-completed">{record.outcome}</span>
                <span className={`outcome-timing ${record.on_time ? 'timing-on-time' : 'timing-late'}`}>
                  {record.on_time ? '✓ Completed on time' : '⚠ Completed after deadline'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Flags Section */}
        {record.flags && record.flags.length > 0 && (
          <section className="receipt-flags-card" id="record-flags-section">
            <div className="flags-header">
              <h3>Auditing Flags ({record.flags.length})</h3>
            </div>
            <ul className="flags-list-items">
              {record.flags.map((fl) => (
                <li key={fl} className="flag-item">
                  <span className="badge badge-warning">{formatFlag(fl)}</span>
                </li>
              ))}
            </ul>
            <p className="flags-disclaimer">
              Flags ask a person to look. They never penalise anyone.
            </p>
          </section>
        )}

        {/* Cryptographic Hash & Verification Box */}
        <section className="record-hash-card" id="record-hash-box">
          <div className="hash-header">
            <h3>Tamper-Evident Record Hash ({record.hash_version})</h3>
            <button
              id="btn-verify-hash"
              type="button"
              className="btn btn-secondary btn-sm no-print"
              onClick={handleVerify}
              disabled={verifying}
            >
              {verifying ? 'Verifying…' : '🔍 Verify Hash'}
            </button>
          </div>

          <div className="hash-box-code" id="record-hash-code">
            <code>{record.record_hash}</code>
          </div>

          {/* Verification Result Banner */}
          {verifyResult && (
            <div
              className={`outcome-banner mt-2 ${
                verifyResult.match ? 'outcome-success' : 'outcome-error'
              }`}
              id="verify-result-banner"
            >
              {verifyResult.match
                ? '✓ Matches: this record has not been edited since capture'
                : '⚠ Does not match: this record was changed after capture'}
            </div>
          )}

          {verifyError && (
            <div className="outcome-banner outcome-error mt-2">{verifyError}</div>
          )}

          <p className="hash-sub-disclaimer">
            The hash shows later edits. It cannot show that the position was honest.
          </p>
        </section>

        {/* Privacy Note */}
        <footer className="receipt-footer">
          <small className="text-muted">
            Vaari Public Proof of Service • Privacy protected: personal names and contact numbers are strictly withheld from public records.
          </small>
        </footer>
      </article>
    </div>
  );
}
