/**
 * Gasket Gateway — Code utilities
 *
 * 1. Copy-to-clipboard for <pre> blocks and API key displays
 * 2. Lightweight syntax highlighting for bash and YAML only (vanilla JS, no libs)
 */

(function () {
  "use strict";

  // ─── Copy to clipboard ──────────────────────────────────────────
  function addCopyButton(preEl) {
    var btn = document.createElement("button");
    btn.className = "copy-btn";
    btn.textContent = "Copy";
    btn.type = "button";
    btn.setAttribute("aria-label", "Copy code to clipboard");
    btn.addEventListener("click", function () {
      var code = preEl.querySelector("code");
      var text = (code || preEl).textContent;
      navigator.clipboard.writeText(text).then(function () {
        btn.textContent = "Copied!";
        btn.classList.add("copied");
        btn.setAttribute("aria-label", "Copied to clipboard");
        setTimeout(function () {
          btn.textContent = "Copy";
          btn.classList.remove("copied");
          btn.setAttribute("aria-label", "Copy code to clipboard");
        }, 2000);
      });
    });
    preEl.appendChild(btn);
  }

  // ─── Syntax highlighting (bash + YAML only) ────────────────────
  // Detects language from <code class="language-bash"> or data-lang attribute,
  // or auto-detects based on content patterns.

  function escapeHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  // Placeholder system to avoid double-wrapping
  var placeholders = [];
  function resetPlaceholders() { placeholders = []; }
  function placeholder(match, cls) {
    var idx = placeholders.length;
    placeholders.push('<span class="' + cls + '">' + match + "</span>");
    return "\x00PH" + idx + "PH\x00";
  }
  function restorePlaceholders(html) {
    return html.replace(/\x00PH(\d+)PH\x00/g, function (_, idx) {
      return placeholders[parseInt(idx, 10)];
    });
  }
  function applyRules(html, rules) {
    rules.forEach(function (rule) {
      html = html.replace(rule.re, function (m) {
        if (m.indexOf("\x00PH") !== -1) return m;
        return placeholder(m, rule.cls);
      });
    });
    return html;
  }

  // Bash rules
  var bashRules = [
    { re: /(#[^\n]*)/g,                         cls: "token-comment" },   // comments
    { re: /("(?:[^"\\]|\\.)*")/g,               cls: "token-string"  },   // double-quoted strings
    { re: /('(?:[^'\\]|\\.)*')/g,               cls: "token-string"  },   // single-quoted strings
    { re: /(\$[\w{}]+)/g,                        cls: "token-keyword" },   // variables like $HOME, ${VAR}
    { re: /(\$\s)/g,                             cls: "token-shell"   },   // shell prompt
    { re: /(--?\w[\w-]*)/g,                      cls: "token-flag"    },   // flags like -H, --output
    { re: /(https?:\/\/[^\s"'\\,]+)/g,           cls: "token-url"     },   // URLs
    { re: /\b(curl|docker|git|npm|npx|pip|sudo|bash|sh|echo|export|source|cd|ls|cat|grep|sed|awk|chmod|chown|mkdir|rm|cp|mv|kill|ps|systemctl|journalctl|gunicorn|flask|python|python3)\b/g, cls: "token-keyword" },
    { re: /([|;>&])/g,                           cls: "token-punct"   },   // pipe, semicolon, redirect
  ];

  // YAML rules
  var yamlRules = [
    { re: /(#[^\n]*)/g,                         cls: "token-comment" },   // comments
    { re: /("(?:[^"\\]|\\.)*")/g,               cls: "token-string"  },   // double-quoted strings
    { re: /('(?:[^'\\]|\\.)*')/g,               cls: "token-string"  },   // single-quoted strings
    { re: /\b(true|false|null|yes|no|on|off)\b/gi, cls: "token-keyword" },// booleans
    { re: /\b(\d+\.?\d*)\b/g,                   cls: "token-number"  },   // numbers
    { re: /^(\s*[\w.-]+)(?=\s*:)/gm,            cls: "token-property"},   // keys (word before colon)
    { re: /(---)/g,                              cls: "token-punct"   },   // document start
  ];

  function detectLang(codeEl) {
    // Check class e.g. class="language-bash"
    var cls = codeEl.className || "";
    if (/language-bash|language-sh|language-shell/i.test(cls)) return "bash";
    if (/language-ya?ml/i.test(cls)) return "yaml";
    // Check data attribute
    var lang = codeEl.getAttribute("data-lang") || "";
    if (/bash|sh|shell/i.test(lang)) return "bash";
    if (/ya?ml/i.test(lang)) return "yaml";
    // Auto-detect from content
    var text = codeEl.textContent;
    if (/^\s*\$\s/m.test(text) || /\bcurl\b/.test(text) || /\bdocker\b/.test(text)) return "bash";
    if (/^\s*[\w.-]+\s*:/m.test(text) && /^\s*-\s/m.test(text)) return "yaml";
    if (/^\s*---/m.test(text)) return "yaml";
    return null;
  }

  function highlightCode(codeEl) {
    var lang = detectLang(codeEl);
    if (!lang) return; // Only highlight bash and yaml

    var html = escapeHtml(codeEl.textContent);
    resetPlaceholders();

    if (lang === "bash") {
      html = applyRules(html, bashRules);
    } else if (lang === "yaml") {
      html = applyRules(html, yamlRules);
    }

    codeEl.innerHTML = restorePlaceholders(html);
  }

  // ─── Init on DOM ready ──────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", function () {
    // Copy buttons on all <pre> blocks
    document.querySelectorAll("pre").forEach(addCopyButton);

    // Copy button on API key displays
    document.querySelectorAll(".api-key-display").forEach(function (el) {
      if (el.querySelector(".api-key-copy")) return;
      var btn = document.createElement("button");
      btn.className = "api-key-copy";
      btn.textContent = "Copy";
      btn.type = "button";
      btn.setAttribute("aria-label", "Copy API key to clipboard");
      btn.addEventListener("click", function () {
        var valEl = el.querySelector(".api-key-value");
        var text = valEl.dataset.realValue || valEl.textContent;
        navigator.clipboard.writeText(text).then(function () {
          btn.textContent = "Copied!";
          btn.classList.add("copied");
          setTimeout(function () {
            btn.textContent = "Copy";
            btn.classList.remove("copied");
          }, 2000);
        });
      });
      el.appendChild(btn);
    });

    // Syntax highlighting on all <pre><code> blocks
    document.querySelectorAll("pre code").forEach(highlightCode);
  });
})();
