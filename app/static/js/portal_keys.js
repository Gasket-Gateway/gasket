/**
 * portal_keys.js — Portal API Keys CRUD logic.
 */
(function() {
  "use strict";

  function escapeHtml(str) { var d = document.createElement('div'); d.textContent = str; return d.innerHTML; }
  function getKeyStatusBadge(k) {
    if (k.revoked) return '<span class="badge badge-danger" style="font-size:0.7rem;">Revoked</span>';
    if (k.is_expired) return '<span class="badge badge-warning" style="font-size:0.7rem;">Expired</span>';
    return '<span class="badge badge-success" style="font-size:0.7rem;">Active</span>';
  }

  var allProfiles = [];

  function loadPortalKeys() {
    var loading = document.getElementById('portal-keys-loading');
    var empty = document.getElementById('portal-keys-empty');
    var container = document.getElementById('portal-keys');
    loading.style.display = 'block'; empty.style.display = 'none'; container.style.display = 'none'; container.innerHTML = '';

    fetch('/api/keys')
      .then(function(r) { return r.json(); })
      .then(function(keys) {
        loading.style.display = 'none';
        if (keys.length === 0) { empty.style.display = 'block'; return; }
        container.style.display = 'block';

        keys.forEach(function(k) {
          var card = document.createElement('div');
          card.className = 'card'; card.style.marginBottom = 'var(--space-md)';
          var featureBadges = '';
          if (k.vscode_continue) featureBadges += '<span class="badge badge-info" style="font-size:0.65rem;margin-left:4px;">VSCode</span>';
          if (k.open_webui) featureBadges += '<span class="badge badge-info" style="font-size:0.65rem;margin-left:4px;">WebUI</span>';

          var html = '<div class="card-header" style="display:flex;align-items:center;justify-content:space-between;">' +
            '<div><strong>' + escapeHtml(k.name) + '</strong> ' + getKeyStatusBadge(k) + featureBadges + '</div>' +
            '<div><code style="font-size:0.8rem;color:var(--text-muted);">' + escapeHtml(k.key_preview) + '</code></div></div>';

          html += '<div class="card-body" style="font-size:0.85rem;">' +
            '<div style="display:flex;gap:var(--space-lg);flex-wrap:wrap;margin-bottom:var(--space-sm);">' +
            '<div><span class="text-muted">Profile:</span> <strong>' + escapeHtml(k.profile_name || '—') + '</strong></div>' +
            '<div><span class="text-muted">Created:</span> ' + (k.created_at ? new Date(k.created_at).toLocaleDateString() : '—') + '</div>' +
            '<div><span class="text-muted">Expires:</span> ' + (k.expires_at ? new Date(k.expires_at).toLocaleDateString() : 'Never') + '</div></div>';

          if (k.revoked) {
            html += '<p style="font-size:0.8rem;color:var(--text-muted);margin-top:var(--space-xs);">' +
              '🔒 Revoked' + (k.revoked_by ? ' by ' + escapeHtml(k.revoked_by) : '') +
              (k.revoked_at ? ' on ' + new Date(k.revoked_at).toLocaleDateString() : '') +
              '. Contact an administrator if you need this key restored.</p>';
          }
          html += '</div>';

          html += '<div class="card-footer" style="display:flex;gap:var(--space-xs);align-items:center;">' +
            '<button class="btn btn-outline btn-sm portal-key-reveal" data-key-id="' + k.id + '" style="font-size:0.7rem;">👁 Reveal</button>' +
            '<button class="btn btn-info btn-sm portal-key-detail" data-key-id="' + k.id + '" style="font-size:0.7rem;">Edit</button>' +
            '<span style="flex:1;"></span>';
          if (!k.revoked) html += '<button class="btn btn-danger btn-sm portal-key-revoke" data-key-id="' + k.id + '" data-key-name="' + escapeHtml(k.name) + '" style="font-size:0.7rem;">Revoke</button>';
          html += '</div>';

          card.innerHTML = html;
          container.appendChild(card);
        });

        container.querySelectorAll('.portal-key-reveal').forEach(function(btn) { btn.addEventListener('click', function() { revealKey(btn.getAttribute('data-key-id')); }); });
        container.querySelectorAll('.portal-key-detail').forEach(function(btn) { btn.addEventListener('click', function() { openKeyDetailModal(btn.getAttribute('data-key-id')); }); });
        container.querySelectorAll('.portal-key-revoke').forEach(function(btn) {
          btn.addEventListener('click', function() { openRevokeModal(btn.getAttribute('data-key-id'), btn.getAttribute('data-key-name')); });
        });
      })
      .catch(function() { loading.style.display = 'none'; empty.style.display = 'block'; });
  }

  // Reveal
  function revealKey(keyId) {
    fetch('/api/keys/' + keyId + '/reveal')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.key_value) {
          document.getElementById('portal-key-created-value').textContent = data.key_value;
          document.getElementById('portal-key-created-title').textContent = '🔑 ' + data.name;
          document.getElementById('portal-key-created-modal').querySelector('p').textContent = 'Your API key value:';
          document.getElementById('portal-key-created-copied').style.display = 'none';
          document.getElementById('portal-key-created-modal').classList.add('active');
        }
      })
      .catch(function() { alert('Failed to reveal key.'); });
  }

  // Detail / Edit modal
  function openKeyDetailModal(keyId) {
    var modal = document.getElementById('portal-key-detail-modal');
    var body = document.getElementById('portal-key-detail-body');
    var error = document.getElementById('portal-key-detail-error');
    error.style.display = 'none';
    body.innerHTML = '<p class="text-muted">Loading…</p>';
    modal.classList.add('active');

    fetch('/api/keys/' + keyId)
      .then(function(r) { return r.json(); })
      .then(function(k) {
        document.getElementById('portal-key-detail-title').textContent = k.name;
        var html = '<div style="margin-bottom:var(--space-md);">' +
          '<div style="display:flex;gap:var(--space-md);flex-wrap:wrap;margin-bottom:var(--space-md);font-size:0.85rem;">' +
          '<div><span class="text-muted">Profile:</span> <strong>' + escapeHtml(k.profile_name || '—') + '</strong></div>' +
          '<div><span class="text-muted">Status:</span> ' + getKeyStatusBadge(k) + '</div>' +
          '<div><span class="text-muted">Created:</span> ' + (k.created_at ? new Date(k.created_at).toLocaleString() : '—') + '</div>' +
          '<div><span class="text-muted">Expires:</span> ' + (k.expires_at ? new Date(k.expires_at).toLocaleString() : 'Never') + '</div></div>' +
          '<div style="margin-top:var(--space-md);">' +
          '<p style="font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;color:var(--text-muted);margin-bottom:var(--space-sm);font-weight:600;">Integrations</p>' +
          '<div class="form-check" style="margin-bottom:var(--space-sm);">' +
          '<input type="checkbox" class="form-check-input" id="detail-vscode" ' + (k.vscode_continue ? 'checked' : '') + '>' +
          '<label class="form-check-label" for="detail-vscode">VSCode Continue</label></div>' +
          '<div class="form-check" style="margin-bottom:var(--space-md);">' +
          '<input type="checkbox" class="form-check-input" id="detail-webui" ' + (k.open_webui ? 'checked' : '') + '>' +
          '<label class="form-check-label" for="detail-webui">Open WebUI</label></div>' +
          '<button class="btn btn-primary btn-sm" id="detail-save-btn" data-key-id="' + k.id + '">Save Changes</button></div></div>';
        body.innerHTML = html;

        document.getElementById('detail-save-btn').addEventListener('click', function() {
          var btn = this; btn.disabled = true; btn.textContent = 'Saving…'; error.style.display = 'none';
          fetch('/api/keys/' + k.id, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ vscode_continue: document.getElementById('detail-vscode').checked, open_webui: document.getElementById('detail-webui').checked })
          })
            .then(function(res) { if (!res.ok) return res.json().then(function(d) { throw new Error(d.error || 'Save failed'); }); return res.json(); })
            .then(function() { modal.classList.remove('active'); loadPortalKeys(); })
            .catch(function(err) { error.textContent = err.message; error.style.display = 'block'; btn.disabled = false; btn.textContent = 'Save Changes'; });
        });
      })
      .catch(function() { body.innerHTML = '<p class="text-danger">Failed to load key details.</p>'; });
  }

  var detailModal = document.getElementById('portal-key-detail-modal');
  document.getElementById('portal-key-detail-close').addEventListener('click', function() { detailModal.classList.remove('active'); });
  document.getElementById('portal-key-detail-done').addEventListener('click', function() { detailModal.classList.remove('active'); });
  detailModal.addEventListener('click', function(e) { if (e.target === detailModal) detailModal.classList.remove('active'); });

  // Revoke modal
  var revokeModal = document.getElementById('portal-key-revoke-modal');
  var pendingRevokeId = null;
  function openRevokeModal(keyId, keyName) {
    pendingRevokeId = keyId;
    document.getElementById('portal-key-revoke-name').textContent = keyName;
    document.getElementById('portal-key-revoke-confirm').disabled = false;
    document.getElementById('portal-key-revoke-confirm').textContent = 'Revoke';
    revokeModal.classList.add('active');
  }
  function closeRevokeModal() { revokeModal.classList.remove('active'); pendingRevokeId = null; }
  document.getElementById('portal-key-revoke-close').addEventListener('click', closeRevokeModal);
  document.getElementById('portal-key-revoke-cancel').addEventListener('click', closeRevokeModal);
  revokeModal.addEventListener('click', function(e) { if (e.target === revokeModal) closeRevokeModal(); });
  document.getElementById('portal-key-revoke-confirm').addEventListener('click', function() {
    if (!pendingRevokeId) return;
    var btn = this; btn.disabled = true; btn.textContent = 'Revoking…';
    fetch('/api/keys/' + pendingRevokeId + '/revoke', { method: 'POST' })
      .then(function(res) { if (!res.ok) return res.json().then(function(d) { throw new Error(d.error); }); closeRevokeModal(); loadPortalKeys(); })
      .catch(function(err) { alert('Revoke failed: ' + err.message); btn.disabled = false; btn.textContent = 'Revoke'; });
  });

  // Create key modal
  var createKeyModal = document.getElementById('portal-create-key-modal');
  var createKeyForm = document.getElementById('portal-create-key-form');
  var createKeyError = document.getElementById('portal-create-key-error');
  var createKeySubmit = document.getElementById('portal-create-key-submit');

  function openCreateKeyModal() {
    createKeyError.style.display = 'none'; createKeySubmit.disabled = false; createKeySubmit.textContent = 'Create';
    document.getElementById('portal-key-name').value = '';
    document.getElementById('portal-key-expiry').value = '';
    document.getElementById('portal-key-vscode').checked = false;
    document.getElementById('portal-key-webui').checked = false;
    document.getElementById('portal-key-webui-group').style.display = 'none';
    var select = document.getElementById('portal-key-profile');
    select.innerHTML = '<option value="">Select a profile…</option>';

    fetch('/admin/api/profiles').then(function(r) { return r.json(); }).then(function(profiles) {
      allProfiles = profiles;
      var checks = profiles.map(function(p) {
        return fetch('/admin/api/policies/acceptances/check/' + p.id).then(function(r2) { return r2.json(); })
          .then(function(status) { return { profile: p, all_accepted: status.all_accepted }; });
      });
      Promise.all(checks).then(function(results) {
        results.forEach(function(r) {
          var opt = document.createElement('option');
          opt.value = r.profile.id;
          opt.textContent = r.profile.name + (r.all_accepted ? '' : ' (policies pending)');
          opt.disabled = !r.all_accepted;
          select.appendChild(opt);
        });
      });
    });
    createKeyModal.classList.add('active');
    document.getElementById('portal-key-name').focus();
  }

  document.getElementById('portal-key-profile').addEventListener('change', function() {
    var profileId = parseInt(this.value);
    var profile = allProfiles.find(function(p) { return p.id === profileId; });
    var group = document.getElementById('portal-key-webui-group');
    if (profile && profile.open_webui_enabled) { group.style.display = ''; } else { group.style.display = 'none'; document.getElementById('portal-key-webui').checked = false; }
  });

  document.getElementById('portal-create-key-btn').addEventListener('click', openCreateKeyModal);
  function closeCreateKeyModal() { createKeyModal.classList.remove('active'); }
  document.getElementById('portal-create-key-close').addEventListener('click', closeCreateKeyModal);
  document.getElementById('portal-create-key-cancel').addEventListener('click', closeCreateKeyModal);
  createKeyModal.addEventListener('click', function(e) { if (e.target === createKeyModal) closeCreateKeyModal(); });

  createKeyForm.addEventListener('submit', function(e) {
    e.preventDefault(); createKeyError.style.display = 'none'; createKeySubmit.disabled = true; createKeySubmit.textContent = 'Creating…';
    var payload = {
      name: document.getElementById('portal-key-name').value.trim(),
      profile_id: parseInt(document.getElementById('portal-key-profile').value),
      vscode_continue: document.getElementById('portal-key-vscode').checked,
      open_webui: document.getElementById('portal-key-webui').checked
    };
    var expiry = document.getElementById('portal-key-expiry').value;
    if (expiry) payload.expires_at = expiry + 'T23:59:59+00:00';

    fetch('/api/keys', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      .then(function(res) { if (!res.ok) return res.json().then(function(d) { throw new Error(d.error || 'Create failed'); }); return res.json(); })
      .then(function(data) {
        closeCreateKeyModal(); loadPortalKeys();
        document.getElementById('portal-key-created-title').textContent = '🔑 API Key Created';
        document.getElementById('portal-key-created-modal').querySelector('p').textContent = 'Your API key has been created. You can always reveal it later from your key list.';
        document.getElementById('portal-key-created-value').textContent = data.key_value;
        document.getElementById('portal-key-created-copied').style.display = 'none';
        document.getElementById('portal-key-created-modal').classList.add('active');
      })
      .catch(function(err) { createKeyError.textContent = err.message; createKeyError.style.display = 'block'; createKeySubmit.disabled = false; createKeySubmit.textContent = 'Create'; });
  });

  // Created modal
  var createdModal = document.getElementById('portal-key-created-modal');
  function closeCreatedModal() { createdModal.classList.remove('active'); }
  document.getElementById('portal-key-created-close').addEventListener('click', closeCreatedModal);
  document.getElementById('portal-key-created-done').addEventListener('click', closeCreatedModal);
  createdModal.addEventListener('click', function(e) { if (e.target === createdModal) closeCreatedModal(); });
  document.getElementById('portal-key-created-copy').addEventListener('click', function() {
    var val = document.getElementById('portal-key-created-value').textContent;
    navigator.clipboard.writeText(val).then(function() {
      document.getElementById('portal-key-created-copied').style.display = 'inline';
      setTimeout(function() { document.getElementById('portal-key-created-copied').style.display = 'none'; }, 2000);
    });
  });

  loadPortalKeys();
})();
