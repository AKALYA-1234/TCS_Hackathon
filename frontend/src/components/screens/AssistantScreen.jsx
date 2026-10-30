import React, { useState } from 'react';
import { Bot, Send, ShieldCheck, ChevronDown, ChevronUp, ArrowRight, Sparkles } from 'lucide-react';
import { Button } from '../ui/BaseComponents';

export function AssistantScreen({
  onOpenProposal,
  onPromptSelect
}) {
  const [messages, setMessages] = useState([
    {
      id: 1,
      sender: 'user',
      text: 'Why is Lab 204 the top waste room today?'
    },
    {
      id: 2,
      sender: 'assistant',
      text: 'Lab 204 has wasted 22 kWh (₹227) today, about 41% of its energy, in three separate episodes: an early start at 07:10, overcooling from 10:40 to 12:00 with the setpoint at 18 °C, and ghost cooling since 13:05 with nobody inside. The ghost cooling is the one still running. Both units draw 3.7 kW against 0–0.4 kW expected. I drafted proposal P-1041 to put the room on standby when it is empty.',
      dataUsed: [
        { query: 'get_waste_events(room="Lab 204", range="today")', result: 'Returned: 3 events · 22 kWh · ₹227' },
        { query: 'get_baseline(room="Lab 204", from="06:00")', result: 'Returned: expected 0–0.4 kW after 13:30, actual 3.7 kW' },
        { query: 'get_timetable(room="Lab 204", day="Thursday")', result: 'Returned: last class ended 13:00, none until Friday 09:00' }
      ],
      proposal: {
        id: 'P-1041',
        title: 'Put Lab 204 on standby when it is empty',
        savings: '₹6.9k – ₹8.3k per month',
        status: 'Needs approval',
        rules: '5 of 5 rules passed'
      }
    }
  ]);

  const [inputVal, setInputVal] = useState('');
  const [dataUsedOpen, setDataUsedOpen] = useState(true);

  const promptSuggestions = [
    'Which rooms waste the most?',
    'What would a 24 °C setpoint save in the Board Room?',
    'Why did Lab 204 spike at 13:05?',
    'Summarise today for the principal'
  ];

  const handleSend = (textToSend) => {
    const q = textToSend || inputVal;
    if (!q.trim()) return;

    const newMsg = { id: Date.now(), sender: 'user', text: q };
    setMessages(prev => [...prev, newMsg]);
    setInputVal('');

    // Simulated Copilot response matching reference
    setTimeout(() => {
      setMessages(prev => [
        ...prev,
        {
          id: Date.now() + 1,
          sender: 'assistant',
          text: `Analysis for "${q}": Based on live telemetry, Academic Block A and Lab 204 represent 68% of today's recoverable waste. Modifying setpoint schedules from 22 °C to 24 °C will yield ₹14,200 monthly reduction with zero comfort violations.`,
          dataUsed: [
            { query: `query_telemetry(metric="all", context="${q}")`, result: 'Returned: 16 rooms · 42 events' }
          ]
        }
      ]);
    }, 600);
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300 max-w-5xl mx-auto">
      {/* 1. Header */}
      <div>
        <h1 className="text-3xl md:text-4xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
          Assistant
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
          Ask about energy, waste events, forecasts and proposals.
        </p>

        {/* Governance banner matching reference design */}
        <div
          className="mt-4 p-4 rounded-2xl flex items-start gap-3 border"
          style={{
            backgroundColor: 'var(--bg-well)',
            borderColor: 'var(--border-subtle)'
          }}
        >
          <div
            className="w-5 h-5 rounded-full flex items-center justify-center shrink-0 mt-0.5"
            style={{ backgroundColor: 'var(--accent-subtle)', color: 'var(--accent)' }}
          >
            <ShieldCheck size={14} />
          </div>
          <div className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            <strong style={{ color: 'var(--text-primary)' }}>The assistant proposes. It never acts on its own.</strong> Any change it suggests lands in the Approvals inbox, passes the rule engine, and waits for a person to approve it.
          </div>
        </div>
      </div>

      {/* 2. Chat Stream Box */}
      <div
        className="p-6 rounded-2xl border min-h-[460px] flex flex-col justify-between space-y-6"
        style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
      >
        <div className="space-y-6">
          {messages.map((m) => (
            <div key={m.id} className="space-y-4">
              {m.sender === 'user' ? (
                <div className="flex justify-end">
                  <div
                    className="max-w-xl px-5 py-3 rounded-2xl rounded-tr-sm text-sm font-medium shadow-xs"
                    style={{ backgroundColor: 'var(--accent)', color: '#FFFFFF' }}
                  >
                    {m.text}
                  </div>
                </div>
              ) : (
                <div className="flex items-start gap-3">
                  <div
                    className="w-8 h-8 rounded-xl flex items-center justify-center font-bold text-sm shrink-0 mt-1 select-none"
                    style={{ backgroundColor: 'var(--accent)', color: '#FFFFFF' }}
                  >
                    ❄
                  </div>

                  <div className="flex-1 space-y-4 max-w-3xl">
                    <p className="text-sm leading-relaxed" style={{ color: 'var(--text-primary)' }}>
                      {m.text}
                    </p>

                    {/* Data Used Accordion (Transparency) */}
                    {m.dataUsed && (
                      <div
                        className="rounded-xl border overflow-hidden"
                        style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}
                      >
                        <button
                          onClick={() => setDataUsedOpen(!dataUsedOpen)}
                          className="w-full px-4 py-2.5 flex items-center justify-between text-xs font-semibold cursor-pointer"
                          style={{ color: 'var(--text-secondary)' }}
                        >
                          <div className="flex items-center gap-2">
                            <span>🗄</span>
                            <span>Data used · {m.dataUsed.length} lookups</span>
                          </div>
                          {dataUsedOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        </button>

                        {dataUsedOpen && (
                          <div className="px-4 pb-3 pt-1 border-t space-y-2 text-xs font-mono" style={{ borderColor: 'var(--border-subtle)' }}>
                            {m.dataUsed.map((d, i) => (
                              <div key={i} className="space-y-0.5">
                                <div style={{ color: 'var(--accent)' }}>{d.query}</div>
                                <div style={{ color: 'var(--text-tertiary)' }}>{d.result}</div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Inline Proposal Card linking to Approvals */}
                    {m.proposal && (
                      <div
                        className="p-4 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                        style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-mono font-bold" style={{ color: 'var(--text-tertiary)' }}>
                              {m.proposal.id}
                            </span>
                            <span
                              className="px-2 py-0.5 rounded text-[11px] font-semibold"
                              style={{ backgroundColor: 'var(--status-review-bg)', color: 'var(--status-review)' }}
                            >
                              {m.proposal.status}
                            </span>
                          </div>
                          <div className="font-bold text-sm" style={{ color: 'var(--text-primary)' }}>
                            {m.proposal.title}
                          </div>
                          <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                            {m.proposal.savings} · {m.proposal.rules}
                          </div>
                        </div>

                        <Button
                          variant="secondary"
                          onClick={() => onOpenProposal && onOpenProposal(m.proposal.id)}
                        >
                          Open in Approvals
                        </Button>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Bottom Input Area */}
        <div className="space-y-3 pt-4 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
          {/* Prompt Suggestions */}
          <div className="flex items-center gap-2 flex-wrap">
            {promptSuggestions.map((prompt) => (
              <button
                key={prompt}
                onClick={() => handleSend(prompt)}
                className="px-3 py-1.5 rounded-full text-xs font-medium border cursor-pointer transition-all hover:bg-slate-500/10"
                style={{
                  backgroundColor: 'var(--bg-card)',
                  borderColor: 'var(--border-subtle)',
                  color: 'var(--text-primary)'
                }}
              >
                {prompt}
              </button>
            ))}
          </div>

          {/* Chat Form */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              placeholder="Ask about a room, a cost or a proposal"
              className="flex-1 px-4 py-2.5 rounded-full border text-sm focus:outline-none transition-colors"
              style={{
                backgroundColor: 'var(--bg-well)',
                borderColor: 'var(--border-subtle)',
                color: 'var(--text-primary)'
              }}
            />
            <button
              type="submit"
              className="w-10 h-10 rounded-full flex items-center justify-center font-bold text-white transition-opacity cursor-pointer disabled:opacity-50"
              style={{ backgroundColor: 'var(--accent)' }}
              disabled={!inputVal.trim()}
            >
              <ArrowRight size={18} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
