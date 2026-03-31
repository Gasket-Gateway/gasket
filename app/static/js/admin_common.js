/**
 * admin_common.js — Shared helpers for all admin pages.
 */
(function() {
  "use strict";

  // ─── HTML escaping ───
  function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // ─── Latency formatting ───
  function formatLatency(ms) {
    if (ms >= 1000) return (ms / 1000).toFixed(1) + 's';
    return ms + 'ms';
  }

  // ─── Modal helpers ───
  function openModal(modalEl) {
    modalEl.classList.add('active');
  }

  function closeModal(modalEl) {
    modalEl.classList.remove('active');
  }

  function bindModalClose(modalEl, closeBtnIds) {
    closeBtnIds.forEach(function(id) {
      var btn = document.getElementById(id);
      if (btn) btn.addEventListener('click', function() { closeModal(modalEl); });
    });
    modalEl.addEventListener('click', function(e) {
      if (e.target === modalEl) closeModal(modalEl);
    });
  }

  // ─── Badge helpers ───
  function getKeyStatusBadge(key) {
    if (key.revoked) return '<span class="badge badge-danger" style="font-size:0.7rem;">Revoked</span>';
    if (key.is_expired) return '<span class="badge badge-warning" style="font-size:0.7rem;">Expired</span>';
    return '<span class="badge badge-success" style="font-size:0.7rem;">Active</span>';
  }

  function sourceBadge(source) {
    if (source === 'config') {
      return '<span class="badge badge-info" style="font-size:0.7rem;">config</span>';
    }
    return '<span class="badge badge-outline" style="font-size:0.7rem;">admin</span>';
  }

  // ─── Export to global scope ───
  window.GasketAdmin = {
    escapeHtml: escapeHtml,
    formatLatency: formatLatency,
    openModal: openModal,
    closeModal: closeModal,
    bindModalClose: bindModalClose,
    getKeyStatusBadge: getKeyStatusBadge,
    sourceBadge: sourceBadge,
  };
})();
