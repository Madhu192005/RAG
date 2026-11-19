/**
 * WasteWise AI – nav.js
 * ----------------------
 * Handles:
 *  1. Desktop sidebar active-link highlighting.
 *  2. Mobile sidebar open/close toggle.
 *  3. Topbar backend-status pill (optional).
 */

const WW_NAV = (() => {

  /* ── Active-link highlighting ─────────────────────────── */
  function highlightCurrent() {
    const current = window.location.pathname.split("/").pop() || "index.html";
    document.querySelectorAll(".sidebar-nav a").forEach(link => {
      const href = link.getAttribute("href").split("/").pop();
      if (href === current || (current === "" && href === "index.html")) {
        link.classList.add("active");
        link.closest("li")?.classList.add("active");
      }
    });
  }

  /* ── Mobile sidebar toggle ────────────────────────────── */
  function initMobileToggle() {
    const btn     = document.getElementById("sidebarToggle");
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("sidebarOverlay");
    if (!btn || !sidebar) return;

    btn.addEventListener("click", () => {
      sidebar.classList.toggle("open");
      if (overlay) overlay.classList.toggle("active");
    });

    overlay?.addEventListener("click", () => {
      sidebar.classList.remove("open");
      overlay.classList.remove("active");
    });
  }

  /* ── Backend status pill in topbar ───────────────────── */
  async function checkTopbarStatus() {
    const pill = document.getElementById("backendStatusPill");
    if (!pill) return;
    try {
      await WW_API.health();
      pill.className = "status-pill online";
      pill.textContent = "● Backend Online";
    } catch {
      pill.className = "status-pill offline";
      pill.textContent = "● Backend Offline";
    }
  }

  /* ── Init ─────────────────────────────────────────────── */
  function init() {
    highlightCurrent();
    initMobileToggle();
    checkTopbarStatus();
  }

  return { init, checkTopbarStatus };
})();

// Auto-init when DOM is ready
document.addEventListener("DOMContentLoaded", WW_NAV.init);
