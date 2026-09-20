// WaterCare AI - Administrator Console Controller
document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const statTotal = document.getElementById('stat-total');
  const statActive = document.getElementById('stat-active');
  const statEscalated = document.getElementById('stat-escalated');
  const statResolved = document.getElementById('stat-resolved');
  const complaintsTbody = document.getElementById('complaints-tbody');
  const btnRefreshAll = document.getElementById('btn-refresh-all');
  const agentModeText = document.getElementById('agent-mode-text');

  // Modals & Triggers
  const btnOpenWorkflow = document.getElementById('btn-open-workflow');
  const modalWorkflow = document.getElementById('modal-workflow');
  const closeWorkflowBtn = document.getElementById('close-workflow-btn');
  const workflowStepsBody = document.getElementById('workflow-steps-body');
  const workflowMeta = document.getElementById('workflow-meta');

  const modalConfirm = document.getElementById('modal-confirm');
  const confirmPromptText = document.getElementById('confirm-prompt-text');
  const btnCancelClear = document.getElementById('btn-cancel-clear');
  const btnConfirmClear = document.getElementById('btn-confirm-clear');

  const modalAudit = document.getElementById('modal-audit');
  const closeAuditBtn = document.getElementById('close-audit-btn');
  const auditModalTitle = document.getElementById('audit-modal-title');
  const auditModalBody = document.getElementById('audit-modal-body');

  let ticketToClear = null;

  // Initialize
  fetchHealth();
  fetchStats();
  fetchActiveComplaints();

  // Auto-refresh active complaints every 3 seconds
  setInterval(() => {
    fetchActiveComplaints();
    fetchStats();
  }, 3000);

  // 1. Health & Mode Check
  async function fetchHealth() {
    try {
      const res = await fetch('/api/health');
      const data = await res.json();
      agentModeText.textContent = data.gemini_api_configured ? 'Gemini LLM Active' : 'Agentic Engine: Online';
    } catch (e) {
      agentModeText.textContent = 'Server Offline';
    }
  }

  // 2. Fetch Stats
  async function fetchStats() {
    try {
      const res = await fetch('/api/stats');
      const data = await res.json();
      statTotal.textContent = data.total_complaints || 0;
      statActive.textContent = data.active_complaints || 0;
      statEscalated.textContent = data.escalated_complaints || 0;
      statResolved.textContent = data.resolved_complaints || 0;
    } catch (err) {
      console.error('Stats fetch failed:', err);
    }
  }

  // 3. Fetch Active Complaints
  async function fetchActiveComplaints() {
    try {
      const res = await fetch('/api/complaints/active');
      const data = await res.json();
      const complaints = data.complaints || [];

      if (complaints.length === 0) {
        complaintsTbody.innerHTML = `
          <tr>
            <td colspan="7">
              <div class="empty-log">
                <div class="empty-log-icon">📋</div>
                <div class="empty-log-text">No active complaints yet.</div>
              </div>
            </td>
          </tr>
        `;
        return;
      }

      complaintsTbody.innerHTML = complaints.map(c => `
        <tr>
          <td><span class="ticket-code">${c.ticket_id}</span></td>
          <td><strong>${c.location}</strong></td>
          <td>${c.category}</td>
          <td><span class="badge-priority ${c.priority}">${c.priority}</span></td>
          <td><span class="badge-status ${c.status}">${c.status}</span></td>
          <td style="font-size:0.75rem; color:#94a3b8;">${c.created_at}</td>
          <td>
            <button class="btn-action-view" onclick="openAuditModal('${c.ticket_id}')">View</button>
            <button class="btn-action-resolve" onclick="promptClearComplaint('${c.ticket_id}')">Resolve / Clear</button>
          </td>
        </tr>
      `).join('');

    } catch (err) {
      console.error('Complaints fetch failed:', err);
    }
  }

  btnRefreshAll.addEventListener('click', () => {
    fetchStats();
    fetchActiveComplaints();
  });

  // 4. Resolve / Clear Complaint Feature
  window.promptClearComplaint = function(ticketId) {
    ticketToClear = ticketId;
    confirmPromptText.textContent = `Are you sure you want to resolve this complaint (${ticketId})?`;
    modalConfirm.style.display = 'flex';
  };

  btnCancelClear.addEventListener('click', () => {
    modalConfirm.style.display = 'none';
    ticketToClear = null;
  });

  btnConfirmClear.addEventListener('click', async () => {
    if (!ticketToClear) return;
    const ticketId = ticketToClear;
    btnConfirmClear.disabled = true;
    btnConfirmClear.textContent = 'Resolving...';

    try {
      const res = await fetch(`/api/complaints/${ticketId}/resolve`, {
        method: 'POST'
      });

      if (!res.ok) throw new Error('Failed to resolve complaint');

      modalConfirm.style.display = 'none';
      ticketToClear = null;

      // Refresh immediately
      fetchStats();
      fetchActiveComplaints();
    } catch (err) {
      alert('Error resolving complaint: ' + err.message);
    } finally {
      btnConfirmClear.disabled = false;
      btnConfirmClear.textContent = 'Yes, Resolve Complaint';
    }
  });

  // 5. Agent Workflow Modal (Hidden by Default)
  btnOpenWorkflow.addEventListener('click', async () => {
    modalWorkflow.style.display = 'flex';
    workflowStepsBody.innerHTML = '<p style="text-align:center; color:#94a3b8; padding:30px;">Loading agent workflow...</p>';

    try {
      const res = await fetch('/api/agent/latest-workflow');
      const data = await res.json();

      if (!data.has_run || !data.steps || data.steps.length === 0) {
        workflowMeta.textContent = 'No executions recorded in this session';
        workflowStepsBody.innerHTML = `
          <div class="empty-log">
            <div class="empty-log-icon">⚙️</div>
            <div class="empty-log-text">No agent workflow has run yet. Submit a complaint from the Citizen Portal to view the multi-step agent reasoning cycle.</div>
          </div>
        `;
        return;
      }

      workflowMeta.textContent = `Triggered at ${data.timestamp} | Mode: ${data.agent_mode}`;

      let ticketSummaryHtml = '';
      if (data.ticket) {
        ticketSummaryHtml = `
          <div style="background:rgba(2,132,199,0.15); border:1px solid #38bdf8; border-radius:8px; padding:12px; margin-bottom:12px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <strong style="color:#fff;">Registered Ticket: <span style="color:#38bdf8;">${data.ticket.ticket_id}</span></strong>
              <span class="badge-priority ${data.ticket.priority}">${data.ticket.priority} PRIORITY</span>
            </div>
            <div style="font-size:0.78rem; color:#cbd5e1; margin-top:4px;">
              ${data.ticket.category} • ${data.ticket.location} • Status: ${data.ticket.status}
            </div>
          </div>
        `;
      }

      const stepsHtml = data.steps.map((step, idx) => {
        let devDetailsHtml = '';
        if (step.data && Object.keys(step.data).length > 0) {
          devDetailsHtml = `
            <details class="dev-details-toggle">
              <summary>Developer Details</summary>
              <pre>${escapeHtml(JSON.stringify(step.data, null, 2))}</pre>
            </details>
          `;
        }

        return `
          <div class="step-item type-${step.step_type}">
            <div class="step-header-row">
              <span class="step-badge">${step.step_type}</span>
              <span class="step-time">${step.timestamp || ''}</span>
            </div>
            <div class="step-heading">${idx + 1}. ${escapeHtml(step.title)}</div>
            <div class="step-narrative">${escapeHtml(step.description)}</div>
            ${devDetailsHtml}
          </div>
        `;
      }).join('');

      workflowStepsBody.innerHTML = ticketSummaryHtml + stepsHtml;

    } catch (err) {
      workflowStepsBody.innerHTML = `<p style="color:#ef4444; padding:20px;">Error retrieving workflow: ${err.message}</p>`;
    }
  });

  closeWorkflowBtn.addEventListener('click', () => {
    modalWorkflow.style.display = 'none';
  });

  // 6. View Complaint Details & Audit Modal
  window.openAuditModal = async function(ticketId) {
    modalAudit.style.display = 'flex';
    auditModalTitle.textContent = `Complaint Details: ${ticketId}`;
    auditModalBody.innerHTML = '<p style="color:#94a3b8; text-align:center;">Loading details...</p>';

    try {
      const res = await fetch(`/api/complaints/${ticketId}`);
      if (!res.ok) throw new Error('Complaint not found');
      const data = await res.json();
      const comp = data.complaint;
      const updates = data.updates || [];

      const updatesHtml = updates.map(u => `
        <div style="border-left:2px solid #38bdf8; padding-left:14px; margin-bottom:12px; position:relative;">
          <div style="display:flex; justify-content:space-between; font-size:0.75rem;">
            <strong style="color:#fff;">${u.action}</strong>
            <span style="color:#94a3b8;">${u.timestamp}</span>
          </div>
          <div style="font-size:0.72rem; color:#38bdf8; margin-bottom:4px;">Action by: ${u.performed_by}</div>
          <div style="font-size:0.8rem; color:#cbd5e1;">${escapeHtml(u.notes)}</div>
        </div>
      `).join('');

      auditModalBody.innerHTML = `
        <div style="background:#080e1c; border:1px solid #1e3258; border-radius:6px; padding:12px; margin-bottom:14px; font-size:0.82rem;">
          <div style="margin-bottom:4px;"><strong>Ticket ID:</strong> <span style="color:#38bdf8;">${comp.ticket_id}</span> | <strong>Status:</strong> ${comp.status}</div>
          <div style="margin-bottom:4px;"><strong>Location / Ward:</strong> ${comp.location} | <strong>Priority:</strong> ${comp.priority}</div>
          <div style="margin-bottom:4px;"><strong>Category:</strong> ${comp.category}</div>
          <div style="margin-top:6px; color:#cbd5e1; background:rgba(255,255,255,0.04); padding:8px; border-radius:4px;">"${escapeHtml(comp.description)}"</div>
        </div>
        <h4 style="font-size:0.86rem; margin-bottom:10px; color:#fff;">Status & Action History:</h4>
        ${updatesHtml || '<p style="color:#94a3b8;">No update records found.</p>'}
      `;

    } catch (err) {
      auditModalBody.innerHTML = `<p style="color:#ef4444;">Error loading details: ${err.message}</p>`;
    }
  };

  closeAuditBtn.addEventListener('click', () => {
    modalAudit.style.display = 'none';
  });

  // Close modals on clicking backdrop
  [modalWorkflow, modalConfirm, modalAudit].forEach(modal => {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.style.display = 'none';
    });
  });

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
});
