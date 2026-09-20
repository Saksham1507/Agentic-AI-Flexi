// WaterCare AI - Frontend Interactive Controller
document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const chatForm = document.getElementById('chat-form');
  const userInput = document.getElementById('user-input');
  const sendBtn = document.getElementById('send-btn');
  const chatStream = document.getElementById('chat-stream');
  const clearChatBtn = document.getElementById('clear-chat-btn');
  const stepsTimeline = document.getElementById('steps-timeline');
  const ticketContainer = document.getElementById('ticket-container');
  const ticketCard = document.getElementById('ticket-card');
  const cardStatus = document.getElementById('card-status');
  const agentModeBadge = document.getElementById('agent-mode-badge');
  const agentStatus = document.getElementById('agent-status');

  // Stats elements
  const statTotal = document.getElementById('stat-total');
  const statEscalated = document.getElementById('stat-escalated');
  const statDisrupted = document.getElementById('stat-disrupted');

  // Tabs elements
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');
  const complaintsTbody = document.getElementById('complaints-tbody');
  const filterWard = document.getElementById('filter-ward');
  const refreshComplaintsBtn = document.getElementById('refresh-complaints-btn');
  const wardGrid = document.getElementById('ward-grid');
  const refreshAreasBtn = document.getElementById('refresh-areas-btn');

  // Tool Tester elements
  const toolSelect = document.getElementById('tool-select');
  const toolArgs = document.getElementById('tool-args');
  const runToolBtn = document.getElementById('run-tool-btn');
  const toolResultBox = document.getElementById('tool-result-box');
  const toolResultCode = document.getElementById('tool-result-code');

  // Modal elements
  const modal = document.getElementById('ticket-modal');
  const modalCloseBtn = document.getElementById('modal-close-btn');
  const modalTitle = document.getElementById('modal-title');
  const modalBody = document.getElementById('modal-body');

  // Conversation history in memory
  let conversationHistory = [];

  // 1. Initialize data
  fetchHealth();
  fetchStats();
  fetchComplaints();
  fetchAreas();

  // 2. Chat Form Submission
  chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = userInput.value.trim();
    if (!message) return;

    // Append citizen message
    appendMessage('user', message);
    userInput.value = '';
    sendBtn.disabled = true;

    // Show loading step indicator in agent panel
    showAgentThinking();

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: message,
          history: conversationHistory
        })
      });

      if (!res.ok) {
        throw new Error(`Server returned status ${res.status}`);
      }

      const data = await res.json();

      // Record in conversation history
      conversationHistory.push({ role: 'user', content: message });
      conversationHistory.push({ role: 'assistant', content: data.response });

      // Update agent mode badge
      if (data.agent_mode) {
        agentModeBadge.textContent = data.agent_mode;
      }

      // Render agent steps in timeline
      renderAgentSteps(data.steps || []);

      // Append agent message in chat
      appendMessage('agent', data.response);

      // If ticket was generated, render ticket card
      if (data.ticket) {
        renderTicketCard(data.ticket);
      }

      // Refresh stats & complaints list
      fetchStats();
      fetchComplaints();
      fetchAreas();

    } catch (err) {
      console.error('Chat error:', err);
      appendMessage('agent', `⚠️ **Error communicating with WaterCare Agent:** ${err.message}. Please check that backend server is running.`);
      renderErrorStep(err.message);
    } finally {
      sendBtn.disabled = false;
      userInput.focus();
    }
  });

  // 3. Demo Scenario Chips
  document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      userInput.value = chip.getAttribute('data-query');
      chatForm.dispatchEvent(new Event('submit'));
    });
  });

  // 4. Clear Chat
  clearChatBtn.addEventListener('click', () => {
    conversationHistory = [];
    chatStream.innerHTML = `
      <div class="message agent-message">
        <div class="msg-avatar">🤖</div>
        <div class="msg-bubble">
          <p><strong>Chat session reset.</strong> You can enter a new complaint or click one of the quick test chips above.</p>
        </div>
      </div>
    `;
    stepsTimeline.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">⚙️</div>
        <p>Agent reasoning & tool execution steps will appear here in real-time when you submit a complaint.</p>
      </div>
    `;
    ticketContainer.style.display = 'none';
  });

  // 5. Append message bubble helper
  function appendMessage(role, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role === 'user' ? 'user-message' : 'agent-message'}`;

    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'msg-avatar';
    avatarDiv.textContent = role === 'user' ? '👤' : '🤖';

    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = 'msg-bubble';
    bubbleDiv.innerHTML = formatMarkdown(text);

    msgDiv.appendChild(avatarDiv);
    msgDiv.appendChild(bubbleDiv);

    chatStream.appendChild(msgDiv);
    chatStream.scrollTop = chatStream.scrollHeight;
  }

  // Basic Markdown formatter (bold, code, bullet points, headers)
  function formatMarkdown(text) {
    if (!text) return '';
    let html = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\n\n/g, '</p><p>')
      .replace(/\n- (.*?)(?=\n|$)/g, '<br>• $1')
      .replace(/\n/g, '<br>');
    return `<p>${html}</p>`;
  }

  // 6. Render Agent Steps in Timeline
  function renderAgentSteps(steps) {
    if (!steps || steps.length === 0) {
      stepsTimeline.innerHTML = `<div class="empty-state"><p>No intermediate steps recorded.</p></div>`;
      return;
    }

    stepsTimeline.innerHTML = '';

    steps.forEach((step, idx) => {
      const card = document.createElement('div');
      card.className = `step-card type-${step.step_type}`;

      let dataPreviewHtml = '';
      if (step.data && Object.keys(step.data).length > 0) {
        dataPreviewHtml = `
          <div class="step-data-preview">
            <pre>${escapeHtml(JSON.stringify(step.data, null, 2))}</pre>
          </div>
        `;
      }

      card.innerHTML = `
        <div class="step-top">
          <span class="step-tag">${step.step_type}</span>
          <span class="step-time">${step.timestamp || ''}</span>
        </div>
        <div class="step-title">${idx + 1}. ${escapeHtml(step.title)}</div>
        <div class="step-desc">${escapeHtml(step.description)}</div>
        ${dataPreviewHtml}
      `;

      stepsTimeline.appendChild(card);
    });

    stepsTimeline.scrollTop = stepsTimeline.scrollHeight;
  }

  function showAgentThinking() {
    stepsTimeline.innerHTML = `
      <div class="step-card type-UNDERSTAND">
        <div class="step-top">
          <span class="step-tag">PROCESSING</span>
          <span class="step-time">Now</span>
        </div>
        <div class="step-title">Agentic Workflow Initiated...</div>
        <div class="step-desc">Analyzing text, parsing intent, checking Ward telemetry, and querying database tools...</div>
      </div>
    `;
  }

  function renderErrorStep(msg) {
    stepsTimeline.innerHTML = `
      <div class="step-card type-ESCALATE">
        <div class="step-top">
          <span class="step-tag">ERROR</span>
          <span class="step-time">Now</span>
        </div>
        <div class="step-title">Agent Execution Failed</div>
        <div class="step-desc">${escapeHtml(msg)}</div>
      </div>
    `;
  }

  // 7. Render Generated Ticket Card
  function renderTicketCard(ticket) {
    if (!ticket) return;

    ticketContainer.style.display = 'block';
    cardStatus.textContent = ticket.status;
    cardStatus.className = `status-badge ${ticket.status}`;

    ticketCard.innerHTML = `
      <div class="ticket-header-row">
        <div>
          <span class="ticket-id">${ticket.ticket_id}</span>
        </div>
        <div>
          <span class="priority-tag ${ticket.priority}">${ticket.priority} PRIORITY</span>
        </div>
      </div>

      <div class="ticket-grid">
        <div class="ticket-field">
          <span class="field-label">Location / Ward</span>
          <span class="field-value">${ticket.location}</span>
        </div>
        <div class="ticket-field">
          <span class="field-label">Category</span>
          <span class="field-value">${ticket.category}</span>
        </div>
        <div class="ticket-field">
          <span class="field-label">Reported Duration</span>
          <span class="field-value">${ticket.duration || 'Unspecified'}</span>
        </div>
        <div class="ticket-field">
          <span class="field-label">Registered At</span>
          <span class="field-value">${ticket.created_at}</span>
        </div>
      </div>

      <div style="margin-top: 10px; font-size: 0.76rem; color: #94a3b8; border-top: 1px solid rgba(56,189,248,0.2); padding-top: 8px;">
        <strong>Description:</strong> ${escapeHtml(ticket.description)}
      </div>
    `;
  }

  // 8. Tabs Switching
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      tabContents.forEach(c => c.classList.remove('active'));

      btn.classList.add('active');
      const tabId = btn.getAttribute('data-tab');
      document.getElementById(tabId).classList.add('active');
    });
  });

  // 9. Fetch Complaints List
  async function fetchComplaints() {
    try {
      const wardQuery = filterWard.value.trim();
      const url = wardQuery ? `/api/complaints?ward=${encodeURIComponent(wardQuery)}` : '/api/complaints';
      const res = await fetch(url);
      const data = await res.json();
      const complaints = data.complaints || [];

      if (complaints.length === 0) {
        complaintsTbody.innerHTML = `<tr><td colspan="6" class="text-center">No complaints found.</td></tr>`;
        return;
      }

      complaintsTbody.innerHTML = complaints.map(c => `
        <tr>
          <td><span class="code-badge">${c.ticket_id}</span></td>
          <td>${c.location}</td>
          <td>${c.category}</td>
          <td><span class="priority-tag ${c.priority}">${c.priority}</span></td>
          <td><span class="status-badge ${c.status}">${c.status}</span></td>
          <td>
            <button class="btn-outline btn-sm" onclick="openTicketModal('${c.ticket_id}')">Audit Trail</button>
          </td>
        </tr>
      `).join('');
    } catch (err) {
      console.error('Failed to load complaints:', err);
    }
  }

  refreshComplaintsBtn.addEventListener('click', fetchComplaints);
  filterWard.addEventListener('input', debounce(fetchComplaints, 300));

  // 10. Fetch Ward Areas
  async function fetchAreas() {
    try {
      const res = await fetch('/api/areas');
      const data = await res.json();
      const areas = data.areas || [];

      wardGrid.innerHTML = areas.map(a => `
        <div class="ward-card">
          <div class="ward-card-header">
            <span class="ward-name">${a.name}</span>
            <span class="ward-status-tag ${a.status}">${a.status}</span>
          </div>
          <div class="reservoir-bar-wrap">
            <div class="reservoir-labels">
              <span>Reservoir Level</span>
              <span>${a.reservoir_level_pct}%</span>
            </div>
            <div class="reservoir-bar">
              <div class="reservoir-fill" style="width: ${a.reservoir_level_pct}%"></div>
            </div>
          </div>
          <div class="ward-detail-text">
            <strong>Officer:</strong> ${a.contact_officer} (📞 ${a.contact_phone})
          </div>
          ${a.maintenance_scheduled && a.maintenance_scheduled !== 'None' ? `
            <div class="ward-detail-text" style="color: #f59e0b;">
              <strong>Maintenance:</strong> ${a.maintenance_scheduled}
            </div>
          ` : ''}
        </div>
      `).join('');
    } catch (err) {
      console.error('Failed to load areas:', err);
    }
  }

  refreshAreasBtn.addEventListener('click', fetchAreas);

  // 11. Fetch System Health & Stats
  async function fetchHealth() {
    try {
      const res = await fetch('/api/health');
      const data = await res.json();
      if (data.gemini_api_configured) {
        agentStatus.textContent = 'Gemini LLM Active';
        agentStatus.className = 'stat-val';
      } else {
        agentStatus.textContent = 'Local Agentic Engine';
      }
    } catch (err) {
      agentStatus.textContent = 'Offline';
    }
  }

  async function fetchStats() {
    try {
      const res = await fetch('/api/stats');
      const data = await res.json();
      statTotal.textContent = data.total_complaints || 0;
      statEscalated.textContent = data.escalated || 0;
      statDisrupted.textContent = data.disrupted_areas || 0;
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  }

  // 12. Direct Tool Execution Tester
  const toolArgSamples = {
    check_area_status: '{"location": "Ward 5"}',
    search_existing_complaints: '{"location": "Ward 5", "category": "No Water Supply"}',
    create_complaint: '{"description": "Water pipe leak on main road", "location": "Ward 2", "category": "Pipeline Leakage", "priority": "HIGH"}',
    update_complaint: '{"ticket_id": "TKT-2026-1001", "status": "IN_PROGRESS", "notes": "Technician dispatched to inspect main valve"}',
    escalate_complaint: '{"ticket_id": "TKT-2026-1001", "reason": "Citizen reported water discoloration and bad smell"}'
  };

  toolSelect.addEventListener('change', () => {
    toolArgs.value = toolArgSamples[toolSelect.value] || '{}';
  });

  runToolBtn.addEventListener('click', async () => {
    const toolName = toolSelect.value;
    let parsedArgs = {};
    try {
      parsedArgs = JSON.parse(toolArgs.value);
    } catch (err) {
      alert('Invalid JSON in arguments field!');
      return;
    }

    runToolBtn.disabled = true;
    runToolBtn.textContent = 'Executing...';

    try {
      const res = await fetch('/api/tools/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tool_name: toolName,
          arguments: parsedArgs
        })
      });
      const data = await res.json();
      toolResultBox.style.display = 'block';
      toolResultCode.textContent = JSON.stringify(data, null, 2);

      // Refresh lists if tool modified data
      fetchStats();
      fetchComplaints();
      fetchAreas();
    } catch (err) {
      toolResultBox.style.display = 'block';
      toolResultCode.textContent = 'Error: ' + err.message;
    } finally {
      runToolBtn.disabled = false;
      runToolBtn.textContent = 'Execute Tool';
    }
  });

  // 13. Audit Trail Modal
  window.openTicketModal = async function(ticketId) {
    modal.style.display = 'flex';
    modalTitle.textContent = `Ticket Audit Trail: ${ticketId}`;
    modalBody.innerHTML = '<p>Loading audit timeline...</p>';

    try {
      const res = await fetch(`/api/complaints/${ticketId}`);
      if (!res.ok) throw new Error('Complaint not found');
      const data = await res.json();
      const comp = data.complaint;
      const updates = data.updates || [];

      let updatesHtml = updates.map(u => `
        <div class="audit-entry">
          <div class="audit-action">${u.action} <span style="font-size:0.7rem; color:#94a3b8;">(${u.performed_by})</span></div>
          <div class="audit-time">${u.timestamp}</div>
          <div class="audit-notes">${escapeHtml(u.notes)}</div>
        </div>
      `).join('');

      modalBody.innerHTML = `
        <div style="background: #17233f; padding: 12px; border-radius: 8px; margin-bottom: 16px;">
          <div style="display:flex; justify-content:space-between; margin-bottom: 6px;">
            <strong style="color:#38bdf8;">${comp.ticket_id}</strong>
            <span class="status-badge ${comp.status}">${comp.status}</span>
          </div>
          <div><strong>Category:</strong> ${comp.category} | <strong>Ward:</strong> ${comp.location} | <strong>Priority:</strong> ${comp.priority}</div>
          <div style="margin-top: 6px; color:#cbd5e1;"><em>"${escapeHtml(comp.description)}"</em></div>
        </div>
        <h4 style="margin-bottom: 12px; font-size: 0.85rem; color:#f8fafc;">Official Action History:</h4>
        ${updatesHtml || '<p>No update records logged.</p>'}
      `;
    } catch (err) {
      modalBody.innerHTML = `<p style="color:#ef4444;">Error loading ticket: ${err.message}</p>`;
    }
  };

  modalCloseBtn.addEventListener('click', () => {
    modal.style.display = 'none';
  });

  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.style.display = 'none';
  });

  // Utility helpers
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function debounce(fn, ms) {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), ms);
    };
  }
});
