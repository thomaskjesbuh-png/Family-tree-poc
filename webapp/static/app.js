/* Search, examine, decide, write the chapter. No framework. */
(() => {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const form = $("#search"), list = $("#list"), statusEl = $("#status"), intro = $("#intro");
  const tray = $("#tray"), tpl = $("#card-t");
  const PART = { "given name": "First name", surname: "Surname", "birth year": "Birth year", place: "Place", family: "Family" };
  const CONF = { high: ["Strong match", "strong"], medium: ["Possible match", "possible"], low: ["Faint trace", "faint"] };
  const BUTTON = "Follow the trail";

  let current = null;     // last search response
  let decisions = {};     // record_id -> {status, confidence, reasons}

  const store = {
    key(q) { return "af:" + JSON.stringify([q.given_name, q.surname, q.birth_year, q.birthplace]); },
    load(q) { try { return JSON.parse(localStorage.getItem(this.key(q)) || "{}"); } catch { return {}; } },
    save(q, d) { try { localStorage.setItem(this.key(q), JSON.stringify(d)); } catch { /* storage off */ } },
  };

  const formData = () => {
    const d = Object.fromEntries(new FormData(form).entries());
    for (const k of Object.keys(d)) d[k] = d[k].trim();
    return d;
  };

  function say(html, kind = "info") {
    statusEl.hidden = !html;
    statusEl.className = "status " + kind;
    statusEl.innerHTML = html || "";
  }
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  async function search(ev) {
    ev && ev.preventDefault();
    const q = formData();
    if (!q.given_name || !q.birth_year) { say("A first name and a rough birth year are all we need to begin.", "gentle"); return; }
    const go = $("#go");
    go.disabled = true; go.textContent = "Following the trail…";
    say(""); list.innerHTML = "";
    try {
      const res = await fetch("/api/search", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(q) });
      const data = await res.json();
      if (!res.ok) { say(esc(data.error || "Something went wrong."), "gentle"); return; }
      current = data;
      decisions = store.load(data.query);
      intro.hidden = true;
      render();
    } catch {
      say("We couldn't reach the archive search just now. Try again in a moment.", "gentle");
    } finally {
      go.disabled = false; go.textContent = BUTTON;
    }
  }

  function render() {
    const c = current, who = esc(c.query.given_name.split(" ")[0]);
    list.innerHTML = "";
    if (!c.candidates.length) {
      say(`<h2>The trail goes quiet here</h2>
        <p>No census entry fits ${who} yet. That makes this an open mystery, not a dead end. A few things often help:</p>
        <ul><li>Widen the birth year: ages in old censuses are often a year or two off.</li>
        <li>Try another spelling, or the patronymic (Olsen, Olsdatter) instead of a farm name.</li>
        <li>Leave out the birthplace: people moved more than we think.</li></ul>`, "mystery");
    } else {
      const strong = c.candidates.filter(x => x.confidence === "high").length;
      const more = c.total > c.shown ? ` Showing the ${c.shown} closest.` : "";
      const lead = strong
        ? `${strong} point${strong === 1 ? "s" : ""} strongly to ${who}.`
        : `None stands out yet, so the family details are your best guide.`;
      say(`<p><b>${c.total} trace${c.total === 1 ? "" : "s"} found.</b> ${lead}${more}</p>`, "info");
    }
    for (const cand of c.candidates) list.appendChild(card(cand));
    updateTray();
  }

  // Plain, gentle wording for the engine's notes; anything unknown is shown as is.
  const NOTE_TEXT = [
    [/^parents\/spouse in this record are inferred/, () => "Parents and spouse are read from who lived in the household, not from a stated link."],
    [/^birth year in record is computed from stated age/, () => "The birth year comes from a stated age, so it may be a year off."],
    [/^close rival: (\S+)/, m => `Another entry (${m[1]}) fits almost as well and looks like a different person.`],
    [/^(\d+) listed family member\(s\) conflict/, () => "A family member listed here doesn't match what you gave."],
    [/^record lists none of the queried family members/, () => "This entry lists none of the family you gave, so a namesake can't be ruled out."],
    [/^birth year outside tolerance/, () => "The birth year is further off than you allowed."],
    [/^fields were extracted from the transcription by a model/, () => "Details were read from the transcription by a model. Check the source."],
  ];
  const noteText = n => { for (const [re, f] of NOTE_TEXT) { const m = n.match(re); if (m) return f(m); } return n; };

  function strongestClue(x) {
    const has = re => x.notes.some(n => re.test(n));
    if (has(/^\d+ listed family member/)) return "A family member listed here doesn't match.";
    const weak = x.explanation.filter(p => p.score < 0.6).map(p => (PART[p.name] || p.name).toLowerCase());
    if (weak.length) return "Doesn't fit on " + weak.join(" and ") + ".";
    if (has(/^close rival/)) return "Fits well, but a namesake nearby fits almost as well.";
    if (has(/^record lists none of the queried family/)) return "Fits, but lists none of the family you gave.";
    const fam = x.explanation.find(p => p.name === "family" && p.score >= 0.9);
    if (fam) return "Name, birth year and family all fit.";
    return "Name, birth year and place all fit.";
  }

  function card(x) {
    const el = tpl.content.firstElementChild.cloneNode(true);
    el.dataset.id = x.record_id;
    $(".year", el).textContent = x.year;
    $(".where", el).textContent = [x.farm, x.municipality].filter(Boolean).join(", ") || "place not given";
    $(".name", el).textContent = x.record_name || "(no name)";
    $(".meta", el).textContent = `Born ${x.birth_year_in_record ?? "?"}${x.birthplace ? " in " + x.birthplace : ""}${x.role ? " · listed as «" + x.role + "»" : ""}`;
    $(".clue", el).textContent = strongestClue(x);
    const [label, cls] = CONF[x.confidence];
    const chip = $(".chip", el);
    chip.textContent = label; chip.classList.add(cls);
    chip.title = `Score ${Math.round(x.score * 100)} of 100`;

    const ul = $(".reasons", el);
    for (const p of x.explanation) {
      const li = document.createElement("li");
      li.className = p.score >= 0.9 ? "fits" : p.score >= 0.6 ? "partly" : "against";
      li.innerHTML = '<span class="lab"></span><span class="txt"></span>';
      $(".lab", li).textContent = PART[p.name] || p.name;
      $(".txt", li).textContent = p.explanation;
      ul.appendChild(li);
    }
    if (x.judge) {
      const li = document.createElement("li");
      li.className = x.judge.verdict === "same" ? "fits" : x.judge.verdict === "different" ? "against" : "partly";
      li.innerHTML = '<span class="lab">Second look</span><span class="txt"></span>';
      $(".txt", li).textContent = `${x.judge.verdict}: ${(x.judge.reasons || []).join("; ")}`;
      ul.appendChild(li);
    }
    const notes = $(".notes", el);
    for (const n of x.notes) { const li = document.createElement("li"); li.textContent = noteText(n); notes.appendChild(li); }

    const hh = x.household || [];
    if (hh.length <= 1) {
      $(".house", el).innerHTML = "<h4>Living at the same place</h4><p class='muted'>Nobody else is listed with this entry.</p>";
    } else {
      const tb = $("tbody", el);
      for (const h of hh) {
        const tr = document.createElement("tr");
        if (h.record_id === x.record_id) tr.className = "me";
        for (const v of [h.name, h.birth_year ?? "?", h.role || ""]) { const td = document.createElement("td"); td.textContent = v; tr.appendChild(td); }
        tb.appendChild(tr);
      }
    }

    $(".cite", el).textContent = x.source;
    const open = $(".open", el);
    if (x.link) open.href = x.link;
    else { open.removeAttribute("href"); open.classList.add("disabled"); open.setAttribute("aria-disabled", "true"); open.textContent = x.demo ? "Example entry, no archive page" : "No archive link"; }

    $(".yes", el).addEventListener("click", () => decide(x, "confirmed"));
    $(".no", el).addEventListener("click", () => decide(x, "rejected"));
    paint(el, decisions[x.record_id]);
    return el;
  }

  function decide(x, status) {
    const prev = decisions[x.record_id];
    if (prev && prev.status === status) delete decisions[x.record_id];   // a second click undoes it
    else decisions[x.record_id] = { status, confidence: x.confidence, reasons: x.explanation.map(p => `${PART[p.name] || p.name}: ${p.explanation}`) };
    store.save(current.query, decisions);
    paint(list.querySelector(`[data-id="${CSS.escape(x.record_id)}"]`), decisions[x.record_id]);
    updateTray();
  }

  function paint(el, d) {
    const kept = !!d && d.status === "confirmed", aside = !!d && d.status === "rejected";
    el.classList.toggle("kept", kept);
    el.classList.toggle("aside", aside);
    $(".yes", el).setAttribute("aria-pressed", String(kept));
    $(".no", el).setAttribute("aria-pressed", String(aside));
    $(".yes", el).textContent = kept ? "✓ Kept" : "This is them";
    $(".no", el).textContent = aside ? "Set aside" : "Not them";
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
