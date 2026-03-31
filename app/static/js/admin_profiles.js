/**
 * admin_profiles.js — Backend Profiles CRUD page logic.
 */
(function() {
  "use strict";
  var G = window.GasketAdmin;

  var profileModal = document.getElementById('profile-modal');
  var profileForm = document.getElementById('profile-form');
  var profileFormId = document.getElementById('profile-form-id');
  var profileFormName = document.getElementById('profile-form-name');
  var profileFormOidcGroups = document.getElementById('profile-form-oidc-groups');
  var profileFormDesc = document.getElementById('profile-form-desc');
  var profileFormBackends = document.getElementById('profile-form-backends');
  var profileFormPolicies = document.getElementById('profile-form-policies');
  var profileFormAuditMeta = document.getElementById('profile-form-audit-meta');
  var profileFormAuditContent = document.getElementById('profile-form-audit-content');
  var profileFormOpenWebui = document.getElementById('profile-form-open-webui');
  var profileFormMaxKeys = document.getElementById('profile-form-max-keys');
  var profileFormExpiryDays = document.getElementById('profile-form-expiry-days');
  var profileFormEnforceExpiry = document.getElementById('profile-form-enforce-expiry');
  var profileFormError = document.getElementById('profile-form-error');
  var profileFormSubmit = document.getElementById('profile-form-submit');
  var profileModalTitle = document.getElementById('profile-modal-title');

  var profileDeleteModal = document.getElementById('profile-delete-modal');
  var profileDeleteNameEl = document.getElementById('profile-delete-name');
  var profileDeleteConfirmBtn = document.getElementById('profile-delete-confirm');
  var pendingProfileDeleteId = null;

  function populateProfileBackendsSelect(selectedIds) {
    profileFormBackends.innerHTML = '';
    return fetch('/admin/api/backends')
      .then(function(r) { return r.json(); })
      .then(function(backends) {
        backends.forEach(function(b) {
          var opt = document.createElement('option');
          opt.value = b.id;
          opt.textContent = b.name;
          if (selectedIds && selectedIds.includes(b.id)) opt.selected = true;
          profileFormBackends.appendChild(opt);
        });
      });
  }

  function populateProfilePoliciesSelect(selectedIds) {
    profileFormPolicies.innerHTML = '';
    return fetch('/admin/api/policies')
      .then(function(r) { return r.json(); })
      .then(function(policies) {
        policies.forEach(function(p) {
          var opt = document.createElement('option');
          opt.value = p.id;
          opt.textContent = p.name + (p.current_version ? ' (v' + p.current_version + ')' : '');
          if (selectedIds && selectedIds.includes(p.id)) opt.selected = true;
          profileFormPolicies.appendChild(opt);
        });
      });
  }

  // ─── Open profile modal for add ───
  document.getElementById('btn-add-profile').addEventListener('click', function() {
    profileModalTitle.textContent = 'Add Profile';
    profileFormSubmit.textContent = 'Create';
    profileFormId.value = '';
    profileFormName.value = '';
    profileFormName.disabled = false;
    profileFormOidcGroups.value = '';
    profileFormDesc.value = '';
    profileFormAuditMeta.checked = true;
    profileFormAuditContent.checked = false;
    profileFormOpenWebui.checked = false;
    profileFormMaxKeys.value = 5;
    profileFormExpiryDays.value = '';
    profileFormEnforceExpiry.checked = false;
    profileFormError.style.display = 'none';

    Promise.all([
      populateProfileBackendsSelect([]),
      populateProfilePoliciesSelect([])
    ]).then(function() {
      G.openModal(profileModal);
      profileFormName.focus();
    });
  });

  // ─── Open profile modal for edit ───
  function openProfileEditModal(id) {
    profileFormError.style.display = 'none';
    profileFormSubmit.textContent = 'Saving…';
    profileFormSubmit.disabled = true;
    profileModalTitle.textContent = 'Edit Profile';

    populateProfileBackendsSelect([]);
    populateProfilePoliciesSelect([]);
    profileFormName.value = 'Loading…';
    profileFormName.disabled = true;
    G.openModal(profileModal);

    fetch('/admin/api/profiles/' + id)
      .then(function(r) {
        if (!r.ok) throw new Error('Failed to load profile');
        return r.json();
      })
      .then(function(data) {
        profileFormId.value = data.id;
        profileFormName.value = data.name;
        profileFormName.disabled = false;
        profileFormOidcGroups.value = (data.oidc_groups || []).join('\n');
        profileFormDesc.value = data.description || '';
        profileFormAuditMeta.checked = data.metadata_audit;
        profileFormAuditContent.checked = data.content_audit;
        profileFormOpenWebui.checked = data.open_webui_enabled;
        profileFormMaxKeys.value = data.max_keys_per_user;
        profileFormExpiryDays.value = data.default_expiry_days || '';
        profileFormEnforceExpiry.checked = data.enforce_expiry;
        populateProfileBackendsSelect(data.backend_ids);
        populateProfilePoliciesSelect(data.policy_ids);
      })
      .catch(function(err) {
        profileFormError.textContent = err.message;
        profileFormError.style.display = 'block';
      })
      .finally(function() {
        profileFormSubmit.textContent = 'Save';
        profileFormSubmit.disabled = false;
      });
  }

  function openProfileDeleteModal(id, name) {
    pendingProfileDeleteId = id;
    profileDeleteNameEl.textContent = name;
    G.openModal(profileDeleteModal);
  }

  G.bindModalClose(profileModal, ['profile-modal-close', 'profile-form-cancel']);
  G.bindModalClose(profileDeleteModal, ['profile-delete-close', 'profile-delete-cancel']);

  // ─── Handle Profile form submission ───
  profileForm.addEventListener('submit', function(e) {
    e.preventDefault();
    profileFormError.style.display = 'none';

    var name = profileFormName.value.trim();
    if (!name) {
      profileFormError.textContent = 'Name is required';
      profileFormError.style.display = 'block';
      return;
    }

    var selectedBackends = [];
    for (var i = 0; i < profileFormBackends.options.length; i++) {
      if (profileFormBackends.options[i].selected) selectedBackends.push(parseInt(profileFormBackends.options[i].value, 10));
    }

    var selectedPolicies = [];
    for (var j = 0; j < profileFormPolicies.options.length; j++) {
      if (profileFormPolicies.options[j].selected) selectedPolicies.push(parseInt(profileFormPolicies.options[j].value, 10));
    }

    var oidcGroupsRaw = profileFormOidcGroups.value.trim();
    var oidcGroupsList = oidcGroupsRaw ? oidcGroupsRaw.split('\n').map(function(g) { return g.trim(); }).filter(function(g) { return g; }) : [];

    var payload = {
      name: name,
      oidc_groups: oidcGroupsList,
      description: profileFormDesc.value.trim(),
      metadata_audit: profileFormAuditMeta.checked,
      content_audit: profileFormAuditContent.checked,
      open_webui_enabled: profileFormOpenWebui.checked,
      max_keys_per_user: parseInt(profileFormMaxKeys.value, 10) || 5,
      enforce_expiry: profileFormEnforceExpiry.checked,
      backend_ids: selectedBackends,
      policy_ids: selectedPolicies
    };

    var expDays = parseInt(profileFormExpiryDays.value, 10);
    payload.default_expiry_days = (!isNaN(expDays) && expDays > 0) ? expDays : null;

    var id = profileFormId.value;
    var url = id ? '/admin/api/profiles/' + id : '/admin/api/profiles';
    var method = id ? 'PUT' : 'POST';

    profileFormSubmit.disabled = true;
    profileFormSubmit.textContent = 'Saving…';

    fetch(url, { method: method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      .then(function(res) {
        if (!res.ok) return res.json().then(function(d) { throw new Error(d.error || 'Save failed'); });
        return res.json();
      })
      .then(function() {
        G.closeModal(profileModal);
        loadProfiles();
      })
      .catch(function(err) {
        profileFormError.textContent = err.message;
        profileFormError.style.display = 'block';
      })
      .finally(function() {
        profileFormSubmit.disabled = false;
        profileFormSubmit.textContent = 'Save';
      });
  });

  // ─── Handle Profile deletion ───
  profileDeleteConfirmBtn.addEventListener('click', function() {
    if (!pendingProfileDeleteId) return;
    profileDeleteConfirmBtn.disabled = true;
    profileDeleteConfirmBtn.textContent = 'Deleting…';

    fetch('/admin/api/profiles/' + pendingProfileDeleteId, { method: 'DELETE' })
      .then(function(res) {
        if (!res.ok) throw new Error('Delete failed');
        G.closeModal(profileDeleteModal);
        loadProfiles();
      })
      .catch(function() { alert('Failed to delete profile.'); })
      .finally(function() {
        profileDeleteConfirmBtn.disabled = false;
        profileDeleteConfirmBtn.textContent = 'Delete';
      });
  });

  // ─── Load and render profiles table ───
  function loadProfiles() {
    var loading = document.getElementById('profiles-loading');
    var empty = document.getElementById('profiles-empty');
    var wrapper = document.getElementById('profiles-table-wrapper');
    var tbody = document.getElementById('profiles-tbody');

    loading.style.display = 'block';
    empty.style.display = 'none';
    wrapper.style.display = 'none';

    fetch('/admin/api/profiles')
      .then(function(r) { return r.json(); })
      .then(function(profiles) {
        loading.style.display = 'none';
        tbody.innerHTML = '';

        if (profiles.length === 0) { empty.style.display = 'block'; return; }

        wrapper.style.display = 'block';

        profiles.forEach(function(p) {
          var tr = document.createElement('tr');
          var isConfig = p.source === 'config';

          var backendsList = p.backend_names && p.backend_names.length > 0
            ? G.escapeHtml(p.backend_names.join(', '))
            : '<em>None</em>';

          var policiesList = p.policy_names && p.policy_names.length > 0
            ? p.policy_names.map(function(n) {
                return '<span class="badge badge-outline" style="font-size:0.7rem; margin-right:2px;">' + G.escapeHtml(n) + '</span>';
              }).join(' ')
            : '—';

          var auditStr = [];
          if (p.metadata_audit) auditStr.push('Meta');
          if (p.content_audit) auditStr.push('Content');
          var auditDisplay = auditStr.length ? G.escapeHtml(auditStr.join(' + ')) : 'None';

          var oidcGroupsDisplay = p.oidc_groups && p.oidc_groups.length > 0
            ? p.oidc_groups.map(function(g) {
                return '<span class="badge badge-outline" style="font-size:0.7rem; margin-right:2px;">' + G.escapeHtml(g) + '</span>';
              }).join(' ')
            : '—';

          tr.innerHTML =
            '<td><strong>' + G.escapeHtml(p.name) + '</strong></td>' +
            '<td><span class="text-muted" style="font-size:0.8rem;">' + G.escapeHtml(p.description || '—') + '</span></td>' +
            '<td>' + oidcGroupsDisplay + '</td>' +
            '<td>' + G.sourceBadge(p.source) + '</td>' +
            '<td><span style="font-size:0.8rem;">' + backendsList + '</span></td>' +
            '<td>' + policiesList + '</td>' +
            '<td><span style="font-size:0.8rem;">' + auditDisplay + '</span></td>' +
            '<td><span style="font-size:0.8rem;">Max ' + p.max_keys_per_user + ' keys</span></td>' +
            '<td style="text-align:right;"><div style="display:flex;gap:var(--space-xs);justify-content:flex-end;"></div></td>';

          var actionsCell = tr.querySelector('td:last-child div');

          if (!isConfig) {
            var editBtn = document.createElement('button');
            editBtn.className = 'btn btn-info btn-sm';
            editBtn.textContent = 'Edit';
            editBtn.style.fontSize = '0.7rem';
            editBtn.addEventListener('click', function() { openProfileEditModal(p.id); });
            actionsCell.appendChild(editBtn);

            var delBtn = document.createElement('button');
            delBtn.className = 'btn btn-danger btn-sm';
            delBtn.textContent = 'Delete';
            delBtn.style.fontSize = '0.7rem';
            delBtn.addEventListener('click', function() { openProfileDeleteModal(p.id, p.name); });
            actionsCell.appendChild(delBtn);
          }

          tbody.appendChild(tr);
        });
      })
      .catch(function() {
        loading.style.display = 'none';
        empty.style.display = 'block';
      });
  }

  // Auto-load on page load
  loadProfiles();
})();
