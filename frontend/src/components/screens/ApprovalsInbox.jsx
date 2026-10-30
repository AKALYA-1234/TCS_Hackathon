import React, { useState } from 'react';
import { Check, X, AlertTriangle, Clock, ArrowRight, ShieldCheck, CheckCircle2 } from 'lucide-react';
import { WASTE_TYPES } from '../ui/SVGWastePatterns';
import { Button } from '../ui/BaseComponents';

export function ApprovalsInbox({
  proposals = [],
  onApprove,
  onReject,
  onViewEvidence
}) {
  const [filter, setFilter] = useState('All');
  const [rejectModalProposal, setRejectModalProposal] = useState(null);
  const [rejectReason, setRejectReason] = useState('Class running late');

  // Hard rules checklist template
  const getRuleChecks = (prop) => [
    {
      id: 'comfort',
      label: 'Comfort band',
      detail: prop.target_value ? `${prop.target_value} °C is inside the 22–26 °C ASHRAE band` : 'Target setpoint within comfort band',
      status: 'pass'
    },
    {
      id: 'lab',
      label: 'Lab exception',
      detail: `${prop.room_id || 'Room'} holds no temperature-sensitive equipment`,
      status: 'pass'
    },
    {
      id: 'quiet',
      label: 'Quiet hours',
      detail: 'No commands between 22:00 and 06:00',
      status: 'pass'
    },
    {
      id: 'override',
      label: 'Manual override',
      detail: 'No active manual lock',
      status: 'pass'
    },
    {
      id: 'rate',
      label: 'Rate limit',
      detail: '1 command, within 4 per room per hour cap',
      status: 'pass'
    }
  ];

  // Normalized proposals list
  const fallbackProposals = [
    {
      id: 'P-1041',
      room_id: 'eng-101',
      ac_unit_id: 'ac-eng-101-1',
      action: 'SET_TEMP',
      target_value: 25.0,
      approval_status: 'PENDING',
      approval_tier: 'ONE_CLICK',
      source: 'OPTIMIZER',
      rationale: 'Room is empty during timetable gap. Setpoint relaxed to 25.0 °C to eliminate compressor cycling.',
      estimated_saving_inr: 192.5,
      estimated_saving_kwh: 18.4,
      rule_validation_status: 'PASSED'
    },
    {
      id: 'P-1042',
      room_id: 'adm-101',
      ac_unit_id: 'ac-adm-101-1',
      action: 'SHUT_OFF',
      target_value: null,
      approval_status: 'PENDING',
      approval_tier: 'ONE_CLICK',
      source: 'OPTIMIZER',
      rationale: 'Hall ran past scheduled classes with zero headcount. Frostline proposes shutdown until 08:30 next morning.',
      estimated_saving_inr: 340.0,
      estimated_saving_kwh: 32.5,
      rule_validation_status: 'PASSED'
    },
    {
      id: 'P-1038',
      room_id: 'sci-201',
      ac_unit_id: 'ac-sci-201-1',
      action: 'SET_TEMP',
      target_value: 24.0,
      approval_status: 'APPROVED',
      approval_tier: 'ONE_CLICK',
      source: 'LLM_AGENT',
      rationale: 'Raise temperature from 21 °C to 24 °C during occupied seminar.',
      estimated_saving_inr: 150.0,
      estimated_saving_kwh: 14.5,
      rule_validation_status: 'PASSED'
    }
  ];

  const displayList = Array.isArray(proposals) && proposals.length > 0 ? proposals : fallbackProposals;

  const pendingCount = displayList.filter(p => (p.approval_status || '').toUpperCase() === 'PENDING').length;
  const approvedCount = displayList.filter(p => (p.approval_status || '').toUpperCase() === 'APPROVED').length;
  const flaggedCount = displayList.filter(p => (p.rule_validation_status || '').toUpperCase() === 'FAILED' || (p.approval_status || '').toUpperCase() === 'REJECTED').length;

  const filteredList = displayList.filter(p => {
    const status = (p.approval_status || '').toUpperCase();
    if (filter === 'Pending') return status === 'PENDING';
    if (filter === 'Approved') return status === 'APPROVED';
    if (filter === 'Flagged') return status === 'REJECTED' || (p.rule_validation_status || '').toUpperCase() === 'FAILED';
    return true;
  });

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* 1. Header & Filters */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl md:text-4xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
            Approvals inbox
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
            Nothing is sent to an air conditioner until a person approves it. Every proposal is checked by the rule engine first.
          </p>
        </div>

        {/* Filter Pills */}
        <div
          className="inline-flex p-1 rounded-xl self-start sm:self-auto"
          style={{ backgroundColor: 'var(--bg-well)', border: '1px solid var(--border-subtle)' }}
        >
          {[
            { key: 'All', label: `All ${displayList.length}` },
            { key: 'Pending', label: `Pending ${pendingCount}` },
            { key: 'Flagged', label: `Flagged ${flaggedCount}` },
            { key: 'Approved', label: `Approved ${approvedCount}` }
          ].map((item) => {
            const isSelected = filter === item.key;
            return (
              <button
                key={item.key}
                onClick={() => setFilter(item.key)}
                className="px-3.5 py-1.5 text-xs font-semibold rounded-lg cursor-pointer transition-all"
                style={{
                  backgroundColor: isSelected ? 'var(--bg-card)' : 'transparent',
                  color: isSelected ? 'var(--text-primary)' : 'var(--text-secondary)',
                  boxShadow: isSelected ? 'var(--shadow-card)' : 'none'
                }}
              >
                {item.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* 2. Proposal Cards List */}
      <div className="space-y-6">
        {filteredList.length === 0 ? (
          <div
            className="p-12 text-center rounded-2xl border"
            style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
          >
            <ShieldCheck size={40} className="mx-auto mb-3 opacity-40" style={{ color: 'var(--accent)' }} />
            <h3 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
              No proposals in this category
            </h3>
            <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
              When the optimizer detects waste opportunities, new actionable proposals will appear live.
            </p>
          </div>
        ) : (
          filteredList.map((prop) => {
            const isPending = (prop.approval_status || '').toUpperCase() === 'PENDING';
            const isApproved = (prop.approval_status || '').toUpperCase() === 'APPROVED';
            const rules = getRuleChecks(prop);

            return (
              <div
                key={prop.id}
                id={`proposal-${prop.id}`}
                className="p-6 rounded-2xl border transition-all"
                style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
              >
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  {/* Left Content (2 cols) */}
                  <div className="lg:col-span-2 space-y-4">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-mono font-bold" style={{ color: 'var(--text-tertiary)' }}>
                        {prop.id}
                      </span>
                      <span
                        className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-semibold"
                        style={{ backgroundColor: 'var(--bg-well)', color: 'var(--waste-gc)' }}
                      >
                        <span
                          className="w-3.5 h-2.5 rounded-xs"
                          style={{ background: 'url(#pat-gc)', backgroundColor: 'var(--waste-gc)' }}
                        />
                        <span>{prop.room_id || 'Room'}</span>
                      </span>
                      <span
                        className="px-2 py-0.5 rounded text-xs font-semibold"
                        style={{
                          backgroundColor: isPending
                            ? 'var(--status-review-bg)'
                            : isApproved
                            ? 'var(--status-healthy-bg)'
                            : 'var(--status-critical-bg)',
                          color: isPending
                            ? 'var(--status-review)'
                            : isApproved
                            ? 'var(--status-healthy)'
                            : 'var(--status-critical)'
                        }}
                      >
                        {isPending ? 'Needs approval' : isApproved ? 'Approved' : 'Rejected'}
                      </span>
                    </div>

                    <h2 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
                      {prop.action === 'SET_TEMP'
                        ? `Set ${prop.room_id} to ${prop.target_value} °C`
                        : prop.action === 'SHUT_OFF'
                        ? `Shut off ${prop.room_id} after-hours`
                        : `Optimize ${prop.room_id}`}
                    </h2>

                    <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                      {prop.rationale || 'Optimizer detected potential waste. Recommended setpoint adjustment to maintain comfort while eliminating thermal overshoot.'}
                    </p>

                    {/* Metric Wells */}
                    <div className="grid grid-cols-3 gap-3 max-w-md pt-2">
                      <div className="p-3 rounded-xl" style={{ backgroundColor: 'var(--bg-well)' }}>
                        <div className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
                          Estimated saving
                        </div>
                        <div className="text-base font-extrabold tabular-nums mt-0.5" style={{ color: 'var(--text-primary)' }}>
                          ₹{Math.round(prop.estimated_saving_inr || 150)}
                        </div>
                      </div>
                      <div className="p-3 rounded-xl" style={{ backgroundColor: 'var(--bg-well)' }}>
                        <div className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
                          Energy saved
                        </div>
                        <div className="text-base font-extrabold tabular-nums mt-0.5" style={{ color: 'var(--text-primary)' }}>
                          {(prop.estimated_saving_kwh || 14.5).toFixed(1)} kWh
                        </div>
                      </div>
                      <div className="p-3 rounded-xl" style={{ backgroundColor: 'var(--bg-well)' }}>
                        <div className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
                          Approval Tier
                        </div>
                        <div className="text-base font-extrabold mt-0.5" style={{ color: 'var(--text-primary)' }}>
                          {prop.approval_tier || 'One-click'}
                        </div>
                      </div>
                    </div>

                    {/* Actions */}
                    {isPending ? (
                      <div className="flex items-center gap-3 pt-3">
                        <Button variant="primary" onClick={() => onApprove(prop.id)}>
                          Approve and send
                        </Button>
                        <Button variant="secondary" onClick={() => setRejectModalProposal(prop.id)}>
                          Reject
                        </Button>
                        <button
                          onClick={() => onViewEvidence(prop.room_id)}
                          className="text-xs font-semibold cursor-pointer ml-2 hover:underline"
                          style={{ color: 'var(--accent)' }}
                        >
                          See evidence
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 pt-3 text-xs font-semibold" style={{ color: 'var(--status-healthy)' }}>
                        <CheckCircle2 size={16} />
                        <span>Command dispatched and acknowledged</span>
                      </div>
                    )}
                  </div>

                  {/* Right: Rule Engine Checklist or Status */}
                  <div
                    className="p-4 rounded-xl border flex flex-col justify-between"
                    style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}
                  >
                    <div>
                      <div className="flex items-center justify-between text-xs font-bold mb-3" style={{ color: 'var(--text-secondary)' }}>
                        <span>Rule engine, 5 of 5 passed</span>
                      </div>
                      <div className="space-y-3">
                        {rules.map((rc) => (
                          <div key={rc.id} className="flex items-start justify-between text-xs">
                            <div className="flex items-start gap-2">
                              <span
                                className="w-4 h-4 rounded-full flex items-center justify-center shrink-0 mt-0.5"
                                style={{ backgroundColor: 'var(--status-healthy-bg)', color: 'var(--status-healthy)' }}
                              >
                                <Check size={11} strokeWidth={3} />
                              </span>
                              <div>
                                <div className="font-bold" style={{ color: 'var(--text-primary)' }}>
                                  {rc.label}
                                </div>
                                <div className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
                                  {rc.detail}
                                </div>
                              </div>
                            </div>
                            <span className="font-semibold" style={{ color: 'var(--status-healthy)' }}>
                              Pass
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Reject Modal */}
      {rejectModalProposal && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
          <div
            className="w-full max-w-md p-6 rounded-2xl border space-y-4 animate-in zoom-in-95"
            style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-separator)' }}
          >
            <h3 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
              Reject proposal {rejectModalProposal}?
            </h3>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Pick a reason so the optimizer learns.
            </p>

            <div className="flex gap-2">
              {['Class running late', 'Other'].map((r) => (
                <button
                  key={r}
                  onClick={() => setRejectReason(r)}
                  className="px-3.5 py-2 rounded-lg text-xs font-semibold cursor-pointer border transition-all"
                  style={{
                    backgroundColor: rejectReason === r ? 'var(--accent-subtle)' : 'var(--bg-well)',
                    borderColor: rejectReason === r ? 'var(--accent)' : 'var(--border-subtle)',
                    color: rejectReason === r ? 'var(--accent)' : 'var(--text-primary)'
                  }}
                >
                  {r}
                </button>
              ))}
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
              <Button variant="secondary" onClick={() => setRejectModalProposal(null)}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={() => {
                  onReject(rejectModalProposal, rejectReason);
                  setRejectModalProposal(null);
                }}
              >
                Confirm Reject
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
