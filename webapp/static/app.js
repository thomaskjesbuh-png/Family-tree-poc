/* Ancestor Finder front end: search, review, decide, report. No framework. */
(() => {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const form = $("#search"), list = $("#list"), statusEl = $("#status"), intro = $("#intro");
  const tray = $("#tray"), tpl = $("#card-t");
  const PART_LABEL = { "given name": "First name", surname: "Surname", "birth year": "Birth year", place: "Place", family: "Family" };

  let current = null;            // last search response
  let decisions = {};            // record_id -> {status, confidence, reasons}

  const store = {
    key(q) { return "af:" + JSON.stringify([q.given_name, q.surname, q.birth_year, q.birthplace]); },
    load(q) { try { return JSON.parse(localStorage.getItem(this.key(q)) || "{}"); } catch { return {}; } },
    save(q, d) { try { localStorage.setItem(this.key(q), JSON.stringify(d)); } catch { /* private mode */ } },
  };

  function formData() {
    const d = Object.fromEntries(new FormData(form).entries());
    for (const k of Object.keys(d)) d[k] = d[k].trim();
    return d;
  }

  function show(msg, kind = "info") {
    statusEl.hidden = !msg;
    statusEl.className = "status " + kind;
    statusEl.textContent = msg || "";
  }

  async function search(ev) {
    ev && ev.preventDefault();
    const q = formData();
    if (!q.given_name || !q.birth_year) { show("Enter at least a first name and an approximate birth year.", "error"); return; }
    $("#go").disabled = true; $("#go").textContent = "Searching…";
    show(""); list.innerHTML = "";
    try {
      const res = await fetch("/api/search", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(q) });
      const data = await res.json();
      if (!res.ok) { show(data.error || "Something went wrong.", data.kind === "privacy" ? "privacy" : "error"); return; }
      current = data;
      decisions = store.load(data.query);
      intro.hidden = true;
      render();
    } catch (e) {
      show("Could not reach the search service. Is it running?", "error");
    } finally {
      $("#go").disabled = false; $("#go").textContent = "Search the censuses";
    }
  }

  function render() {
    const c = current;
    list.innerHTML = "";
    if (!c.candidates.length) {
      show("No matching record found in the censuses searched. Nothing is claimed. Try a wider birth-year range, another spelling, or leave out the birthplace.", "info");
    } else {
      const more = c.total > c.shown ? ` (best ${c.shown} of ${c.total} shown)` : "";
      const highs = c.candidates.filter(x => x.confidence === "high").length;
      show(`${c.total} possible record${c.total === 1 ? "" : "s"}${more}. ${highs ? highs + " rated high." : "None rated high, so check the family details carefully."}`, "info");
    }
    for (const cand of c.candidates) list.appendChild(card(cand));
    updateTray();
  }

  function card(x) {
    const el = tpl.content.firstElementChild.cloneNode(true);
    el.dataset.id = x.record_id;
    $(".rank", el).textContent = "#" + x.rank;
    $(".name", el).textContent = x.record_name || "(no name)";
    const place = [x.farm, x.municipality].filter(Boolean).join(", ");
    $(".meta", el).textContent = `${x.year} census · ${place || "place not given"} · born ${x.birth_year_in_record ?? "?"}${x.birthplace ? " in " + x.birthplace : ""}`;
    const badge = $(".badge", el);
    badge.textContent = x.confidence[0].toUpperCase() + x.confidence.slice(1);
    badge.classList.add(x.confidence);
    $(".score", el).textContent = Math.round(x.score * 100) + "%";

    const ul = $(".reasons", el);
    for (const p of x.explanation) {
      const li = document.createElement("li");
      li.className = p.score >= 0.9 ? "ok" : p.score >= 0.6 ? "part" : "bad";
      li.innerHTML = `<span class="lab"></span><span class="txt"></span>`;
      $(".lab", li).textContent = PART_LABEL[p.name] || p.name;
      $(".txt", li).textContent = p.explanation;
      ul.appendChild(li);
    }
    if (x.judge) {
      const li = document.createElement("li");
      li.className = x.judge.verdict === "same" ? "ok" : x.judge.verdict === "different" ? "bad" : "part";
      li.innerHTML = `<span class="lab">Model check</span><span class="txt"></span>`;
      $(".txt", li).textContent = `${x.judge.verdict}: ${(x.judge.reasons || []).join("; ")}`;
      ul.appendChild(li);
    }
    const notes = $(".notes", el);
    for (const n of x.notes) { const li = document.createElement("li"); li.textContent = n; notes.appendChild(li); }

    const tb = $("tbody", el);
    const hh = x.household && x.household.length ? x.household : [];
    if (hh.length <= 1) {
      $(".house", el).innerHTML = "<h4>Listed at the same place</h4><p class='muted'>No other people listed with this record.</p>";
    } else {
      for (const h of hh) {
        const tr = document.createElement("tr");
        if (h.record_id === x.record_id) tr.className = "me";
        for (const v of [h.name, h.birth_year ?? "?", h.role || ""]) { const td = document.createElement("td"); td.textContent = v; tr.appendChild(td); }
        tb.appendChild(tr);
      }
    }

    $(".cite", el).textContent = x.source;
    const open = $(".open", el);
    if (x.link) open.href = x.link; else { open.removeAttribute("href"); open.classList.add("disabled"); open.textContent = x.demo ? "Demo record, no source" : "No link"; open.setAttribute("aria-disabled", "true"); }

    $(".yes", el).addEventListener("click", () => decide(x, "confirmed"));
    $(".no", el).addEventListener("click", () => decide(x, "rejected"));
    paint(el, decisions[x.record_id]);
    return el;
  }

  function decide(x, status) {
    const prev = decisions[x.record_id];
    if (prev && prev.status === status) delete decisions[x.record_id];   // click again to undo
    else decisions[x.record_id] = { status, confidence: x.confidence, reasons: x.explanation.map(p => `${PART_LABEL[p.name] || p.name}: ${p.explanation}`) };
    store.save(current.query, decisions);
    paint(list.querySelector(`[data-id="${CSS.escape(x.record_id)}"]`), decisions[x.record_id]);
    updateTray();
  }

  function paint(el, d) {
    el.classList.toggle("confirmed", !!d && d.status === "confirmed");
    el.classList.toggle("rejected", !!d && d.status === "rejected");
    $(".yes", el).setAttribute("aria-pressed", String(!!d && d.status === "confirmed"));
    $(".no", el).setAttribute("aria-pressed", String(!!d && d.status === "rejected"));
    $(".yes", el).textContent = d && d.status === "confirmed" ? "✓ Confirmed" : "This is them";
    $(".no", el).textContent = d && d.status === "rejected" ? "✕ Ruled out" : "Not them";
  }

  function updateTray() {
    const vals = Object.values(decisions);
    const yes = vals.filter(d => d.status === "confirmed").length, no = vals.filter(d => d.status === "rejected").length;
    tray.hidden = !current;
    $("#tray-count").textContent = yes;
    $("#tray-rejected").textContent = no;
    $("#make-report").disabled = yes === 0;
  }

  $("#report-form").addEventListener("submit", () => {
    $("#payload").value = JSON.stringify({ query: current.query, decisions });
  });
  form.addEventListener("submit", search);
  const ex = $("#example");
  if (ex) ex.addEventListener("click", () => {
    const v = { given_name: "Ole Andreas", surname: "Larsen", birth_year: "1851", birthplace: "Rakkestad", county: "Østfold", sex: "m", father_name: "Lars Olsen", spouse_name: "Marte Kristine" };
    for (const [k, val] of Object.entries(v)) form.elements[k].value = val;
    form.elements.birth_year_tolerance.value = "2";
    search();
  });
})();
