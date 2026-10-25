/* Minimal progressive enhancement. The pages work without JavaScript; this adds:
   - the copy button (patient ID / invitation code) with an aria-live confirmation,
   - closing the circle menu (a native <details>) with Escape or a click/tap outside it (F-20). */
(function () {
  "use strict";

  function announce(statusEl, message) {
    if (!statusEl) return;
    statusEl.textContent = message;
    window.setTimeout(function () { statusEl.textContent = ""; }, 4000);
  }

  function fallbackCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.className = "visually-hidden";
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-copy-target]");
    if (!button) return;
    var source = document.getElementById(button.getAttribute("data-copy-target"));
    var status = document.getElementById(button.getAttribute("data-copy-status"));
    if (!source) return;
    var text = source.textContent.trim();
    var done = function (ok) { announce(status, ok ? "Copied" : "Could not copy. Select the text and copy it yourself."); };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(fallbackCopy(text)); });
    } else {
      done(fallbackCopy(text));
    }
  });

  // The circle menu is a native <details>, which does not close by itself.
  function openMenus() { return document.querySelectorAll("nav details[open]"); }
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    Array.prototype.forEach.call(openMenus(), function (d) {
      d.removeAttribute("open");
      var summary = d.querySelector("summary");
      if (summary) summary.focus();
    });
  });
  document.addEventListener("click", function (event) {
    Array.prototype.forEach.call(openMenus(), function (d) { if (!d.contains(event.target)) d.removeAttribute("open"); });
  });

  // --- bigger words: a per-browser reading aid on the child view; nothing is sent anywhere
  var BIGGER_KEY = "fcc-bigger-words";
  function biggerOn() { try { return window.localStorage.getItem(BIGGER_KEY) === "1"; } catch (e) { return false; } }
  function applyBigger(on, button) {
    document.documentElement.classList.toggle("bigger-words", on);
    if (button) { button.setAttribute("aria-pressed", on ? "true" : "false"); }
  }
  var biggerButton = document.querySelector("[data-bigger-words]");
  if (biggerButton) {
    applyBigger(biggerOn(), biggerButton);
    biggerButton.addEventListener("click", function () {
      var on = !document.documentElement.classList.contains("bigger-words");
      applyBigger(on, biggerButton);
      try { window.localStorage.setItem(BIGGER_KEY, on ? "1" : "0"); } catch (e) { /* storage blocked: still works for this page */ }
    });
  }
  // --- end bigger words

  // Polling: while a note is "queued" or "running", ask the status endpoint and reload when it finishes.
  // Without JavaScript the page still shows the state and a Refresh link. Only textContent is used to change the page (no HTML is ever built from data).
  var poller = document.querySelector("[data-poll-url]");
  if (poller && window.fetch) {
    var pollUrl = poller.getAttribute("data-poll-url");
    var state = poller.getAttribute("data-poll-state");
    var labels = { queued: "Waiting in line to be prepared\u2026", running: "Being prepared now\u2026" };
    var delay = 3000;
    var tick = function () {
      fetch(pollUrl, { credentials: "same-origin", headers: { Accept: "application/json" } })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
          if (data && data.state && data.state !== state) {
            if (data.state === "done" || data.state === "failed" || data.state === "none") { window.location.reload(); return; }
            state = data.state;
            var label = poller.querySelector("[data-poll-label]");
            if (label && labels[state]) { label.textContent = labels[state]; }
          }
          delay = Math.min(delay + 1000, 12000);
          window.setTimeout(tick, delay);
        })
        .catch(function () { delay = Math.min(delay * 2, 30000); window.setTimeout(tick, delay); });
    };
    window.setTimeout(tick, delay);
  }

  // Buttons that only make sense with JavaScript stay hidden until it runs.
  Array.prototype.forEach.call(document.querySelectorAll("[data-needs-js]"), function (el) { el.hidden = false; });
})();
