/* Start with you, grow the tree backwards, follow each ancestor's trail.
   The tree lives in this browser (localStorage). People are numbered the
   genealogist's way (ahnentafel): you are 1, the father of n is 2n and the
   mother is 2n+1, so a person's generation and relatives follow from the number. */
(() => {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const S = window.AF_STATUS, CUTOFF = S.cutoff_year;
  const PART = { "given name": "First name", surname: "Surname", "birth year": "Birth year", place: "Place", family: "Family" };
  const CONF = { high: ["Strong match", "strong"], medium: ["Possible match", "possible"], low: ["Faint trace", "faint"] };
  const GEN = ["You", "Parents", "Grandparents", "Great-grandparents"];
  const genName = g => GEN[g] || `${g - 2}× great-grandparents`;
  const KEY = "af:tree:v1";

  /* ---------------- state ---------------- */
  let tree = load();            // { "1": person, "2": person, ... }
  let active = null;            // number of the person whose trail is open
  let current = null;           // last search response

  function load() { try { return JSON.parse(localStorage.getItem(KEY) || "null") || {}; } catch { return {}; } }
  function save() { try { localStorage.setItem(KEY, JSON.stringify(tree)); } catch { /* storage off */ } }

  const person = n => tree[String(n)];
  const gen = n => Math.floor(Math.log2(n));
  const fullName = p => [p.given_name, p.surname].filter(Boolean).join(" ");
  const first = p => (p.given_name || "").split(" ")[0];
  const sexOf = n => (n === 1 ? "" : n % 2 === 0 ? "m" : "f");
  const traceable = p => p && p.birth_year && Number(p.birth_year) <= CUTOFF;
  const keptCount = p => Object.values((p && p.kept) || {}).filter(d => d.status === "confirmed").length;

  function relationLabel(n) {
    if (n === 1) return "You";
    const child = person(Math.floor(n / 2));
    const role = n % 2 === 0 ? "Father" : "Mother";
    if (Math.floor(n / 2) === 1) return `Your ${role.toLowerCase()}`;
    return child ? `${role} of ${first(child)}` : role;
  }

  /* what the tree knows about a person, as a search */
  function queryFor(n) {
    const p = person(n), f = person(2 * n), m = person(2 * n + 1);
    const partner = n > 1 ? person(n ^ 1) : null;      // the other parent of their child
    return {
      given_name: p.given_name || "", surname: p.surname || "", birth_year: p.birth_year || "",
      birthplace: p.birthplace || "", sex: sexOf(n), birth_year_tolerance: "2",
      father_name: f ? fullName(f) : "", mother_name: m ? fullName(m) : "",
      spouse_name: partner ? fullName(partner) : "", county: "", name_variants: "",
    };
  }

  /* ---------------- views ---------------- */
  function show(view) {
    for (const id of ["start-view", "tree-view", "search-view"]) $("#" + id).hidden = id !== view;
    window.scrollTo(0, 0);
  }

  function route() {
    if (!person(1)) { show("start-view"); return; }
    renderTree(); show("tree-view");
  }

  /* ---------------- start ---------------- */
  $("#start-form").addEventListener("submit", ev => {
    ev.preventDefault();
    const d = Object.fromEntries(new FormData(ev.target).entries());
    if (!d.given_name.trim()) { ev.target.elements.given_name.focus(); return; }
    tree = { "1": clean(d) };
    save(); route();
  });

  function clean(d) {
    const p = {};
    for (const k of ["given_name", "surname", "birth_year", "birthplace", "death_year"]) {
      const v = (d[k] || "").trim();
      if (v) p[k] = k.endsWith("_year") ? v.replace(/\D/g, "").slice(0, 4) : v;
    }
    return p;
  }

  /* ---------------- tree ---------------- */
  function renderTree() {
    const host = $("#tree");
    host.innerHTML = "";
    const nums = Object.keys(tree).map(Number);
    const maxGen = Math.max(...nums.map(gen));
    for (let g = 0; g <= maxGen + 1; g++) {
      const col = document.createElement("section");
      col.className = "gen";
      const h = document.createElement("h2");
      h.textContent = genName(g);
      col.appendChild(h);
      let any = false;
      for (let n = 2 ** g; n < 2 ** (g + 1); n++) {
        const p = person(n);
        if (p) { col.appendChild(personCard(n, p)); any = true; }
        else if (person(Math.floor(n / 2)) && n > 1) { col.appendChild(addSlot(n)); any = true; }
      }
      if (any) host.appendChild(col);
    }
  }

  function personCard(n, p) {
    const el = document.createElement("article");
    el.className = "pcard";
    const rel = document.createElement("p"); rel.className = "rel"; rel.textContent = relationLabel(n);
    const nm = document.createElement("h3"); nm.textContent = fullName(p) || "(no name)";
    const yrs = document.createElement("p"); yrs.className = "yrs num";
    yrs.textContent = [p.birth_year ? (p.death_year ? `${p.birth_year}–${p.death_year}` : `born ${p.birth_year}`) : "", p.birthplace].filter(Boolean).join(" · ") || "Birth year unknown";
    const st = document.createElement("p"); st.className = "state";
    const kept = keptCount(p);
    if (!p.birth_year) { st.textContent = "Add a birth year to see if we can trace them"; st.classList.add("muted-state"); }
    else if (!traceable(p)) { st.textContent = "Living memory"; st.classList.add("muted-state"); }
    else if (kept) { st.textContent = `${kept} record${kept === 1 ? "" : "s"} kept`; st.classList.add("kept-state"); }
    else { st.textContent = "Ready to trace"; st.classList.add("ready-state"); }
    const acts = document.createElement("div"); acts.className = "pacts";
    if (traceable(p)) acts.appendChild(btn(kept ? "Continue the trail" : "Follow the trail", "primary small", () => openTrail(n)));
    if (kept) acts.appendChild(btn("Read the chapter", "small", () => chapter(n)));
    acts.appendChild(btn("Edit", "quiet small", () => edit(n)));
    el.append(rel, nm, yrs, st, acts);
    return el;
  }

  function addSlot(n) {
    const child = person(Math.floor(n / 2));
    const b = btn(`+ Add ${n % 2 === 0 ? "father" : "mother"}${Math.floor(n / 2) === 1 ? "" : " of " + first(child)}`, "slot", () => edit(n));
    return b;
  }

  function btn(text, cls, fn) {
    const b = document.createElement("button");
    b.type = "button"; b.className = cls; b.textContent = text;
    b.addEventListener("click", fn);
    return b;
  }

  /* ---------------- editor ---------------- */
  const dlg = $("#editor"), ef = $("#edit-form");
  let editing = null;
  function edit(n) {
    editing = n;
    const p = person(n) || {};
    $("#edit-title").textContent = person(n) ? `Edit ${fullName(p)}` : (n === 1 ? "You" : `Add ${relationLabel(n).toLowerCase()}`);
    for (const k of ["given_name", "surname", "birth_year", "birthplace", "death_year"]) ef.elements[k].value = p[k] || "";
    // a sensible default: a child's surname is often the father's patronymic or farm name, so leave it empty
    $("#edit-remove").hidden = !person(n) || n === 1;
    dlg.returnValue = "";
    dlg.showModal();
    ef.elements.given_name.focus();
  }
  dlg.addEventListener("close", () => {
    if (dlg.returnValue === "save") {
      const d = clean(Object.fromEntries(new FormData(ef).entries()));
      if (d.given_name) { tree[String(editing)] = Object.assign(person(editing) || {}, d); save(); }
    } else if (dlg.returnValue === "remove" && editing !== 1) {
      // removing a person also removes everyone behind them in the tree
      for (const k of Object.keys(tree)) { let m = Number(k); while (m > editing) m = Math.floor(m / 2); if (m === editing) delete tree[k]; }
      save();
    }
    renderTree();
  });
  $("#edit-save").addEventListener("click", ev => { if (!ef.elements.given_name.value.trim()) { ev.preventDefault(); ef.elements.given_name.focus(); } });

  $("#reset").addEventListener("click", () => {
    if (confirm("Start over? This clears the tree saved in this browser.")) { tree = {}; save(); route(); }
  });

  /* ---------------- following a trail ---------------- */
  const form = $("#search"), list = $("#list"), statusEl = $("#status");

  function openTrail(n) {
    active = n; current = null;
    const p = person(n), q = queryFor(n);
    $("#trail-name").textContent = fullName(p);
    $("#tray-name").textContent = first(p);
    for (const [k, v] of Object.entries(q)) if (form.elements[k]) form.elements[k].value = v;
    list.innerHTML = ""; say(""); $("#tray").hidden = true;
    show("search-view");
    search();
  }
  $("#back").addEventListener("click", () => { active = null; route(); });

  const say = (html, kind = "info") => { statusEl.hidden = !html; statusEl.className = "status " + kind; statusEl.innerHTML = html || ""; };
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  async function search(ev) {
    ev && ev.preventDefault();
    const q = Object.fromEntries(new FormData(form).entries());
    for (const k of Object.keys(q)) q[k] = q[k].trim();
    if (!q.given_name || !q.birth_year) { say("A first name and a rough birth year are all we need to begin.", "gentle"); return; }
    const go = $("#go");
    go.disabled = true; go.textContent = "Following the trail…";
    list.innerHTML = "";
    try {
      const res = await fetch("/api/search", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(q) });
      const data = await res.json();
      if (!res.ok) { say(esc(data.error || "Something went wrong."), "gentle"); return; }
      current = data;
      renderResults();
    } catch {
      say("We couldn't reach the archive search just now. Try again in a moment.", "gentle");
    } finally {
      go.disabled = false; go.textContent = "Follow the trail";
    }
  }
  form.addEventListener("submit", search);

  function decisions() { const p = person(active); p.kept = p.kept || {}; return p.kept; }

  function renderResults() {
    const c = current, who = esc(first(person(active)) || c.query.given_name);
    list.innerHTML = "";
    if (!c.candidates.length) {
      say(`<h2>The trail goes quiet here</h2>
        <p>No census entry fits ${who} yet. That makes this an open mystery, not a dead end. A few things often help:</p>
        <ul><li>Widen the birth year: ages in old censuses are often a year or two off.</li>
        <li>Try another spelling, or the patronymic (Olsen, Olsdatter) instead of a farm name.</li>
        <li>Leave out the birthplace: people moved more than we think.</li>
        <li>So far we search ${esc(S.coverage.counties.join(", "))}. If ${who} lived elsewhere, that census isn't in yet.</li></ul>`, "mystery");
    } else {
      const strong = c.candidates.filter(x => x.confidence === "high").length;
      const more = c.total > c.shown ? ` Showing the ${c.shown} closest.` : "";
      const lead = strong ? `${strong} point${strong === 1 ? "s" : ""} strongly to ${who}.` : "None stands out yet, so the family details are your best guide.";
      say(`<p><b>${c.total} trace${c.total === 1 ? "" : "s"} found.</b> ${lead}${more}</p>`, "info");
    }
    for (const cand of c.candidates) list.appendChild(card(cand));
    updateTray();
  }

  const NOTE_TEXT = [
    [/^parents\/spouse in this record are inferred/, () => "Parents and spouse are read from who lived in the household, not from a stated link."],
    [/^birth year in record is computed from stated age/, () => "The birth year comes from a stated age, so it may be a year off."],
    [/^close rival: (\S+)/, m => `Another entry (${m[1]}) fits almost as well and looks like a different person.`],
    [/^(\d+) listed family member\(s\) conflict/, () => "A family member listed here doesn't match your tree."],
    [/^record lists none of the queried family members/, () => "This entry lists none of the family in your tree, so a namesake can't be ruled out."],
    [/^birth year outside tolerance/, () => "The birth year is further off than you allowed."],
    [/^fields were extracted from the transcription by a model/, () => "Details were read from the transcription by a model. Check the source."],
  ];
  const noteText = n => { for (const [re, f] of NOTE_TEXT) { const m = n.match(re); if (m) return f(m); } return n; };

  function strongestClue(x) {
    const has = re => x.notes.some(n => re.test(n));
    if (has(/^\d+ listed family member/)) return "A family member listed here doesn't match your tree.";
    const weak = x.explanation.filter(p => p.score < 0.6).map(p => (PART[p.name] || p.name).toLowerCase());
    if (weak.length) return "Doesn't fit on " + weak.join(" and ") + ".";
    if (has(/^close rival/)) return "Fits well, but a namesake nearby fits almost as well.";
    if (has(/^record lists none of the queried family/)) return "Fits, but lists none of the family in your tree.";
    if (x.explanation.find(p => p.name === "family" && p.score >= 0.9)) return "Name, birth year and family all fit.";
    return "Name, birth year and place all fit.";
  }

  function card(x) {
    const el = $("#card-t").content.firstElementChild.cloneNode(true);
    el.dataset.id = x.record_id;
    $(".year", el).textContent = x.year;
    $(".where", el).textContent = [x.farm, x.municipality].filter(Boolean).join(", ") || "place not given";
    $(".name", el).textContent = x.record_name || "(no name)";
    $(".meta", el).textContent = `Born ${x.birth_year_in_record ?? "?"}${x.birthplace ? " in " + x.birthplace : ""}${x.role ? " · listed as «" + x.role + "»" : ""}`;
    $(".clue", el).textContent = strongestClue(x);
    const [label, cls] = CONF[x.confidence];
    const chip = $(".chip", el);
    chip.textContent = label; chip.classList.add(cls); chip.title = `Score ${Math.round(x.score * 100)} of 100`;
    const ul = $(".reasons", el);
    for (const p of x.explanation) {
      const li = document.createElement("li");
      li.className = p.score >= 0.9 ? "fits" : p.score >= 0.6 ? "partly" : "against";
      li.innerHTML = '<span class="lab"></span><span class="txt"></span>';
      $(".lab", li).textContent = PART[p.name] || p.name;
      $(".txt", li).textContent = p.explanation;
      ul.appendChild(li);
    }
    for (const n of x.notes) { const li = document.createElement("li"); li.textContent = noteText(n); $(".notes", el).appendChild(li); }
    const hh = x.household || [];
    if (hh.length <= 1) $(".house", el).innerHTML = "<h4>Living at the same place</h4><p class='muted'>Nobody else is listed with this entry.</p>";
    else for (const h of hh) {
      const tr = document.createElement("tr");
      if (h.record_id === x.record_id) tr.className = "me";
      for (const v of [h.name, h.birth_year ?? "?", h.role || ""]) { const td = document.createElement("td"); td.textContent = v; tr.appendChild(td); }
      $("tbody", el).appendChild(tr);
    }
    $(".cite", el).textContent = x.source;
    const open = $(".open", el);
    if (x.link) open.href = x.link;
    else { open.removeAttribute("href"); open.classList.add("disabled"); open.setAttribute("aria-disabled", "true"); open.textContent = x.demo ? "Example entry, no archive page" : "No archive link"; }
    $(".yes", el).addEventListener("click", () => decide(x, "confirmed"));
    $(".no", el).addEventListener("click", () => decide(x, "rejected"));
    paint(el, decisions()[x.record_id]);
    return el;
  }

  function decide(x, status) {
    const d = decisions(), prev = d[x.record_id];
    if (prev && prev.status === status) delete d[x.record_id];
    else d[x.record_id] = { status, confidence: x.confidence, year: x.year, reasons: x.explanation.map(p => `${PART[p.name] || p.name}: ${p.explanation}`) };
    save();
    paint(list.querySelector(`[data-id="${CSS.escape(x.record_id)}"]`), d[x.record_id]);
    updateTray();
  }

  function paint(el, d) {
    const kept = !!d && d.status === "confirmed", aside = !!d && d.status === "rejected";
    el.classList.toggle("kept", kept); el.classList.toggle("aside", aside);
    $(".yes", el).setAttribute("aria-pressed", String(kept)); $(".no", el).setAttribute("aria-pressed", String(aside));
    $(".yes", el).textContent = kept ? "✓ Kept" : "This is them";
    $(".no", el).textContent = aside ? "Set aside" : "Not them";
  }

  function updateTray() {
    const vals = Object.values(decisions());
    const yes = vals.filter(d => d.status === "confirmed").length, no = vals.filter(d => d.status === "rejected").length;
    $("#tray").hidden = !current;
    $("#tray-count").textContent = yes; $("#tray-rejected").textContent = no;
    $("#make-report").disabled = yes === 0;
  }

  /* ---------------- chapters ---------------- */
  function chapter(n) {
    const q = queryFor(n);
    if (n === active) Object.assign(q, Object.fromEntries(new FormData(form).entries()));
    $("#payload").value = JSON.stringify({ query: q, decisions: person(n).kept || {} });
    $("#report-form").submit();
  }
  $("#report-form").addEventListener("submit", ev => { ev.preventDefault(); chapter(active); });

  /* ---------------- example family (invented) ---------------- */
  const EXAMPLE = {
    "1": { given_name: "Ingrid", surname: "Lie", birth_year: "1991", birthplace: "Fredrikstad" },
    "2": { given_name: "Erik", surname: "Lie", birth_year: "1959", birthplace: "Rakkestad" },
    "3": { given_name: "Hilde", surname: "Berg", birth_year: "1962", birthplace: "Sarpsborg" },
    "4": { given_name: "Kåre", surname: "Lie", birth_year: "1933", birthplace: "Rakkestad", death_year: "2011" },
    "5": { given_name: "Solveig", surname: "Haugen", birth_year: "1936", birthplace: "Degernes", death_year: "2019" },
    "8": { given_name: "Ole", surname: "Kristiansen", birth_year: "1909", birthplace: "Rakkestad", death_year: "1978" },
    "16": { given_name: "Kristian", surname: "Olsen", birth_year: "1886", birthplace: "Rakkestad" },
    "32": { given_name: "Ole Andreas", surname: "Larsen", birth_year: "1851", birthplace: "Rakkestad" },
    "33": { given_name: "Marte Kristine", birth_year: "1854", birthplace: "Degernes" },
    "64": { given_name: "Lars", surname: "Olsen", birth_year: "1822", birthplace: "Rakkestad" },
    "65": { given_name: "Berte", surname: "Hansdatter", birth_year: "1826", birthplace: "Degernes" },
  };
  const ex = $("#example");
  if (ex) ex.addEventListener("click", () => { tree = JSON.parse(JSON.stringify(EXAMPLE)); save(); route(); });

  route();
})();
