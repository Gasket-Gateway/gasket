/**
 * admin_status.js — Connection Status page logic.
 */
(function() {
  "use strict";
  var G = window.GasketAdmin;

  // ─── Error modal ───
  var modal = document.getElementById('error-detail-modal');
  var modalService = document.getElementById('error-modal-service');
  var modalDetail = document.getElementById('error-modal-detail');
  var modalTitle = document.getElementById('error-modal-title');
  var modalRecheckBtn = document.getElementById('error-modal-recheck');
  var currentModalServiceKey = null;
  var currentModalServiceName = null;

  function openErrorModal(serviceKey, serviceName, detail, latencyMs) {
    currentModalServiceKey = serviceKey;
    currentModalServiceName = serviceName;
    modalTitle.textContent = serviceName + ' — Connection Error';
    modalService.innerHTML = 'Service <strong>' + serviceName + '</strong> failed its health check.';
    modalDetail.textContent = detail || 'Unknown error';
    var modalLatency = document.getElementById('error-modal-latency');
    if (modalLatency) modalLatency.textContent = G.formatLatency(latencyMs || 0);
    modalRecheckBtn.disabled = false;
    modalRecheckBtn.textContent = 'Recheck';
    G.openModal(modal);
  }

  function closeErrorModal() {
    G.closeModal(modal);
    document.querySelector('#error-detail-modal .modal').classList.remove('modal-expanded');
    currentModalServiceKey = null;
    currentModalServiceName = null;
  }

  document.getElementById('error-modal-close').addEventListener('click', closeErrorModal);
  modal.addEventListener('click', function(e) {
    if (e.target === modal) closeErrorModal();
  });

  document.getElementById('error-modal-expand').addEventListener('click', function() {
    document.querySelector('#error-detail-modal .modal').classList.toggle('modal-expanded');
  });

  modalRecheckBtn.addEventListener('click', function() {
    if (!currentModalServiceKey) return;
    recheckService(currentModalServiceKey, currentModalServiceName, true);
  });

  // ─── Recheck a single service ───
  function recheckService(serviceKey, serviceName, fromModal) {
    var cardId = 'status-card-' + serviceKey;
    var card = document.getElementById(cardId);

    if (card) resetCardToChecking(card);

    if (fromModal) {
      modalRecheckBtn.disabled = true;
      modalRecheckBtn.textContent = 'Checking…';
    }

    fetch('/admin/api/status/' + encodeURIComponent(serviceKey))
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (card) updateCard(card, serviceKey, serviceName, data.status, data.detail, data.latency_ms);
        if (fromModal) {
          if (data.status === 'connected') {
            closeErrorModal();
          } else {
            modalDetail.textContent = data.detail || 'Unknown error';
            var modalLatency = document.getElementById('error-modal-latency');
            if (modalLatency) modalLatency.textContent = G.formatLatency(data.latency_ms || 0);
            modalRecheckBtn.disabled = false;
            modalRecheckBtn.textContent = 'Recheck';
          }
        }
      })
      .catch(function() {
        if (card) updateCard(card, serviceKey, serviceName, 'error', 'Failed to fetch status', 0);
        if (fromModal) {
          modalRecheckBtn.disabled = false;
          modalRecheckBtn.textContent = 'Recheck';
        }
      });
  }

  // ─── Reset card to checking state ───
  function resetCardToChecking(card) {
    var dot = card.querySelector('.status-dot');
    var detailText = card.querySelector('.status-detail-text');
    var actions = card.querySelector('.status-card-actions');
    if (dot) dot.className = 'status-dot status-checking';
    if (detailText) {
      detailText.className = 'text-muted mt-sm status-detail-text';
      detailText.style.fontSize = '0.8rem';
      detailText.textContent = 'Checking…';
    }
    if (actions) actions.remove();
  }

  // ─── Update a card with results ───
  function updateCard(card, serviceKey, serviceName, status, detail, latencyMs) {
    var dot = card.querySelector('.status-dot');
    var detailText = card.querySelector('.status-detail-text');

    if (dot) {
      dot.className = 'status-dot';
      dot.classList.add(status === 'connected' ? 'status-connected' : 'status-error');
    }

    if (detailText) {
      detailText.classList.remove('text-muted', 'text-danger');
      if (status === 'connected') {
        detailText.classList.add('text-muted');
        detailText.textContent = G.formatLatency(latencyMs);
      } else {
        detailText.classList.add('text-danger');
        detailText.textContent = 'Error — ' + G.formatLatency(latencyMs);
      }
    }

    var oldActions = card.querySelector('.status-card-actions');
    if (oldActions) oldActions.remove();

    var cardBody = card.querySelector('.card-body');
    var actionsDiv = document.createElement('div');
    actionsDiv.className = 'status-card-actions mt-sm';
    actionsDiv.style.display = 'flex';
    actionsDiv.style.gap = 'var(--space-xs)';
    actionsDiv.style.justifyContent = 'center';

    var recheckBtn = document.createElement('button');
    recheckBtn.className = 'btn btn-outline btn-sm';
    recheckBtn.textContent = 'Recheck';
    recheckBtn.style.fontSize = '0.7rem';
    recheckBtn.addEventListener('click', function() {
      recheckService(serviceKey, serviceName, false);
    });
    actionsDiv.appendChild(recheckBtn);

    if (status !== 'connected') {
      var errorBtn = document.createElement('button');
      errorBtn.className = 'btn btn-danger btn-sm';
      errorBtn.textContent = 'View Error';
      errorBtn.style.fontSize = '0.7rem';
      errorBtn.addEventListener('click', function() {
        openErrorModal(serviceKey, serviceName, detail, latencyMs);
      });
      actionsDiv.appendChild(errorBtn);
    }

    cardBody.appendChild(actionsDiv);
  }

  // ─── Create a backend card ───
  function createBackendCard(backend) {
    var card = document.createElement('div');
    card.className = 'card';
    card.id = 'status-card-' + backend.name;
    card.setAttribute('data-service', backend.name);
    card.setAttribute('data-service-name', backend.name);

    card.innerHTML =
      '<div class="card-body text-center">' +
        '<div class="status-indicator" style="justify-content: center;">' +
          '<span class="status-dot status-checking"></span>' +
          '<span>' + G.escapeHtml(backend.name) + '</span>' +
        '</div>' +
        '<p class="text-muted mt-sm status-detail-text" style="font-size:0.8rem;">Checking…</p>' +
      '</div>';

    updateCard(card, backend.name, backend.name, backend.status, backend.detail, backend.latency_ms || 0);
    return card;
  }

  // ─── Fetch all connection statuses ───
  var coreServiceNames = {
    postgresql: 'PostgreSQL',
    oidc: 'OIDC Provider',
    opensearch: 'OpenSearch'
  };

  function fetchAllStatuses() {
    Object.keys(coreServiceNames).forEach(function(svc) {
      var card = document.getElementById('status-card-' + svc);
      if (card) resetCardToChecking(card);
    });

    fetch('/admin/api/status')
      .then(function(res) { return res.json(); })
      .then(function(data) {
        Object.keys(coreServiceNames).forEach(function(svc) {
          if (data[svc]) {
            var card = document.getElementById('status-card-' + svc);
            if (card) updateCard(card, svc, coreServiceNames[svc], data[svc].status, data[svc].detail, data[svc].latency_ms);
          }
        });

        var container = document.getElementById('openai-backends-status');
        container.innerHTML = '';
        if (data.openai_backends && data.openai_backends.length > 0) {
          var heading = document.createElement('h3');
          heading.textContent = 'OpenAI Backends';
          heading.style.marginBottom = 'var(--space-md)';
          container.appendChild(heading);

          var grid = document.createElement('div');
          grid.className = 'grid grid-4';
          data.openai_backends.forEach(function(backend) {
            grid.appendChild(createBackendCard(backend));
          });
          container.appendChild(grid);
        }
      })
      .catch(function() {
        Object.keys(coreServiceNames).forEach(function(svc) {
          var card = document.getElementById('status-card-' + svc);
          if (card) updateCard(card, svc, coreServiceNames[svc], 'error', 'Failed to fetch status from /admin/api/status', 0);
        });
      });
  }

  fetchAllStatuses();
  document.getElementById('btn-check-all-status').addEventListener('click', fetchAllStatuses);
})();
