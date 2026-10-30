import { useEffect, useState, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import StatusStrip from '../components/StatusStrip';
import {
  getDashboardSummary,
  getWillMiss,
  getMachines,
  downloadUsageCsv,
  ApiError,
} from '../api';
import { triggerReauth } from '../components/PasscodeGate';
import { friendlyError } from '../errors';
import type { DashboardSummary, WillMissItem, MachineOut } from '../types';

const REASON_ACTIONS: Record<string, string> = {
  INVALID_REQUEST: 'Correct the request.',
  DEADLINE_PASSED: 'Call the farmer and record the outcome.',
  NO_COMPATIBLE_MACHINE: 'Refer to another centre.',
  MACHINE_UNAVAILABLE: 'Check repairs, or ask a nearby centre.',
  TRAVEL_INFEASIBLE: 'Refer to the nearest centre that offers the service.',
  NO_CAPACITY: 'Check the alternate centre listed.',
};

const FLAG_LABELS: Record<string, string> = {
  too_fast: 'Finished faster than a machine can work',
  position_mismatch: 'Position outside expected plot',
  exact_duplicate_photo: 'Exact duplicate photo',
  code_missing: "Farmer's code not entered",
  code_wrong: "Farmer's code wrong",
};

export default function OfficerPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [willMissList, setWillMissList] = useState<WillMissItem[]>([]);
  const [machines, setMachines] = useState<MachineOut[]>([]);

  const [filterDate, setFilterDate] = useState('');
  const [filterVillage, setFilterVillage] = useState('all');
  const [filterMachineId, setFilterMachineId] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<number>(Date.now());
  const [secondsAgo, setSecondsAgo] = useState(0);

  const fetchData = useCallback(async () => {
    setError(null);
    try {
      const summaryParams = {
        date: filterDate || undefined,
        village: filterVillage !== 'all' ? filterVillage : undefined,
        machine_id: filterMachineId !== 'all' ? parseInt(filterMachineId, 10) : undefined,
        status: filterStatus !== 'all' ? filterStatus : undefined,
      };

      const [summaryRes, willMissRes, machinesRes] = await Promise.all([
        getDashboardSummary(summaryParams),
        getWillMiss(),
        getMachines(),
      ]);

      setSummary(summaryRes);
      setWillMissList(willMissRes);
      setMachines(machinesRes);
      setLastUpdated(Date.now());
      setSecondsAgo(0);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          triggerReauth(err);
          return;
        }
        setError(friendlyError(err.error_code) || err.message);
      } else {
        setError('Failed to load officer dashboard.');
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [filterDate, filterVillage, filterMachineId, filterStatus]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    const timer = setInterval(() => {
      fetchData();
    }, 15000);
    return () => clearInterval(timer);
  }, [fetchData]);

  useEffect(() => {
    const ticker = setInterval(() => {
      setSecondsAgo(Math.floor((Date.now() - lastUpdated) / 1000));
    }, 1000);
    return () => clearInterval(ticker);
  }, [lastUpdated]);

  const handleManualRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  const handleDownloadCsv = async () => {
    try {
      const csvText = await downloadUsageCsv();
      const blob = new Blob([csvText], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'vaari_usage.csv';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(friendlyError(err.error_code) || err.message);
      }
    }
  };

  const villagesList = useMemo(() => {
    if (!summary?.by_village) return [];
    return Object.keys(summary.by_village).sort();
  }, [summary?.by_village]);

  const maxReasonCount = useMemo(() => {
    if (!summary?.by_reason) return 1;
    const counts = Object.values(summary.by_reason);
    return counts.length > 0 ? Math.max(...counts, 1) : 1;
  }, [summary?.by_reason]);

  const flaggedJobs = summary?.flagged_jobs || [];

  return (
    <div className="officer-container" id="officer-page">
      <StatusStrip />

      <div className="officer-header">
        <div>
          <div className="officer-badge-row">
            <span className="badge badge-accent">Officer Overview</span>
            <span className="officer-ticker" id="officer-refresh-ticker">
              Updated {secondsAgo === 0 ? 'just now' : `${secondsAgo}s ago`}
            </span>
          </div>
          <h1 className="page-title">Operations & Oversight Dashboard</h1>
          <p className="page-subtitle">
            Aggregate progress, capacity utilization, and machine assignment oversight
          </p>
        </div>

        <div className="officer-header-actions" style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            id="btn-download-usage-csv"
            type="button"
            className="btn btn-secondary"
            onClick={handleDownloadCsv}
          >
            📥 Download usage CSV
          </button>
          <button
            id="btn-officer-refresh"
            type="button"
            className="btn btn-secondary"
            onClick={handleManualRefresh}
            disabled={refreshing}
          >
            {refreshing ? 'Refreshing…' : '🔄 Refresh Data'}
          </button>
        </div>
      </div>

      {error && (
        <div className="outcome-banner outcome-error" id="officer-error-banner">
          {error}
          <button type="button" className="btn btn-secondary btn-sm ml-2" onClick={handleManualRefresh}>
            Retry
          </button>
        </div>
      )}

      {/* Filters Bar */}
      <section className="card filter-card" id="officer-filters-bar">
        <div className="officer-filters-grid">
          <div className="form-group">
            <label htmlFor="filter-officer-date">Date:</label>
            <input
              id="filter-officer-date"
              type="date"
              value={filterDate}
              onChange={(e) => setFilterDate(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label htmlFor="filter-officer-village">Village:</label>
            <select
              id="filter-officer-village"
              value={filterVillage}
              onChange={(e) => setFilterVillage(e.target.value)}
            >
              <option value="all">All villages</option>
              {villagesList.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="filter-officer-machine">Machine:</label>
            <select
              id="filter-officer-machine"
              value={filterMachineId}
              onChange={(e) => setFilterMachineId(e.target.value)}
            >
              <option value="all">All machines</option>
              {machines.map((m) => (
                <option key={m.id} value={String(m.id)}>
                  {m.name}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="filter-officer-status">Status:</label>
            <select
              id="filter-officer-status"
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
            >
              <option value="all">All statuses</option>
              <option value="scheduled">Scheduled</option>
              <option value="in_progress">In Progress</option>
              <option value="done">Completed</option>
              <option value="will_miss">Will Miss</option>
              <option value="needs_info">Need Info</option>
              <option value="open">Open</option>
            </select>
          </div>
        </div>
      </section>

      {/* 8 Core Metrics Cards */}
      <section className="officer-metrics-grid" id="officer-summary-cards">
        <div className="card metric-card" id="metric-total">
          <span className="metric-num">{summary?.total ?? (loading ? '…' : 0)}</span>
          <span className="metric-tag">Total Requests</span>
        </div>

        <div className="card metric-card metric-scheduled" id="metric-scheduled">
          <span className="metric-num">{summary?.scheduled ?? (loading ? '…' : 0)}</span>
          <span className="metric-tag">Scheduled</span>
        </div>

        <div className="card metric-card metric-progress" id="metric-in-progress">
          <span className="metric-num">{summary?.in_progress ?? (loading ? '…' : 0)}</span>
          <span className="metric-tag">In Progress</span>
        </div>

        <div className="card metric-card metric-completed" id="metric-completed">
          <span className="metric-num">{summary?.completed ?? (loading ? '…' : 0)}</span>
          <span className="metric-tag">Completed</span>
        </div>

        <div className="card metric-card metric-will-miss" id="metric-will-miss">
          <span className="metric-num">{summary?.will_miss ?? (loading ? '…' : 0)}</span>
          <span className="metric-tag">Will Miss</span>
        </div>

        <div className="card metric-card metric-review" id="metric-needs-review">
          <span className="metric-num">{summary?.needs_review ?? (loading ? '…' : 0)}</span>
          <span className="metric-tag">Needs Review</span>
          <small className="metric-subtag">Jobs flagged for a person to look at</small>
        </div>

        <div className="card metric-card metric-needs-info" id="metric-needs-info">
          <span className="metric-num">{summary?.needs_info ?? (loading ? '…' : 0)}</span>
          <span className="metric-tag">Needs Info</span>
          <small className="metric-subtag">Awaiting harvest date</small>
        </div>

        <div className="card metric-card metric-capacity" id="metric-capacity">
          <span className="metric-num">{summary?.capacity_used_pct ?? (loading ? '…' : 0)}%</span>
          <span className="metric-tag">7-Day Capacity Used</span>
          <small className="metric-subtag">Active fleet capacity</small>
        </div>
      </section>

      {/* Flagged Jobs for Review Section (Step 07: village, machine, flags, link to record — no names or phones) */}
      <section className="card" id="officer-flagged-jobs-section">
        <div className="card-header">
          <div>
            <h2>Jobs Flagged for Review ({flaggedJobs.length})</h2>
            <p className="card-subtitle">
              Flags ask a person to look. They never penalise anyone. No personal names or phone numbers are shown.
            </p>
          </div>
        </div>

        {flaggedJobs.length === 0 ? (
          <p className="text-muted p-2">No jobs currently flagged for review.</p>
        ) : (
          <div className="table-responsive">
            <table className="data-table" id="officer-flagged-jobs-table">
              <thead>
                <tr>
                  <th>Request</th>
                  <th>Village</th>
                  <th>Machine</th>
                  <th>Acres</th>
                  <th>Flags</th>
                  <th>Record</th>
                </tr>
              </thead>
              <tbody>
                {flaggedJobs.map((fj) => (
                  <tr key={fj.slot_id} id={`flagged-job-row-${fj.slot_id}`}>
                    <td><strong>{fj.request_id}</strong></td>
                    <td>{fj.village}</td>
                    <td>{fj.machine}</td>
                    <td>{fj.acres} ac</td>
                    <td>
                      {fj.flags.map((fl) => (
                        <span key={fl} className="badge badge-warning mr-1">
                          {FLAG_LABELS[fl] || fl}
                        </span>
                      ))}
                    </td>
                    <td>
                      {fj.record_token ? (
                        <Link
                          to={`/record/${fj.record_token}`}
                          className="btn btn-secondary btn-sm"
                        >
                          View Record ➔
                        </Link>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Middle Row: Will Miss by Reason & By Village */}
      <div className="officer-middle-grid">
        <section className="card reason-breakdown-card" id="by-reason-card">
          <div className="card-header">
            <h2>Will Miss by Reason</h2>
            <span className="badge badge-neutral">Operational Bottlenecks</span>
          </div>

          {!summary?.by_reason || Object.keys(summary.by_reason).length === 0 ? (
            <p className="text-muted p-2">No unserved requests recorded.</p>
          ) : (
            <div className="reason-bars-list">
              {Object.entries(summary.by_reason).map(([code, count]) => {
                const pct = Math.round((count / maxReasonCount) * 100);
                const nextAction = REASON_ACTIONS[code] || 'Review alternative allocation.';

                return (
                  <div key={code} className="reason-bar-item" id={`reason-bar-${code}`}>
                    <div className="reason-bar-label-row">
                      <span className="reason-code-name">
                        <span className={`reason-chip chip-${code.toLowerCase()}`}>{code}</span>
                      </span>
                      <strong className="reason-count">{count} {count === 1 ? 'request' : 'requests'}</strong>
                    </div>

                    <div className="reason-bar-track">
                      <div className="reason-bar-fill" style={{ width: `${pct}%` }} />
                    </div>

                    <div className="reason-action-line">
                      <strong>Next Action: </strong>
                      <span>{nextAction}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        <section className="card village-breakdown-card" id="by-village-card">
          <div className="card-header">
            <h2>Requests by Village</h2>
            <span className="badge badge-neutral">Geographic Distribution</span>
          </div>

          {!summary?.by_village || Object.keys(summary.by_village).length === 0 ? (
            <p className="text-muted p-2">No village data available.</p>
          ) : (
            <div className="table-responsive max-h-300">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Village</th>
                    <th className="text-right">Requests</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(summary.by_village)
                    .sort(([, a], [, b]) => b - a)
                    .map(([vName, count]) => (
                      <tr key={vName}>
                        <td><strong>{vName}</strong></td>
                        <td className="text-right">{count}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      {/* Will-Miss Full List (Strictly NO phone numbers or farmer names) */}
      <section className="card will-miss-section" id="officer-will-miss-table">
        <div className="card-header">
          <div>
            <h2>Unserved Requests ({willMissList.length})</h2>
            <p className="card-subtitle">
              Sowing deadlines at risk — anonymized for officer inspection
            </p>
          </div>
          <span className="badge badge-warning">Action Required</span>
        </div>

        {willMissList.length === 0 ? (
          <div className="empty-state p-3">
            <p>No unserved requests in the system.</p>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Request ID</th>
                  <th>Village</th>
                  <th>Acres</th>
                  <th>Service</th>
                  <th>Deadline</th>
                  <th>Reason</th>
                  <th>Next Action</th>
                  <th>Alternative Centre</th>
                </tr>
              </thead>
              <tbody>
                {willMissList.map((item) => (
                  <tr key={item.request_id} id={`officer-miss-row-${item.request_id}`}>
                    <td><strong>VR-{item.request_id}</strong></td>
                    <td>{item.village}</td>
                    <td>{item.acres}</td>
                    <td className="text-capitalize">{item.service_type.replace('_', ' ')}</td>
                    <td>{item.deadline_date || '—'}</td>
                    <td>
                      <span className={`reason-chip chip-${item.reason_code.toLowerCase()}`}>
                        {item.reason_code}
                      </span>
                    </td>
                    <td className="next-action-cell">
                      <strong>{item.next_action}</strong>
                    </td>
                    <td>
                      {item.nearest_alternative ? (
                        <span>
                          {item.nearest_alternative}
                          {item.alternative_distance_km != null && (
                            <span className="text-muted"> ({item.alternative_distance_km} km)</span>
                          )}
                        </span>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <footer className="officer-footer" id="officer-disclaimer">
        <p className="officer-disclaimer-text">
          Will miss means the request cannot be served before its deadline with the machines available. It is never a statement about what a farmer will do.
        </p>
      </footer>
    </div>
  );
}
