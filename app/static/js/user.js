/**
 * Gasket Gateway — User dropdown menu toggle
 */

(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var toggleBtn = document.getElementById("user-menu-toggle");
    var dropdown = document.getElementById("user-dropdown");

    if (!toggleBtn || !dropdown) return;

    toggleBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      var isOpen = dropdown.classList.toggle("open");
      toggleBtn.setAttribute("aria-expanded", isOpen ? "true" : "false");
    });

    // Close dropdown when clicking outside
    document.addEventListener("click", function (e) {
      if (!dropdown.contains(e.target) && e.target !== toggleBtn) {
        dropdown.classList.remove("open");
        toggleBtn.setAttribute("aria-expanded", "false");
      }
    });

    // Close on Escape key
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        dropdown.classList.remove("open");
        toggleBtn.setAttribute("aria-expanded", "false");
      }
    });
  });
})();
