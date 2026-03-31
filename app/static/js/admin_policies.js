/**
 * admin_policies.js — Policies CRUD + acceptance records page logic.
 */
(function() {
  "use strict";
  var G = window.GasketAdmin;

  var policyModal = document.getElementById('policy-modal');
  var policyForm = document.getElementById('policy-form');
  var policyFormId = document.getElementById('policy-form-id');
  var policyFormName = document.getElementById('policy-form-name');
  var policyFormDesc = document.getElementById('policy-form-desc');
  var policyFormContent = document.getElementById('policy-form-content');
  var policyFormReaccept = document.getElementById('policy-form-reaccept');
  var policyFormError = document.getElementById('policy-form-error');
  var policyFormSubmit = document.getElementById('policy-form-submit');
  var policyModalTitle = document.getElementById('policy-modal-title');

  var policyDeleteModal = document.getElementById('policy-delete-modal');
  var policyDeleteNameEl = document.getElementById('policy-delete-name');
  var policyDeleteConfirmBtn = document.getElementById('policy-delete-confirm');
  var pendingPolicyDeleteId = null;

  document.getElementById('btn-add-policy').addEventListener('click', function() {
    policyModalTitle.textContent = 'Add Policy';
    policyFormSubmit.textContent = 'Create';
    policyFormId.value = '';
    policyFormName.value = '';
    policyFormName.disabled = false;
    policyFormDesc.value = '';
    policyFormContent.value = '';
    policyFormReaccept.checked = false;
    policyFormError.style.display = 'none';
    G.openModal(policyModal);
    policyFormName.focus();
  });

  function openPolicyEditModal(id) {
    policyFormError.style.display = 'none';
    policyFormSubmit.textContent = 'Saving…';
    policyFormSubmit.disabled = true;
    policyModalTitle.textContent = 'Edit Policy';
    G.openModal(policyModal);

    fetch('/admin/api/policies/' + id)
      .then(function(r) { if (!r.ok) throw new Error('Failed to load'); return r.json(); })
      .then(function(d) {
        policyFormId.value = d.id;
        policyFormName.value = d.name;
        policyFormName.disabled = false;
        policyFormDesc.value = d.description || '';
        policyFormContent.value = d.current_content || '';
        policyFormReaccept.checked = d.enforce_reacceptance;
      })
      .catch(function(err) { policyFormError.textContent = err.message; policyFormError.style.display = 'block'; })
      .finally(function() { policyFormSubmit.textContent = 'Save'; policyFormSubmit.disabled = false; });
  }

  G.bindModalClose(policyModal, ['policy-modal-close', 'policy-form-cancel']);
  G.bindModalClose(policyDeleteModal, ['policy-delete-close', 'policy-delete-cancel']);

  policyForm.addEventListener('submit', function(e) {
    e.preventDefault();
    policyFormError.style.display = 'none';
    var name = policyFormName.value.trim();
    if (!name) { policyFormError.textContent = 'Name is required'; policyFormError.style.display = 'block'; return; }
    var content = policyFormContent.value.trim();
    if (!content) { policyFormError.textContent = 'Policy content is required'; policyFormError.style.display = 'block'; return; }

    var payload = { name: name, description: policyFormDesc.value.trim(), content: content, enforce_reacceptance: policyFormReaccept.checked };
    var id = policyFormId.value;
    var url = id ? '/admin/api/policies/' + id : '/admin/api/policies';
    var method = id ? 'PUT' : 'POST';
    policyFormSubmit.disabled = true;
    policyFormSubmit.textContent = 'Saving…';

    fetch(url, { method: method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      .then(function(res) { if (!res.ok) return res.json().then(function(d) { throw new Error(d.error || 'Save failed'); }); return res.json(); })
      .then(function() { G.closeModal(policyModal); loadPolicies(); })
      .catch(function(err) { policyFormError.textContent = err.message; policyFormError.style.display = 'block'; })
      .finally(function() { policyFormSubmit.disabled = false; policyFormSubmit.textContent = 'Save'; });
  });

  function openPolicyDeleteModal(id, name) {
    pendingPolicyDeleteId = id;
    policyDeleteNameEl.textContent = name;
    G.openModal(policyDeleteModal);
  }

  policyDeleteConfirmBtn.addEventListener('click', function() {
    if (!pendingPolicyDeleteId) return;
    policyDeleteConfirmBtn.disabled = true;
    policyDeleteConfirmBtn.textContent = 'Deleting…';
    fetch('/admin/api/policies/' + pendingPolicyDeleteId, { method: 'DELETE' })
      .then(function(res) { if (!res.ok) throw new Error('Delete failed'); G.closeModal(policyDeleteModal); loadPolicies(); })
      .catch(function() { alert('Failed to delete policy.'); })
      .finally(function() { policyDeleteConfirmBtn.disabled = false; policyDeleteConfirmBtn.textContent = 'Delete'; });
  });

  function loadPolicies() {
    var loading = document.getElementById('policies-loading');
    var empty = document.getElementById('policies-empty');
    var wrapper = document.getElementById('policies-table-wrapper');
    var tbody = document.getElementById('policies-tbody');
    loading.style.display = 'block'; empty.style.display = 'none'; wrapper.style.display = 'none';

    fetch('/admin/api/policies')
      .then(function(r) { return r.json(); })
      .then(function(policies) {
        loading.style.display = 'none';
        tbody.innerHTML = '';
        if (policies.length === 0) { empty.style.display = 'block'; return; }
        wrapper.style.display = 'block';
        policies.forEach(function(p) {
          var tr = document.createElement('tr');
          var reacceptBadge = p.enforce_reacceptance
            ? '<span class="badge badge-warning" style="font-size:0.7rem;">Enabled</span>'
            : '<span class="text-muted" style="font-size:0.8rem;">—</span>';
          var profilesList = p.profile_names && p.profile_names.length > 0
            ? p.profile_names.map(function(n) { return '<span class="badge badge-outline" style="font-size:0.7rem; margin-right:2px;">' + G.escapeHtml(n) + '</span>'; }).join(' ')
            : '—';
          tr.innerHTML =
            '<td><strong>' + G.escapeHtml(p.name) + '</strong></td>' +
            '<td><span class="text-muted" style="font-size:0.8rem;">' + G.escapeHtml(p.description || '—') + '</span></td>' +
            '<td>' + G.sourceBadge(p.source) + '</td>' +
            '<td><span style="font-size:0.8rem;">v' + (p.current_version || '—') + '</span></td>' +
            '<td>' + reacceptBadge + '</td>' +
            '<td>' + profilesList + '</td>' +
            '<td style="text-align:right;"><div style="display:flex;gap:var(--space-xs);justify-content:flex-end;"></div></td>';
          var actionsCell = tr.querySelector('td:last-child div');
          if (p.source !== 'config') {
            var editBtn = document.createElement('button');
            editBtn.className = 'btn btn-info btn-sm'; editBtn.textContent = 'Edit'; editBtn.style.fontSize = '0.7rem';
            editBtn.addEventListener('click', function() { openPolicyEditModal(p.id); });
            actionsCell.appendChild(editBtn);
            var delBtn = document.createElement('button');
            delBtn.className = 'btn btn-danger btn-sm'; delBtn.textContent = 'Delete'; delBtn.style.fontSize = '0.7rem';
            delBtn.addEventListener('click', function() { openPolicyDeleteModal(p.id, p.name); });
            actionsCell.appendChild(delBtn);
          }
          tbody.appendChild(tr);
        });
      })
      .catch(function() { loading.style.display = 'none'; empty.style.display = 'block'; });
  }

  function loadAcceptances(userFilter) {
    var loading = document.getElementById('acceptances-loading');
    var empty = document.getElementById('acceptances-empty');
    var wrapper = document.getElementById('acceptances-table-wrapper');
    var tbody = document.getElementById('acceptances-tbody');
    loading.style.display = 'block'; empty.style.display = 'none'; wrapper.style.display = 'none';
    var url = '/admin/api/policies/acceptances';
    if (userFilter) url += '?user=' + encodeURIComponent(userFilter);
    fetch(url)
      .then(function(r) { return r.json(); })
      .then(function(acceptances) {
        loading.style.display = 'none'; tbody.innerHTML = '';
        if (acceptances.length === 0) { empty.style.display = 'block'; return; }
        wrapper.style.display = 'block';
        acceptances.forEach(function(a) {
          var tr = document.createElement('tr');
          tr.innerHTML =
            '<td>' + G.escapeHtml(a.user_email) + '</td>' +
            '<td>' + G.escapeHtml(a.policy_name || '—') + '</td>' +
            '<td>v' + (a.version_number || '—') + '</td>' +
            '<td>' + G.escapeHtml(a.profile_name || '—') + '</td>' +
            '<td><span class="text-muted" style="font-size:0.8rem;">' + (a.accepted_at ? new Date(a.accepted_at).toLocaleString() : '—') + '</span></td>';
          tbody.appendChild(tr);
        });
      })
      .catch(function() { loading.style.display = 'none'; empty.style.display = 'block'; });
  }

  var acceptancesFilter = document.getElementById('acceptances-user-filter');
  var acceptancesFilterTimeout = null;
  if (acceptancesFilter) {
    acceptancesFilter.addEventListener('input', function() {
      clearTimeout(acceptancesFilterTimeout);
      acceptancesFilterTimeout = setTimeout(function() { loadAcceptances(acceptancesFilter.value.trim()); }, 300);
    });
  }

  loadPolicies();
  loadAcceptances();
})();
