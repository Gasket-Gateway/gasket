/**
 * Gasket Gateway — Theme toggle (dark/light mode)
 *
 * Priority order:
 *   1. localStorage preference (user's explicit choice)
 *   2. Server-side default_theme from config
 *   3. OS prefers-color-scheme
 *   4. Fallback to "light"
 */

(function () {
  "use strict";

  const STORAGE_KEY = "gasket-theme";

  function getDefaultTheme() {
    // Check for server-configured default (injected into <html data-default-theme>)
    const serverDefault = document.documentElement.dataset.defaultTheme;
    if (serverDefault === "dark" || serverDefault === "light") {
      return serverDefault;
    }
    // Fall back to OS preference
    if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
      return "dark";
    }
    return "light";
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    // Update toggle button icon
    const toggleBtn = document.getElementById("theme-toggle");
    if (toggleBtn) {
      toggleBtn.textContent = theme === "dark" ? "☀️" : "🌙";
      toggleBtn.setAttribute("aria-label", theme === "dark" ? "Switch to light mode" : "Switch to dark mode");
    }
  }

  function initTheme() {
    const saved = localStorage.getItem(STORAGE_KEY);
    const theme = saved || getDefaultTheme();
    applyTheme(theme);
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    const next = current === "dark" ? "light" : "dark";
    localStorage.setItem(STORAGE_KEY, next);
    applyTheme(next);
  }

  // Apply immediately to avoid flash
  initTheme();

  // Bind toggle button once DOM is ready
  document.addEventListener("DOMContentLoaded", function () {
    const toggleBtn = document.getElementById("theme-toggle");
    if (toggleBtn) {
      toggleBtn.addEventListener("click", toggleTheme);
    }
    // Re-apply in case DOM wasn't ready for icon update
    const saved = localStorage.getItem(STORAGE_KEY);
    applyTheme(saved || getDefaultTheme());
  });
})();
