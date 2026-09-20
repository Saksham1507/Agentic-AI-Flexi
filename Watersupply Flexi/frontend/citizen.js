// WaterCare AI - Citizen Portal Interactive Controller
document.addEventListener('DOMContentLoaded', () => {
  const citizenForm = document.getElementById('citizen-form');
  const citizenInput = document.getElementById('citizen-input');
  const submitBtn = document.getElementById('submit-btn');
  const chatMessages = document.getElementById('chat-messages');
  const resetChatBtn = document.getElementById('reset-chat-btn');

  // Ticket Card elements
  const ticketCard = document.getElementById('ticket-card');
  const cardTicketId = document.getElementById('card-ticket-id');
  const cardCategory = document.getElementById('card-category');
  const cardLocation = document.getElementById('card-location');
  const cardPriority = document.getElementById('card-priority');
  const cardStatus = document.getElementById('card-status');
  const cardOfficerText = document.getElementById('card-officer-text');

  let conversationHistory = [];
  let currentActiveTicketId = null;
  let statusPollInterval = null;

  // 1. Example Suggestions Click-to-Fill (Does NOT auto-submit!)
  document.querySelectorAll('.example-card').forEach(card => {
    card.addEventListener('click', () => {
      const text = card.getAttribute('data-text');
      if (text) {
        citizenInput.value = text;
        citizenInput.focus();
        // Visual feedback on card
        card.style.borderColor = '#0284c7';
        setTimeout(() => { card.style.borderColor = ''; }, 300);
      }
    });
  });

  // 2. Handle citizen complaint submission
  citizenForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = citizenInput.value.trim();
    if (!text) return;

    // Clear any previous ticket card and stop previous resolution poll immediately.
    // This ensures stale data from the last complaint is never shown for the new one.
    if (statusPollInterval) {
      clearInterval(statusPollInterval);
      statusPollInterval = null;
    }
    ticketCard.style.display = 'none';
    currentActiveTicketId = null;

    // Append user message
    appendMessage('user', text);
    citizenInput.value = '';
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span>Processing...</span>`;

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          history: conversationHistory
        })
      });

      if (!res.ok) {
        throw new Error(`Server returned status ${res.status}`);
      }

      const data = await res.json();

      // Record in conversation history
      conversationHistory.push({ role: 'user', content: text });
      conversationHistory.push({ role: 'assistant', content: data.response });

      // Append assistant message
      appendMessage('agent', data.response);

      // If a ticket was created, update & reveal the Ticket Card
      if (data.ticket) {
        displayTicketCard(data.ticket);
        startTrackingResolution(data.ticket.ticket_id);
      }

    } catch (err) {
      console.error('Submission error:', err);
      appendMessage('agent', `⚠️ **Unable to connect to municipal server.** (${err.message}). Please check that backend server is running.`);
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = `
        <span>Submit Complaint</span>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
        </svg>
      `;
      citizenInput.focus();
    }
  });

  // 3. Display Ticket Card
  function displayTicketCard(ticket) {
    currentActiveTicketId = ticket.ticket_id;
    cardTicketId.textContent = ticket.ticket_id;
    cardCategory.textContent = ticket.category;
    cardLocation.textContent = ticket.location;

    // Priority badge
    cardPriority.textContent = ticket.priority;
    cardPriority.className = `priority-tag ${ticket.priority}`;

    // Status badge
    cardStatus.textContent = ticket.status;
    cardStatus.className = `status-tag ${ticket.status}`;

    // Officer
    if (ticket.contact_officer) {
      cardOfficerText.textContent = `Assigned Officer: ${ticket.contact_officer}`;
    }

    ticketCard.style.display = 'block';
  }

  // 4. Poll for ticket resolution from Admin Dashboard
  function startTrackingResolution(ticketId) {
    if (statusPollInterval) clearInterval(statusPollInterval);

    statusPollInterval = setInterval(async () => {
      try {
        const res = await fetch(`/api/complaints/${ticketId}/status-check`);
        if (!res.ok) return;
        const data = await res.json();

        if (data.is_resolved) {
          clearInterval(statusPollInterval);
          statusPollInterval = null;

          // Update card badge
          cardStatus.textContent = 'RESOLVED';
          cardStatus.className = 'status-tag RESOLVED';

          // Append prominent resolution message to chat
          appendResolutionAlert(ticketId);
        }
      } catch (err) {
        // Silent catch on poll
      }
    }, 2000); // Poll every 2 seconds
  }

  function appendResolutionAlert(ticketId) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message agent-message';

    msgDiv.innerHTML = `
      <div class="msg-icon" style="background:#dcfce7; color:#15803d;">✅</div>
      <div class="msg-bubble" style="background:#f0fdf4; border: 1.5px solid #86efac; color:#166534;">
        <p><strong>✅ Complaint Resolved!</strong></p>
        <p>Your complaint <strong>${ticketId}</strong> has been resolved by the Water Supply Department.</p>
        <p style="font-size:0.8rem; color:#15803d; margin-top:4px;">Thank you for helping us maintain municipal water supply services!</p>
      </div>
    `;

    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  // 5. Append regular message
  function appendMessage(role, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role === 'user' ? 'user-message' : 'agent-message'}`;

    const iconDiv = document.createElement('div');
    iconDiv.className = 'msg-icon';
    iconDiv.textContent = role === 'user' ? '👤' : '🤖';

    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = 'msg-bubble';
    bubbleDiv.innerHTML = formatMarkdown(text);

    msgDiv.appendChild(iconDiv);
    msgDiv.appendChild(bubbleDiv);

    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  // Basic markdown parser
  function formatMarkdown(text) {
    if (!text) return '';
    let html = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code style="background:#e2e8f0; padding:2px 5px; border-radius:4px; font-family:monospace;">$1</code>')
      .replace(/\n\n/g, '</p><p>')
      .replace(/\n- (.*?)(?=\n|$)/g, '<br>• $1')
      .replace(/\n/g, '<br>');
    return `<p>${html}</p>`;
  }

  // 6. Reset chat
  resetChatBtn.addEventListener('click', () => {
    conversationHistory = [];
    if (statusPollInterval) clearInterval(statusPollInterval);
    ticketCard.style.display = 'none';

    chatMessages.innerHTML = `
      <div class="message agent-message">
        <div class="msg-icon">🤖</div>
        <div class="msg-bubble">
          <p><strong>Fresh consultation started.</strong></p>
          <p>How can I assist you with your water supply today?</p>
        </div>
      </div>
    `;
    citizenInput.focus();
  });
});
