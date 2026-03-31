/**
 * admin_backends.js — OpenAI Backends CRUD page logic.
 */
(function() {
  "use strict";
  var G = window.GasketAdmin;

  var backendModal = document.getElementById('backend-modal');
  var backendForm = document.getElementById('backend-form');
  var backendFormId = document.getElementById('backend-form-id');
  var backendFormName = document.getElementById('backend-form-name');
  var backendFormUrl = document.getElementById('backend-form-url');
  var backendFormKey = document.getElementById('backend-form-key');
  var backendFormTls = document.getElementById('backend-form-tls');
  var backendFormError = document.getElementById('backend-form-error');
  var backendFormSubmit = document.getElementById('backend-form-submit');
  var backendModalTitle = document.getElementById('backend-modal-title');

  var deleteModal = document.getElementById('backend-delete-modal');
  var deleteNameEl = document.getElementById('backend-delete-name');
  var deleteConfirmBtn = document.getElementById('backend-delete-confirm');
  var pendingDeleteId = null;

  // ─── Error modal (for test connection) ───
  var errorModal = document.getElementById('error-detail-modal');
  var errorModalTitle = document.getElementById('error-modal-title');
  var errorModalService = document.getElementById('error-modal-service');
  var errorModalDetail = document.getElementById('error-modal-detail');
  var errorModalRecheckBtn = document.getElementById('error-modal-recheck');
  var currentErrorServiceKey = null;
  var currentErrorServiceName = null;

  function openErrorModal(serviceKey, serviceName, detail, latencyMs) {
    currentErrorServiceKey = serviceKey;
    currentErrorServiceName = serviceName;
    errorModalTitle.textContent = serviceName + ' — Connection Error';
    errorModalService.innerHTML = 'Service <strong>' + serviceName + '</strong> failed its health check.';
    errorModalDetail.textContent = detail || 'Unknown error';
    var latencyEl = document.getElementById('error-modal-latency');
    if (latencyEl) latencyEl.textContent = G.formatLatency(latencyMs || 0);
    errorModalRecheckBtn.disabled = false;
    errorModalRecheckBtn.textContent = 'Recheck';
    G.openModal(errorModal);
  }

  function closeErrorModal() {
    G.closeModal(errorModal);
    errorModal.querySelector('.modal').classList.remove('modal-expanded');
    currentErrorServiceKey = null;
    currentErrorServiceName = null;
  }

  document.getElementById('error-modal-close').addEventListener('click', closeErrorModal);
  errorModal.addEventListener('click', function(e) { if (e.target === errorModal) closeErrorModal(); });
  document.getElementById('error-modal-expand').addEventListener('click', function() {
    errorModal.querySelector('.modal').classList.toggle('modal-expanded');
  });
  errorModalRecheckBtn.addEventListener('click', function() {
    if (!currentErrorServiceKey) return;
    testBackendConnection(currentErrorServiceKey, errorModalRecheckBtn);
  });

  // ─── Open backend modal for add ───
  document.getElementById('btn-add-backend').addEventListener('click', function() {
    backendModalTitle.textContent = 'Add Backend';
    backendFormSubmit.textContent = 'Create';
    backendFormId.value = '';
    backendFormName.value = '';
    backendFormUrl.value = '';
    backendFormKey.value = '';
    backendFormTls.checked = false;
    backendFormName.disabled = false;
    backendFormError.style.display = 'none';
    var testResult = document.getElementById('backend-form-test-result');
    if (testResult) testResult.style.display = 'none';
    G.openModal(backendModal);
    backendFormName.focus();
  });

  // ─── Open backend modal for edit ───
  function openEditModal(id) {
    backendFormError.style.display = 'none';
    var testResult = document.getElementById('backend-form-test-result');
    if (testResult) testResult.style.display = 'none';
    backendFormSubmit.textContent = 'Saving…';
    backendFormSubmit.disabled = true;
    backendModalTitle.textContent = 'Edit Backend';

    fetch('/admin/api/backends/' + id)
      .then(function(r) { return r.json(); })
      .then(function(b) {
        backendFormId.value = b.id;
        backendFormName.value = b.name;
        backendFormUrl.value = b.base_url;
        backendFormKey.value = b.api_key;
        backendFormTls.checked = b.skip_tls_verify;
        backendFormName.disabled = false;
        backendFormSubmit.textContent = 'Save';
        backendFormSubmit.disabled = false;
        G.openModal(backendModal);
        backendFormUrl.focus();
      })
      .catch(function() {
        backendFormSubmit.textContent = 'Save';
        backendFormSubmit.disabled = false;
      });
  }

  // ─── Close backend modal ───
  G.bindModalClose(backendModal, ['backend-modal-close', 'backend-form-cancel']);

  // ─── Submit backend form ───
  backendForm.addEventListener('submit', function(e) {
    e.preventDefault();
    backendFormError.style.display = 'none';

    var id = backendFormId.value;
    var payload = {
      name: backendFormName.value.trim(),
      base_url: backendFormUrl.value.trim(),
      api_key: backendFormKey.value,
      skip_tls_verify: backendFormTls.checked
    };

    var url = id ? '/admin/api/backends/' + id : '/admin/api/backends';
    var method = id ? 'PUT' : 'POST';

    backendFormSubmit.disabled = true;
    backendFormSubmit.textContent = id ? 'Saving…' : 'Creating…';

    fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(function(res) {
        if (!res.ok) return res.json().then(function(d) { throw new Error(d.error || 'Request failed'); });
        return res.json();
      })
      .then(function() {
        G.closeModal(backendModal);
        loadBackends();
      })
      .catch(function(err) {
        backendFormError.textContent = err.message;
        backendFormError.style.display = 'block';
      })
      .finally(function() {
        backendFormSubmit.disabled = false;
        backendFormSubmit.textContent = id ? 'Save' : 'Create';
      });
  });

  // ─── Delete modal ───
  function openDeleteModal(id, name) {
    pendingDeleteId = id;
    deleteNameEl.textContent = name;
    deleteConfirmBtn.disabled = false;
    deleteConfirmBtn.textContent = 'Delete';
    G.openModal(deleteModal);
  }

  G.bindModalClose(deleteModal, ['backend-delete-close', 'backend-delete-cancel']);

  deleteConfirmBtn.addEventListener('click', function() {
    if (!pendingDeleteId) return;
    deleteConfirmBtn.disabled = true;
    deleteConfirmBtn.textContent = 'Deleting…';

    fetch('/admin/api/backends/' + pendingDeleteId, { method: 'DELETE' })
      .then(function(res) {
        if (!res.ok) return res.json().then(function(d) { throw new Error(d.error); });
        G.closeModal(deleteModal);
        loadBackends();
      })
      .catch(function(err) {
        deleteConfirmBtn.disabled = false;
        deleteConfirmBtn.textContent = 'Delete';
        alert('Delete failed: ' + err.message);
      });
  });

  // ─── Test connection ───
  function testBackendConnection(name, btn) {
    btn.disabled = true;
    btn.textContent = '⟳';

    fetch('/admin/api/status/' + encodeURIComponent(name))
      .then(function(r) { return r.json(); })
      .then(function(data) {
        updateBackendRowStatus(btn.closest('tr'), data);
      })
      .finally(function() {
        btn.disabled = false;
        btn.textContent = '⟳';
      });
  }

  function updateBackendRowStatus(row, data) {
    if (!row) return;
    var dot = row.querySelector('.status-dot');
    if (dot) dot.className = 'status-dot ' + (data.status === 'connected' ? 'status-connected' : 'status-error');
    var statusText = row.querySelector('.backend-status-text');
    if (statusText) {
      statusText.textContent = data.status === 'connected' ? G.formatLatency(data.latency_ms) : 'Error';
      statusText.className = 'backend-status-text ' + (data.status === 'connected' ? 'text-muted' : 'text-danger');
    }
  }

  function checkAllBackends() {
    var rows = document.querySelectorAll('#backends-tbody tr');
    rows.forEach(function(row) {
      var testBtn = row.querySelector('.btn-outline');
      var nameCell = row.querySelector('td:first-child strong');
      if (testBtn && nameCell) testBackendConnection(nameCell.textContent, testBtn);
    });
  }

  document.getElementById('btn-check-all-backends').addEventListener('click', checkAllBackends);

  // ─── Test Connection from edit modal ───
  var backendFormTestBtn = document.getElementById('backend-form-test');
  var backendFormTestResult = document.getElementById('backend-form-test-result');

  backendFormTestBtn.addEventListener('click', function() {
    backendFormTestResult.style.display = 'none';
    backendFormError.style.display = 'none';

    var name = backendFormName.value.trim();
    var baseUrl = backendFormUrl.value.trim();
    if (!name || !baseUrl) {
      backendFormError.textContent = 'name and base_url are required';
      backendFormError.style.display = 'block';
      return;
    }

    var id = backendFormId.value;
    var payload = {
      name: name, base_url: baseUrl,
      api_key: backendFormKey.value,
      skip_tls_verify: backendFormTls.checked
    };

    var url = id ? '/admin/api/backends/' + id : '/admin/api/backends';
    var method = id ? 'PUT' : 'POST';

    backendFormTestBtn.disabled = true;
    backendFormTestBtn.textContent = '⟳ Saving…';

    fetch(url, { method: method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      .then(function(res) {
        if (!res.ok) return res.json().then(function(d) { throw new Error(d.error || 'Save failed'); });
        return res.json();
      })
      .then(function(saved) {
        backendFormId.value = saved.id;
        backendFormTestBtn.textContent = '⟳ Testing…';
        return fetch('/admin/api/status/' + encodeURIComponent(saved.name))
          .then(function(r) { return r.json(); })
          .then(function(data) {
            backendFormTestResult.style.display = 'block';
            if (data.status === 'connected') {
              backendFormTestResult.style.color = 'var(--color-success)';
              backendFormTestResult.textContent = '✓ Saved & connected — ' + G.formatLatency(data.latency_ms);
            } else {
              backendFormTestResult.style.color = 'var(--color-danger)';
              backendFormTestResult.textContent = '✗ Saved but connection failed — ' + (data.detail || 'Unknown error');
            }
          });
      })
      .catch(function(err) {
        backendFormError.textContent = err.message;
        backendFormError.style.display = 'block';
      })
      .finally(function() {
        backendFormTestBtn.disabled = false;
        backendFormTestBtn.textContent = '⟳ Save & Test';
      });
  });

  // ─── Load and render backends table ───
  function loadBackends(autoCheck) {
    var loading = document.getElementById('backends-loading');
    var empty = document.getElementById('backends-empty');
    var wrapper = document.getElementById('backends-table-wrapper');
    var tbody = document.getElementById('backends-tbody');

    loading.style.display = 'block';
    empty.style.display = 'none';
    wrapper.style.display = 'none';

    fetch('/admin/api/backends')
      .then(function(r) { return r.json(); })
      .then(function(backends) {
        loading.style.display = 'none';
        tbody.innerHTML = '';

        if (backends.length === 0) { empty.style.display = 'block'; return; }

        wrapper.style.display = 'block';

        backends.forEach(function(b) {
          var tr = document.createElement('tr');
          var isConfig = b.source === 'config';

          tr.innerHTML =
            '<td><strong>' + G.escapeHtml(b.name) + '</strong></td>' +
            '<td><code style="font-size:0.8rem;">' + G.escapeHtml(b.base_url) + '</code></td>' +
            '<td><code style="font-size:0.8rem;">' + G.escapeHtml(b.api_key || '—') + '</code></td>' +
            '<td>' + (b.skip_tls_verify ? '⚠️ Skipped' : '✓ Enabled') + '</td>' +
            '<td>' + G.sourceBadge(b.source) + '</td>' +
            '<td><div class="status-indicator" style="gap:var(--space-xs);"><span class="status-dot status-checking"></span><span class="backend-status-text text-muted" style="font-size:0.8rem;">—</span></div></td>' +
            '<td style="text-align:right;"><div style="display:flex;gap:var(--space-xs);justify-content:flex-end;"></div></td>';

          var actionsCell = tr.querySelector('td:last-child div');

          var testBtn = document.createElement('button');
          testBtn.className = 'btn btn-outline btn-sm';
          testBtn.textContent = '⟳';
          testBtn.title = 'Test connection';
          testBtn.style.fontSize = '0.7rem';
          testBtn.addEventListener('click', function() { testBackendConnection(b.name, testBtn); });
          actionsCell.appendChild(testBtn);

          if (!isConfig) {
            var editBtn = document.createElement('button');
            editBtn.className = 'btn btn-info btn-sm';
            editBtn.textContent = 'Edit';
            editBtn.style.fontSize = '0.7rem';
            editBtn.addEventListener('click', function() { openEditModal(b.id); });
            actionsCell.appendChild(editBtn);

            var delBtn = document.createElement('button');
            delBtn.className = 'btn btn-danger btn-sm';
            delBtn.textContent = 'Delete';
            delBtn.style.fontSize = '0.7rem';
            delBtn.addEventListener('click', function() { openDeleteModal(b.id, b.name); });
            actionsCell.appendChild(delBtn);
          }

          tbody.appendChild(tr);
        });

        if (autoCheck) setTimeout(checkAllBackends, 100);
      })
      .catch(function() {
        loading.style.display = 'none';
        empty.style.display = 'block';
      });
  }

  // Auto-load and check on page load
  loadBackends(true);
})();
