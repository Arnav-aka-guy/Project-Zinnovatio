import { useEffect, useState, useMemo, useCallback } from 'react';
import { Link } from 'react-router-dom';
import StatusStrip from '../components/StatusStrip';
import Badge from '../components/Badge';
import NewRequestForm from '../components/NewRequestForm';
import RequestDetailPanel from '../components/RequestDetailPanel';
import WillMissTab from '../components/WillMissTab';
import MachinesTab from '../components/MachinesTab';
import DeskMapPanel from '../optional/DeskMapPanel';
import {
  getDashboardSummary,
  getRequests,
  getMachines,
  getSchedule,
  runSchedule,
  getHealth,
  ApiError,
} from '../api';
import { triggerReauth } from '../components/PasscodeGate';
import { friendlyError } from '../errors';
import type {
  DashboardSummary,
  RequestOut,
  MachineOut,
  ScheduleDay,
} from '../types';

export default function DeskPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [requests, setRequests] = useState<RequestOut[]>([]);
  const [machines, setMachines] = useState<MachineOut[]>([]);
  const [todaySchedule, setTodaySchedule] = useState<ScheduleDay[]>([]);
  const [todayDate, setTodayDate] = useState<string>('');

  const [activeTab, setActiveTab] = useState<'requests' | 'will_miss' | 'machines' | 'map'>('requests');
  const [statusFilter, setStatusFilter] = useState('all');
  const [villageFilter, setVillageFilter] = useState('all');
  const [selectedRequest, setSelectedRequest] = useState<RequestOut | null>(null);

  const [loading, setLoading] = useState(true);
  const [runningScheduler, setRunningScheduler] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDeskData = useCallback(async () => {
    setError(null);
    try {
      const health = await getHealth();
      const currentToday = health.today;
      setTodayDate(currentToday);

      const [summaryData, requestsData, machinesData, scheduleData] = await Promise.all([
        getDashboardSummary(),
        getRequests(),
        getMachines(),
        getSchedule({ date: currentToday }),
      ]);

      setSummary(summaryData);
      setRequests(requestsData);
      setMachines(machinesData);
      setTodaySchedule(scheduleData);

      setSelectedRequest(prev => {
        if (!prev) return null;
        return requestsData.find(r => r.id === prev.id) || null;
      });
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          triggerReauth(err);
          return;
        }
        setError(friendlyError(err.error_code) || err.message);
      } else {
        setError('Failed to load operator desk data.');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDeskData();
  }, [loadDeskData]);

  const handleRunScheduler = async () => {
    setRunningScheduler(true);
    try {
      await runSchedule();
      await loadDeskData();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(friendlyError(err.error_code) || err.message);
      } else {
        setError('Failed to run scheduler.');
      }
    } finally {
      setRunningScheduler(false);
    }
  };

  const villagesList = useMemo(() => {
    const set = new Set<string>();
    requests.forEach(r => {
      if (r.village) set.add(r.village);
    });
    return Array.from(set).sort();
  }, [requests]);

  const filteredRequests = useMemo(() => {
    return requests.filter(r => {
      if (statusFilter !== 'all' && r.status !== statusFilter) return false;
      if (villageFilter !== 'all' && r.village !== villageFilter) return false;
      return true;
    });
  }, [requests, statusFilter, villageFilter]);

  const handleSelectRequestId = (id: number) => {
    const found = requests.find(r => r.id === id);
    if (found) {
      setSelectedRequest(found);
    }
  };

  return (
    <div className="desk-container" id="desk-page">
      <StatusStrip />

      {/* Top Header & Metrics Bar */}
      <div className="desk-header">
        <div className="desk-title-group">
          <h1>Operator Desk</h1>
          <p className="page-subtitle">Real-time request intake, machine dispatch, and schedule reflow</p>
        </div>

        <div className="desk-header-actions" style={{ display: 'flex', gap: '0.5rem' }}>
          <Link
            to="/intake"
            id="btn-add-register-photo"
            className="btn btn-secondary"
          >
            📷 Add from register photo
          </Link>
          <button
            id="btn-run-scheduler"
            type="button"
            className="btn btn-primary"
            onClick={handleRunScheduler}
            disabled={runningScheduler}
          >
            {runningScheduler ? 'Running Scheduler…' : '⚡ Run Scheduler'}
          </button>
        </div>
      </div>

      {/* Summary Counts Bar */}
      <div className="summary-metrics-bar" id="summary-metrics-bar">
        <div className="metric-card">
          <span className="metric-num">{summary?.total ?? (loading ? '…' : 0)}</span>
          <span className="metric-tag">Total Requests</span>
        </div>
        <div className="metric-card metric-scheduled">
          <span className="metric-num">{summary?.scheduled ?? (loading ? '…' : 0)}</span>
          <span className="metric-tag">Scheduled</span>
        </div>
        <div className="metric-card metric-will-miss">
          <span className="metric-num">{summary?.will_miss ?? (loading ? '…' : 0)}</span>
          <span className="metric-tag">Will Miss</span>
        </div>
        <div className="metric-card metric-needs-info">
          <span className="metric-num">{summary?.needs_info ?? (loading ? '…' : 0)}</span>
          <span className="metric-tag">Need info: no harvest date yet</span>
        </div>
      </div>

      {error && (
        <div className="outcome-banner outcome-error mb-3" id="desk-error-banner">
          {error}
          <button type="button" className="btn btn-secondary btn-sm ml-2" onClick={loadDeskData}>
            Retry
          </button>
        </div>
      )}

      {/* 15-Second New Request Form */}
      <NewRequestForm
        villages={villagesList}
        onSuccess={() => {
          loadDeskData();
        }}
      />

      {/* Tabs Row */}
      <div className="desk-tabs-bar" role="tablist">
        <button
          id="tab-requests"
          type="button"
          role="tab"
          aria-selected={activeTab === 'requests'}
          className={`tab-btn ${activeTab === 'requests' ? 'active' : ''}`}
          onClick={() => setActiveTab('requests')}
        >
          All Requests ({requests.length})
        </button>
        <button
          id="tab-will-miss"
          type="button"
          role="tab"
          aria-selected={activeTab === 'will_miss'}
          className={`tab-btn ${activeTab === 'will_miss' ? 'active' : ''}`}
          onClick={() => setActiveTab('will_miss')}
        >
          Will Miss ({summary?.will_miss ?? 0})
        </button>
        <button
          id="tab-machines"
          type="button"
          role="tab"
          aria-selected={activeTab === 'machines'}
          className={`tab-btn ${activeTab === 'machines' ? 'active' : ''}`}
          onClick={() => setActiveTab('machines')}
        >
          Machines ({machines.length})
        </button>
        <button
          id="tab-map"
          type="button"
          role="tab"
          aria-selected={activeTab === 'map'}
          className={`tab-btn ${activeTab === 'map' ? 'active' : ''}`}
          onClick={() => setActiveTab('map')}
        >
          Map ({todaySchedule.reduce((acc, d) => acc + d.slots.length, 0)} today)
        </button>
      </div>

      {/* Tab 1: Requests Table */}
      {activeTab === 'requests' && (
        <div className="card table-card" id="requests-tab-content">
          <div className="filters-bar">
            <div className="filter-group">
              <label htmlFor="filter-status">Status:</label>
              <select
                id="filter-status"
                value={statusFilter}
                onChange={e => setStatusFilter(e.target.value)}
              >
                <option value="all">All statuses</option>
                <option value="scheduled">Scheduled</option>
                <option value="will_miss">Will Miss</option>
                <option value="needs_info">Need Info</option>
                <option value="open">Open</option>
                <option value="done">Done</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>

            <div className="filter-group">
              <label htmlFor="filter-village">Village:</label>
              <select
                id="filter-village"
                value={villageFilter}
                onChange={e => setVillageFilter(e.target.value)}
              >
                <option value="all">All villages ({villagesList.length})</option>
                {villagesList.map(v => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </div>

            <div className="filter-count">
              Showing {filteredRequests.length} of {requests.length}
            </div>
          </div>

          {loading ? (
            <div className="loading-state">Loading requests…</div>
          ) : filteredRequests.length === 0 ? (
            <div className="empty-state">
              <p>No requests found matching the selected filters.</p>
            </div>
          ) : (
            <div className="table-responsive">
              <table className="data-table" id="desk-requests-table">
                <thead>
                  <tr>
                    <th>Farmer</th>
                    <th>Village</th>
                    <th>Acres</th>
                    <th>Service</th>
                    <th>Deadline</th>
                    <th>Status</th>
                    <th>Slot Date & Machine</th>
                    <th>Badges</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRequests.map(r => (
                    <tr
                      key={r.id}
                      className={`clickable-row ${selectedRequest?.id === r.id ? 'row-selected' : ''}`}
                      onClick={() => setSelectedRequest(r)}
                      id={`req-row-${r.id}`}
                    >
                      <td>
                        <div className="farmer-cell">
                          <strong className="farmer-name">{r.farmer.name || r.farmer.phone}</strong>
                          {r.farmer.name && <span className="farmer-phone-sub">{r.farmer.phone}</span>}
                        </div>
                      </td>
                      <td>{r.village}</td>
                      <td>{r.acres}</td>
                      <td className="text-capitalize">{r.service_type.replace('_', ' ')}</td>
                      <td>{r.deadline_date || '—'}</td>
                      <td>
                        <span className={`status-pill pill-${r.status}`}>{r.status}</span>
                      </td>
                      <td>
                        {r.slot ? (
                          <div className="slot-cell">
                            <span className="slot-date">{r.slot.service_date}</span>
                            <span className="slot-mach text-muted">• {r.slot.machine_name}</span>
                          </div>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>
                      <td>
                        {r.badges?.map(b => (
                          <Badge key={b} name={b} />
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {activeTab === 'will_miss' && (
        <div className="card" id="will-miss-tab-content">
          <WillMissTab onSelectRequest={handleSelectRequestId} />
        </div>
      )}

      {activeTab === 'machines' && (
        <div className="card" id="machines-tab-content">
          <MachinesTab
            machines={machines}
            schedule={todaySchedule}
            todayDate={todayDate}
            onRefreshAll={loadDeskData}
          />
        </div>
      )}

      {activeTab === 'map' && (
        <DeskMapPanel
          requests={requests}
          schedule={todaySchedule}
          todayDate={todayDate}
          onSelectRequest={(req) => setSelectedRequest(req)}
        />
      )}

      <RequestDetailPanel
        request={selectedRequest}
        onClose={() => setSelectedRequest(null)}
        onUpdate={loadDeskData}
      />
    </div>
  );
}
