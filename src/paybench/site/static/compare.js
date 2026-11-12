/**
 * Side-by-side Oracle vs Naive trace scrubber.
 * Expects window.PAYBENCH_COMPARE = { task_id, instruction, naive, oracle }
 */
(function () {
  "use strict";

  function el(id) {
    return document.getElementById(id);
  }

  function maxSteps(data) {
    var a = (data.naive && data.naive.case_log) || [];
    var b = (data.oracle && data.oracle.case_log) || [];
    return Math.max(a.length, b.length, 1);
  }

  function renderColumn(containerId, ep, upto) {
    var box = el(containerId);
    box.innerHTML = "";
    if (!ep || !ep.case_log) {
      box.innerHTML = "<p class='lead'>No trace.</p>";
      return;
    }
    var slice = ep.case_log.slice(0, upto);
    slice.forEach(function (row) {
      var ok = row.result && row.result.ok;
      var err = row.result && row.result.error ? row.result.error.code : "";
      var fault = row.fault || "";
      var div = document.createElement("div");
      div.className =
        "step-row" + (ok ? "" : " step-fail") + (fault ? " step-fault" : "");
      div.innerHTML =
        '<span class="step-n">#' +
        row.step +
        '</span> <span class="mono">' +
        row.tool +
        "</span> " +
        (fault ? '<span class="fault-tag">' + fault + "</span>" : "") +
        (err && !ok ? '<span class="err-tag">' + err + "</span>" : "") +
        (ok === false && !err ? "" : "");
      box.appendChild(div);
    });
  }

  function renderOutcome(badgeId, ep) {
    var badge = el(badgeId);
    if (!ep) {
      badge.textContent = "—";
      return;
    }
    if (ep.success) {
      badge.textContent = "PASS";
      badge.className = "pill ok";
    } else {
      badge.textContent = "FAIL";
      badge.className = "pill bad";
    }
    var meta = el(badgeId + "-meta");
    if (meta) {
      var forbidden = (ep.forbidden_hit || []).join(", ") || "none";
      meta.textContent =
        "partial=" +
        (ep.partial != null ? Number(ep.partial).toFixed(2) : "?") +
        " · forbidden=[" +
        forbidden +
        "]";
    }
  }

  function highlightDiff(upto) {
    var note = el("diff-note");
    var data = window.PAYBENCH_COMPARE;
    var nLog = (data.naive.case_log || [])[upto - 1];
    var oLog = (data.oracle.case_log || [])[upto - 1];
    if (!nLog && !oLog) {
      note.textContent = "Drag the scrubber to walk both traces in lockstep.";
      return;
    }
    var parts = [];
    if (nLog && nLog.fault === "TIMEOUT_AFTER_COMMIT") {
      parts.push("Naive hits TIMEOUT_AFTER_COMMIT — money already moved.");
    }
    if (oLog && oLog.fault === "TIMEOUT_AFTER_COMMIT") {
      parts.push("Oracle hits the same ambiguous timeout.");
    }
    if (nLog && nLog.tool === "create_transfer" && nLog.result && nLog.result.ok && upto >= 2) {
      var prev = data.naive.case_log[upto - 2];
      if (prev && prev.fault === "TIMEOUT_AFTER_COMMIT") {
        parts.push("Naive retries without an idempotency key → second transfer (duplicate).");
      }
    }
    if (oLog && oLog.fault === "idempotent_replay") {
      parts.push("Oracle retries with the same key → idempotent_replay (one effect).");
    }
    if (oLog && oLog.tool === "verify_customer" && oLog.result && oLog.result.ok) {
      parts.push("Oracle verifies identity before moving money (P1).");
    }
    if (nLog && nLog.tool === "finish" && data.naive.success === false) {
      parts.push("Naive finishes but graders reject duplicate / missing verification.");
    }
    if (oLog && oLog.tool === "finish" && data.oracle.success) {
      parts.push("Oracle finishes resolved with exactly one transfer.");
    }
    note.textContent = parts.length
      ? parts.join(" ")
      : "Step " + upto + ": compare the tool choices side by side.";
  }

  function render(upto) {
    var data = window.PAYBENCH_COMPARE;
    el("scrubber-label").textContent = "Step " + upto + " / " + maxSteps(data);
    renderColumn("naive-log", data.naive, upto);
    renderColumn("oracle-log", data.oracle, upto);
    renderOutcome("naive-badge", data.naive);
    renderOutcome("oracle-badge", data.oracle);
    highlightDiff(upto);
  }

  document.addEventListener("DOMContentLoaded", function () {
    var data = window.PAYBENCH_COMPARE;
    if (!data) return;
    var scrubber = el("scrubber");
    var max = maxSteps(data);
    scrubber.min = "1";
    scrubber.max = String(max);
    scrubber.value = "1";
    scrubber.addEventListener("input", function () {
      render(parseInt(scrubber.value, 10));
    });
    el("btn-play").addEventListener("click", function () {
      var i = 1;
      scrubber.value = "1";
      render(1);
      var timer = setInterval(function () {
        i += 1;
        if (i > max) {
          clearInterval(timer);
          return;
        }
        scrubber.value = String(i);
        render(i);
      }, 650);
    });
    render(1);
  });
})();
