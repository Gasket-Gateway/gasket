/**
 * portal_profiles.js — Portal profiles + policy acceptance logic.
 */
(function() {
  "use strict";

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  var currentAcceptPolicyId = null;
  var currentAcceptProfileId = null;

  function loadPortalProfiles() {
    var loading = document.getElementById('portal-profiles-loading');
    var empty = document.getElementById('portal-profiles-empty');
    var container = document.getElementById('portal-profiles');
    loading.style.display = 'block'; empty.style.display = 'none'; container.style.display = 'none'; container.innerHTML = '';

    fetch('/api/profiles')
      .then(function(r) { return r.json(); })
      .then(function(profiles) {
        loading.style.display = 'none';
        if (profiles.length === 0) { empty.style.display = 'block'; return; }
        container.style.display = 'block';

        var checkPromises = profiles.map(function(p) {
          return fetch('/admin/api/policies/acceptances/check/' + p.id)
            .then(function(r2) { return r2.json(); })
            .then(function(status) { return { profile: p, policies: status }; });
        });

        Promise.all(checkPromises).then(function(results) {
          results.forEach(function(result) {
            var p = result.profile;
            var ps = result.policies;
            var card = document.createElement('div');
            card.className = 'card'; card.style.marginBottom = 'var(--space-md)';

            var hasPolicies = (ps.accepted && ps.accepted.length > 0) || (ps.pending && ps.pending.length > 0);

            var headerHtml = '<div class="card-header" style="display:flex;align-items:center;justify-content:space-between;">' +
              '<div><strong>' + escapeHtml(p.name) + '</strong>' +
              (p.source === 'config' ? ' <span class="badge badge-info" style="font-size:0.65rem;">config</span>' : '') +
              '</div><div>' +
              (ps.all_accepted
                ? '<span class="badge badge-success" style="font-size:0.7rem;">✓ All policies accepted</span>'
                : (hasPolicies ? '<span class="badge badge-warning" style="font-size:0.7rem;">⚠ Policies pending</span>' : '<span class="badge badge-success" style="font-size:0.7rem;">✓ No policies required</span>')) +
              '</div></div>';

            var bodyHtml = '<div class="card-body">';
            if (p.description) bodyHtml += '<p class="text-muted" style="font-size:0.85rem;margin-bottom:var(--space-md);">' + escapeHtml(p.description) + '</p>';

            if (hasPolicies) {
              bodyHtml += '<div style="margin-bottom:var(--space-sm);">';
              bodyHtml += '<p style="font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;color:var(--text-muted);margin-bottom:var(--space-xs);font-weight:600;">Policies</p>';
              if (ps.accepted && ps.accepted.length > 0) {
                ps.accepted.forEach(function(ap) {
                  bodyHtml += '<div style="display:flex;align-items:center;gap:var(--space-sm);margin-bottom:var(--space-xs);">' +
                    '<span class="status-dot status-connected" style="flex-shrink:0;"></span>' +
                    '<span style="font-size:0.85rem;">' + escapeHtml(ap.policy_name) + ' (v' + ap.version_number + ')</span>' +
                    '<span class="text-muted" style="font-size:0.75rem;">accepted ' + (ap.accepted_at ? new Date(ap.accepted_at).toLocaleDateString() : '') + '</span></div>';
                });
              }
              if (ps.pending && ps.pending.length > 0) {
                ps.pending.forEach(function(pp) {
                  var btnId = 'accept-' + p.id + '-' + pp.policy_id;
                  bodyHtml += '<div style="display:flex;align-items:center;gap:var(--space-sm);margin-bottom:var(--space-xs);">' +
                    '<span class="status-dot status-error" style="flex-shrink:0;"></span>' +
                    '<span style="font-size:0.85rem;">' + escapeHtml(pp.policy_name) + '</span>' +
                    '<button class="btn btn-primary btn-sm" style="font-size:0.7rem;padding:2px 8px;" id="' + btnId + '" data-policy-id="' + pp.policy_id + '" data-profile-id="' + p.id + '">Review & Accept</button></div>';
                });
              }
              bodyHtml += '</div>';
            }
            bodyHtml += '</div>';

            var footerHtml = '<div class="card-footer" style="display:flex;gap:var(--space-xs);align-items:center;">' +
              '<span class="text-muted" style="font-size:0.8rem;">Backends: ' + (p.backend_names && p.backend_names.length > 0 ? escapeHtml(p.backend_names.join(', ')) : 'None') + '</span>' +
              '<span style="flex:1;"></span>' +
              '<span class="text-muted" style="font-size:0.8rem;">Max ' + p.max_keys_per_user + ' keys</span></div>';

            card.innerHTML = headerHtml + bodyHtml + footerHtml;
            container.appendChild(card);

            if (ps.pending && ps.pending.length > 0) {
              ps.pending.forEach(function(pp) {
                var btn = document.getElementById('accept-' + p.id + '-' + pp.policy_id);
                if (btn) btn.addEventListener('click', function() { openPolicyAcceptModal(pp.policy_id, p.id); });
              });
            }
          });
        });
      })
      .catch(function() { loading.style.display = 'none'; empty.style.display = 'block'; });
  }

  // Policy acceptance modal
  var modal = document.getElementById('portal-policy-modal');
  var acceptBtn = document.getElementById('portal-policy-accept');
  var acceptError = document.getElementById('portal-policy-error');

  function openPolicyAcceptModal(policyId, profileId) {
    currentAcceptPolicyId = policyId;
    currentAcceptProfileId = profileId;
    acceptError.style.display = 'none';
    acceptBtn.disabled = false;
    acceptBtn.textContent = 'I Accept';
    fetch('/api/policies/' + policyId)
      .then(function(r) { return r.json(); })
      .then(function(d) {
        document.getElementById('portal-policy-name').textContent = d.name + (d.current_version ? ' (v' + d.current_version + ')' : '');
        document.getElementById('portal-policy-desc').textContent = d.description || '';
        document.getElementById('portal-policy-content').textContent = d.current_content || 'No content available.';
        modal.classList.add('active');
      })
      .catch(function() { alert('Failed to load policy details.'); });
  }

  function closeModal() { modal.classList.remove('active'); currentAcceptPolicyId = null; currentAcceptProfileId = null; }
  document.getElementById('portal-policy-modal-close').addEventListener('click', closeModal);
  document.getElementById('portal-policy-cancel').addEventListener('click', closeModal);
  modal.addEventListener('click', function(e) { if (e.target === modal) closeModal(); });

  acceptBtn.addEventListener('click', function() {
    if (!currentAcceptPolicyId || !currentAcceptProfileId) return;
    acceptBtn.disabled = true; acceptBtn.textContent = 'Accepting…'; acceptError.style.display = 'none';
    fetch('/admin/api/policies/' + currentAcceptPolicyId + '/accept', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ profile_id: currentAcceptProfileId })
    })
      .then(function(res) { if (!res.ok) return res.json().then(function(d) { throw new Error(d.error || 'Accept failed'); }); return res.json(); })
      .then(function() { closeModal(); loadPortalProfiles(); })
      .catch(function(err) { acceptError.textContent = err.message; acceptError.style.display = 'block'; acceptBtn.disabled = false; acceptBtn.textContent = 'I Accept'; });
  });

  loadPortalProfiles();
})();
