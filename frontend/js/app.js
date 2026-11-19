/**
 * WasteWise AI – app.js (Step 2 Enhanced)
 * ---------------------------------------
 * Handles:
 *  1. Preserved Step 1 checkBackendConnection() using central WW_CONFIG & WW_API.
 *  2. Header elevation/shadow on scroll.
 *  3. Mobile menu toggle for landing page navigation.
 *  4. Smooth link navigation behavior.
 */

/**
 * Called when the user clicks "Check Backend Connection".
 * Uses centralized WW_API.health() and renders real results or actual network errors.
 */
async function checkBackendConnection() {
  const btn        = document.getElementById("checkBtn");
  const resultBox  = document.getElementById("resultBox");
  const statusIcon = document.getElementById("statusIcon");
  const statusText = document.getElementById("statusText");
  const responseData = document.getElementById("responseData");

  if (!btn || !resultBox) return;

  // Loading UI state
  btn.disabled = true;
  btn.textContent = "⏳ Connecting…";

  resultBox.className = "result-box loading";
  resultBox.classList.remove("hidden");
  statusIcon.textContent = "⏳";
  statusText.textContent = "Connecting to backend at " + WW_CONFIG.BACKEND_URL + "…";
  responseData.textContent = "";

  try {
    // Real call via central API module
    const data = await WW_API.health();

    resultBox.className = "result-box success";
    statusIcon.textContent = "✅";
    statusText.textContent = "Connected! HTTP 200 OK";
    responseData.textContent = JSON.stringify(data, null, 2);
  } catch (error) {
    resultBox.className = "result-box error";
    statusIcon.textContent = "❌";
    statusText.textContent = "Connection failed – backend not reachable";
    responseData.textContent =
      `Error: ${error.message}\n\n` +
      `Troubleshooting:\n` +
      `  • Verify the FastAPI server is running on: ${WW_CONFIG.BACKEND_URL}\n` +
      `  • In your backend directory run:\n` +
      `      .\\venv\\Scripts\\Activate.ps1\n` +
      `      uvicorn app.main:app --reload --host 127.0.0.1 --port 8000\n` +
      `  • Ensure CORS allows your frontend origin.`;
  } finally {
    btn.disabled = false;
    btn.textContent = "🔌 Check Backend Connection";
  }
}

// Landing page interactions
document.addEventListener("DOMContentLoaded", () => {
  // 1. Header scroll shadow
  const header = document.getElementById("mainHeader");
  if (header) {
    window.addEventListener("scroll", () => {
      if (window.scrollY > 15) {
        header.classList.add("scrolled");
      } else {
        header.classList.remove("scrolled");
      }
    });
  }

  // 2. Mobile Menu Toggle
  const mobileBtn = document.getElementById("mobileMenuBtn");
  const navLinks = document.getElementById("navLinks");
  if (mobileBtn && navLinks) {
    mobileBtn.addEventListener("click", () => {
      const isVisible = navLinks.style.display === "flex";
      navLinks.style.display = isVisible ? "none" : "flex";
      if (!isVisible) {
        navLinks.style.flexDirection = "column";
        navLinks.style.position = "absolute";
        navLinks.style.top = "70px";
        navLinks.style.left = "0";
        navLinks.style.right = "0";
        navLinks.style.background = "#ffffff";
        navLinks.style.padding = "20px 24px";
        navLinks.style.boxShadow = "var(--shadow-md)";
        navLinks.style.borderBottom = "1px solid var(--clr-border)";
      }
    });
  }
});
