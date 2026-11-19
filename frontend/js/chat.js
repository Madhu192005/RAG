/**
 * WasteWise AI – chat.js (Grounded RAG Backend Integration)
 * ---------------------------------------------------------
 * Connects directly to POST /api/assistant/chat via WW_API.
 * Displays source-cited answers and keeps an authenticated conversation session.
 */

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("chatForm");
  const input = document.getElementById("chatInput");
  const container = document.getElementById("chatContainer");
  const clearBtn = document.getElementById("clearChatBtn");
  const chips = document.querySelectorAll(".suggest-chip");
  const citationsBody = document.getElementById("citationsBody");
  let sessionStorageKey = getSessionStorageKey();
  let sessionId = sessionStorage.getItem(sessionStorageKey);

  if (!form || !input || !container) return;

  // Handle submit
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = input.value.trim();
    if (!query) return;
    syncConversationSession();

    // 1. Append user message
    appendMessage("user", query);
    input.value = "";
    input.style.height = "48px";

    // 2. Add loading state indicator
    const loadingId = appendLoadingIndicator();

    try {
      // 3. Real call to FastAPI backend: POST /api/assistant/chat
      const result = await WW_API.chatAssistant(query, sessionId);
      if (result.session_id) {
        sessionId = result.session_id;
        sessionStorage.setItem(sessionStorageKey, sessionId);
      }
      removeLoadingIndicator(loadingId);
      appendAssistantResponse(result);

      // Render citations in sidebar if returned
      if (citationsBody && result.sources && result.sources.length > 0) {
        citationsBody.innerHTML = result.sources.map(s => `
          <div style="background:var(--clr-surface);border:1px solid var(--clr-border-lt);padding:10px;border-radius:6px;margin-bottom:8px;">
            <strong style="font-size:0.85rem;color:var(--clr-primary);">[${escapeHTML(s.citation_id)}] ${escapeHTML(s.title)}</strong>
            <p style="font-size:0.78rem;color:var(--clr-text-muted);margin:4px 0 0;">${escapeHTML(s.snippet)}</p>
          </div>
        `).join("");
      } else if (citationsBody) {
        citationsBody.innerHTML = `
          <div class="empty-state" style="padding:16px 0;">
            <h3 style="font-size:0.95rem;">No verified sources</h3>
            <p style="font-size:0.8rem;">No source passages were sufficient to answer this question.</p>
          </div>
        `;
      }
    } catch (error) {
      removeLoadingIndicator(loadingId);
      appendErrorResponse(query, error.message);
    }
  });

  // Handle Enter key for quick send
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.dispatchEvent(new Event("submit"));
    }
  });

  // Handle prompt suggestion chips
  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      input.value = chip.dataset.query || chip.textContent.trim();
      input.focus();
    });
  });

  // Handle Clear Chat
  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      sessionId = null;
      sessionStorage.removeItem(sessionStorageKey);
      container.innerHTML = `
        <div class="chat-msg assistant">
          <div>Chat history cleared.</div>
          <div style="margin-top:6px;font-size:0.85rem;color:var(--clr-text-muted);">
            Ready to receive new inquiries. A new conversation will be started on the next message.
          </div>
        </div>
      `;
      if (citationsBody) {
        citationsBody.innerHTML = `
          <div class="empty-state" style="padding:16px 0;">
            <div class="empty-icon" style="font-size:1.8rem;">📚</div>
            <h3 style="font-size:0.95rem;">No active sources</h3>
            <p style="font-size:0.8rem;">Verified source passages used in assistant answers will appear here.</p>
          </div>
        `;
      }
    });
  }

  function appendMessage(role, text) {
    const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const div = document.createElement("div");
    div.className = `chat-msg ${role}`;
    
    const p = document.createElement("p");
    p.textContent = text;
    p.style.margin = "0";

    const meta = document.createElement("div");
    meta.className = "msg-meta";
    meta.textContent = role === "user" ? `You · ${time}` : `Assistant · ${time}`;

    div.appendChild(p);
    div.appendChild(meta);
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
  }

  function getSessionStorageKey() {
    return `ww_assistant_session:${WW_API.getToken() || "guest"}`;
  }

  function syncConversationSession() {
    const activeKey = getSessionStorageKey();
    if (activeKey !== sessionStorageKey) {
      sessionStorageKey = activeKey;
      sessionId = sessionStorage.getItem(sessionStorageKey);
    }
  }

  function appendLoadingIndicator() {
    const id = "loading-" + Date.now();
    const div = document.createElement("div");
    div.id = id;
    div.className = "chat-msg assistant";
    div.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;">
        <span class="loading-spinner"></span>
        <span style="font-size:0.88rem;color:var(--clr-text-muted);">Querying FastAPI backend (/api/assistant/chat)…</span>
      </div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return id;
  }

  function removeLoadingIndicator(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  function appendAssistantResponse(result) {
    const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const div = document.createElement("div");
    div.className = "chat-msg assistant";

    const statusBadge = result.status === "insufficient_evidence"
      ? `<span class="badge badge-orange">Insufficient evidence</span>`
      : `<span class="badge badge-green">Grounded answer</span>`;
    const warnings = Array.isArray(result.warnings) && result.warnings.length
      ? result.warnings
      : (result.warning ? [result.warning] : []);

    div.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
        ${statusBadge}
        <span style="font-size:0.82rem;font-weight:600;color:var(--clr-text);">WasteWise AI</span>
      </div>
      <div style="font-size:0.92rem;line-height:1.55;">
        ${escapeHTML(result.answer)}
      </div>
      ${warnings.length ? `
        <div class="alert alert-warning" style="margin-top:10px;margin-bottom:0;padding:8px 12px;font-size:0.82rem;">
          <span class="alert-icon">⚠️</span>
          <div>${warnings.map(escapeHTML).join("<br>")}</div>
        </div>
      ` : ""}
      <div class="msg-meta">
        <span>Evidence: ${escapeHTML(result.confidence)} · ${time}</span>
      </div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
  }

  function appendErrorResponse(userQuery, errorDetail) {
    const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const div = document.createElement("div");
    div.className = "chat-msg assistant";
    div.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
        <span class="badge badge-red">Backend Connection Failed</span>
      </div>
      <div class="alert alert-error" style="margin-bottom:0;padding:10px 14px;font-size:0.85rem;">
        <span class="alert-icon">❌</span>
        <div>
          <strong>Error querying /api/assistant/chat:</strong><br>
          ${escapeHTML(errorDetail)}<br><br>
          <em>Please verify the backend server is running on <code>${WW_CONFIG.BACKEND_URL}</code>.</em>
        </div>
      </div>
      <div class="msg-meta">
        <span>Network Error · ${time}</span>
      </div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
  }

  function escapeHTML(str) {
    if (!str) return "";
    return String(str).replace(/[&<>'"]/g, 
      tag => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        "'": '&#39;',
        '"': '&quot;'
      }[tag] || tag)
    );
  }
});
