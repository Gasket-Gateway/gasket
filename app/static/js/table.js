/**
 * Gasket Gateway — Interactive table utilities
 *
 * 1. Column sorting (string, number, date) via header clicks
 * 2. Separate text search on Key Name (col 0) and Backend Profile (col 1)
 * 3. Multi-select status filter via toggle chips
 */

(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var table = document.getElementById("demo-table");
    if (!table) return;

    var thead = table.querySelector("thead");
    var tbody = table.querySelector("tbody");
    var searchKey = document.getElementById("table-search-key");
    var searchBackend = document.getElementById("table-search-backend");
    var statusChips = document.querySelectorAll(".status-chip");
    var resultCount = document.getElementById("table-result-count");

    // ─── Sort state ───────────────────────────────────────────────
    var sortCol = -1;
    var sortDir = 1; // 1 = asc, -1 = desc

    function getSortValue(td, type) {
      var raw = td.getAttribute("data-sort-value");
      if (raw !== null) {
        if (type === "number") return parseFloat(raw) || 0;
        if (type === "date") return raw; // ISO string sorts lexicographically
        return raw.toLowerCase();
      }
      var text = td.textContent.trim().toLowerCase();
      if (type === "number") return parseFloat(text.replace(/,/g, "")) || 0;
      return text;
    }

    function sortTable(colIdx, type) {
      if (sortCol === colIdx) {
        sortDir *= -1;
      } else {
        sortCol = colIdx;
        sortDir = 1;
      }

      var rows = Array.from(tbody.querySelectorAll("tr"));
      rows.sort(function (a, b) {
        var aVal = getSortValue(a.cells[colIdx], type);
        var bVal = getSortValue(b.cells[colIdx], type);
        if (aVal < bVal) return -1 * sortDir;
        if (aVal > bVal) return 1 * sortDir;
        return 0;
      });

      rows.forEach(function (row) { tbody.appendChild(row); });
      updateSortIndicators();
      applyFilters();
    }

    function updateSortIndicators() {
      thead.querySelectorAll("th[data-col]").forEach(function (th) {
        th.classList.remove("sort-asc", "sort-desc");
        if (parseInt(th.getAttribute("data-col"), 10) === sortCol) {
          th.classList.add(sortDir === 1 ? "sort-asc" : "sort-desc");
        }
      });
    }

    // Click handler on sortable headers
    thead.querySelectorAll("th[data-col]").forEach(function (th) {
      th.addEventListener("click", function () {
        var col = parseInt(th.getAttribute("data-col"), 10);
        var type = th.getAttribute("data-type") || "string";
        sortTable(col, type);
      });
    });

    // ─── Status chip toggles ──────────────────────────────────────
    statusChips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        chip.classList.toggle("active");
        var isActive = chip.classList.contains("active");
        chip.setAttribute("aria-pressed", isActive ? "true" : "false");
        applyFilters();
      });
    });

    // ─── Search & Filter ──────────────────────────────────────────
    function getActiveStatuses() {
      var active = [];
      statusChips.forEach(function (chip) {
        if (chip.classList.contains("active")) {
          active.push(chip.getAttribute("data-status"));
        }
      });
      return active;
    }

    function applyFilters() {
      var keyQuery = (searchKey ? searchKey.value : "").trim().toLowerCase();
      var backendQuery = (searchBackend ? searchBackend.value : "").trim().toLowerCase();
      var activeStatuses = getActiveStatuses();
      var rows = Array.from(tbody.querySelectorAll("tr"));
      var visible = 0;

      rows.forEach(function (row) {
        var cells = row.cells;
        var keyName = cells[0].textContent.trim().toLowerCase();
        var backend = cells[1].textContent.trim().toLowerCase();
        var rowStatus = cells[5].textContent.trim();

        var matchesKey = !keyQuery || keyName.indexOf(keyQuery) !== -1;
        var matchesBackend = !backendQuery || backend.indexOf(backendQuery) !== -1;
        var matchesStatus = activeStatuses.length === 0 || activeStatuses.indexOf(rowStatus) !== -1;

        if (matchesKey && matchesBackend && matchesStatus) {
          row.style.display = "";
          visible++;
        } else {
          row.style.display = "none";
        }
      });

      if (resultCount) {
        var total = rows.length;
        var countText = visible === total
          ? String(total)
          : visible + " of " + total;
        resultCount.innerHTML = 'Rows: <span class="result-pill">' + countText + '</span>';
      }
    }

    if (searchKey) searchKey.addEventListener("input", applyFilters);
    if (searchBackend) searchBackend.addEventListener("input", applyFilters);

    // Initial count
    applyFilters();
  });
})();
