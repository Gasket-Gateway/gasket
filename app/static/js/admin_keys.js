/**
 * admin_keys.js — Admin API Keys management page logic.
 */
(function() {
  "use strict";
  var G = window.GasketAdmin;

  var snapshotsModal = document.getElementById('admin-key-snapshots-modal');
  G.bindModalClose(snapshotsModal, ['admin-key-snapshots-close', 'admin-key-snapshots-done']);

  function openSnapshotsModal(keyId, keyName) {
    document.getElementById('admin-key-snapshots-title').textContent = 'Policy Snapshots — ' + keyName;
    var content = document.getElementById('admin-key-snapshots-content');
    content.innerHTML = '<p class="text-muted" style="font-size:0.85rem;">Loading…</p>';
    G.openModal(snapshotsModal);
    fetch('/admin/api/keys/' + keyId + '/policies')
      .then(function(r) { return r.json(); })
      .then(function(snapshots) {
        if (snapshots.length === 0) { content.innerHTML = '<p class="text-muted" style="font-size:0.85rem;">No policy snapshots recorded for this key.</p>'; return; }
        var html = '<table class="table" style="font-size:0.85rem;"><thead><tr><th>Policy</th><th>Version</th></tr></thead><tbody>';
        snapshots.forEach(function(s) { html += '<tr><td>' + G.escapeHtml(s.policy_name || '—') + '</td><td>v' + s.version_number + '</td></tr>'; });
        html += '</tbody></table>';
        content.innerHTML = html;
      })
      .catch(function() { content.innerHTML = '<p class="text-danger" style="font-size:0.85rem;">Failed to load snapshots.</p>'; });
  }

  function loadAdminKeys() {
    var loading = document.getElementById('admin-keys-loading');
    var empty = document.getElementById('admin-keys-empty');
    var wrapper = document.getElementById('admin-keys-table-wrapper');
    var tbody = document.getElementById('admin-keys-tbody');
    loading.style.display = 'block'; empty.style.display = 'none'; wrapper.style.display = 'none';

    var userFilter = document.getElementById('admin-keys-user-filter').value.trim();
    var profileFilter = document.getElementById('admin-keys-profile-filter').value;
    var params = [];
    if (userFilter) params.push('user=' + encodeURIComponent(userFilter));
    if (profileFilter) params.push('profile_id=' + profileFilter);
    var url = '/admin/api/keys' + (params.length ? '?' + params.join('&') : '');

    fetch(url)
      .then(function(r) { return r.json(); })
      .then(function(keys) {
        loading.style.display = 'none'; tbody.innerHTML = '';
        if (keys.length === 0) { empty.style.display = 'block'; return; }
        wrapper.style.display = 'block';
        keys.forEach(function(k) {
          var tr = document.createElement('tr');
          tr.innerHTML =
            '<td>' + G.escapeHtml(k.user_email) + '</td>' +
            '<td><strong>' + G.escapeHtml(k.name) + '</strong></td>' +
            '<td><code style="font-size:0.8rem;">' + G.escapeHtml(k.key_preview) + '</code></td>' +
            '<td><span class="badge badge-outline" style="font-size:0.7rem;">' + G.escapeHtml(k.profile_name || '—') + '</span></td>' +
            '<td>' + G.getKeyStatusBadge(k) + '</td>' +
            '<td><span class="text-muted" style="font-size:0.8rem;">' + (k.expires_at ? new Date(k.expires_at).toLocaleDateString() : '—') + '</span></td>' +
            '<td><span class="text-muted" style="font-size:0.8rem;">' + (k.created_at ? new Date(k.created_at).toLocaleDateString() : '—') + '</span></td>' +
            '<td style="text-align:right;"><div style="display:flex;gap:var(--space-xs);justify-content:flex-end;"></div></td>';
          var actionsCell = tr.querySelector('td:last-child div');

          var snapBtn = document.createElement('button');
          snapBtn.className = 'btn btn-outline btn-sm'; snapBtn.textContent = '📋'; snapBtn.title = 'View policy snapshots'; snapBtn.style.fontSize = '0.7rem';
          snapBtn.addEventListener('click', function() { openSnapshotsModal(k.id, k.name); });
          actionsCell.appendChild(snapBtn);

          if (k.revoked) {
            var restoreBtn = document.createElement('button');
            restoreBtn.className = 'btn btn-primary btn-sm'; restoreBtn.textContent = 'Restore'; restoreBtn.style.fontSize = '0.7rem';
            if (k.is_expired) { restoreBtn.disabled = true; restoreBtn.title = 'Cannot restore expired keys'; }
            restoreBtn.addEventListener('click', function() {
              restoreBtn.disabled = true; restoreBtn.textContent = '…';
              fetch('/admin/api/keys/' + k.id + '/restore', { method: 'POST' })
                .then(function(res) { if (!res.ok) return res.json().then(function(d) { throw new Error(d.error); }); loadAdminKeys(); })
                .catch(function(err) { alert('Restore failed: ' + err.message); restoreBtn.disabled = false; restoreBtn.textContent = 'Restore'; });
            });
            actionsCell.appendChild(restoreBtn);
          } else {
            var revokeBtn = document.createElement('button');
            revokeBtn.className = 'btn btn-danger btn-sm'; revokeBtn.textContent = 'Revoke'; revokeBtn.style.fontSize = '0.7rem';
            revokeBtn.addEventListener('click', function() {
              revokeBtn.disabled = true; revokeBtn.textContent = '…';
              fetch('/admin/api/keys/' + k.id + '/revoke', { method: 'POST' })
                .then(function(res) { if (!res.ok) return res.json().then(function(d) { throw new Error(d.error); }); loadAdminKeys(); })
                .catch(function(err) { alert('Revoke failed: ' + err.message); revokeBtn.disabled = false; revokeBtn.textContent = 'Revoke'; });
            });
            actionsCell.appendChild(revokeBtn);
          }
          tbody.appendChild(tr);
        });
      })
      .catch(function() { loading.style.display = 'none'; empty.style.display = 'block'; });
  }

  function populateAdminKeysProfileFilter() {
    var select = document.getElementById('admin-keys-profile-filter');
    var current = select.value;
    fetch('/admin/api/profiles')
      .then(function(r) { return r.json(); })
      .then(function(profiles) {
        select.innerHTML = '<option value="">All profiles</option>';
        profiles.forEach(function(p) {
          var opt = document.createElement('option');
          opt.value = p.id; opt.textContent = p.name;
          if (String(p.id) === current) opt.selected = true;
          select.appendChild(opt);
        });
      });
  }

  var adminKeysFilterTimeout = null;
  document.getElementById('admin-keys-user-filter').addEventListener('input', function() {
    clearTimeout(adminKeysFilterTimeout);
    adminKeysFilterTimeout = setTimeout(loadAdminKeys, 300);
  });
  document.getElementById('admin-keys-profile-filter').addEventListener('change', loadAdminKeys);
  document.getElementById('btn-refresh-keys').addEventListener('click', loadAdminKeys);

  populateAdminKeysProfileFilter();
  loadAdminKeys();
})();
