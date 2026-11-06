/* Spor: start med deg, bygg treet bakover, følg sporet til hver forfar.
   Treet lagres i nettleseren (localStorage) med ahnentafel-nummer:
   du er 1, far til n er 2n og mor er 2n+1. */
(() => {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const S = window.AF_STATUS, CUTOFF = S.cutoff_year;
  const KEY = "af:tree:v1", FOCUS_KEY = "af:focus:v1";

  /* ---------------- tilstand ---------------- */
  let tree = loadJSON(KEY, {});
  let focus = Number(loadJSON(FOCUS_KEY, 1)) || 1;
  let active = null;     // personen hvis spor er åpent
  let current = null;    // siste søkesvar
  let weakerOpen = false;

  function loadJSON(k, d) { try { const v = JSON.parse(localStorage.getItem(k)); return v ?? d; } catch { return d; } }
  function save() { try { localStorage.setItem(KEY, JSON.stringify(tree)); localStorage.setItem(FOCUS_KEY, JSON.stringify(focus)); } catch { /* lagring av */ } }

  const person = n => tree[String(n)];
  const gen = n => Math.floor(Math.log2(n));
  const fullName = p => [p.given_name, p.surname].filter(Boolean).join(" ");
  const first = p => ((p && p.given_name) || "").split(" ")[0];
  const sexOf = n => (n === 1 ? "" : n % 2 === 0 ? "m" : "f");
  const traceable = p => p && p.birth_year && Number(p.birth_year) <= CUTOFF;
  const keptOf = p => Object.entries((p && p.kept) || {}).filter(([, d]) => d.status === "confirmed");
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  /* text with each run of digits in <span class="num">, so only digits get tabular figures */
  const nums = (tag, cls, text) => {
    const e = el(tag, cls);
    String(text ?? "").split(/(\d+)/).forEach((part, i) => { if (part) e.appendChild(i % 2 ? el("span", "num", part) : document.createTextNode(part)); });
    return e;
  };
  const art = id => $("#" + id).content.firstElementChild.cloneNode(true);
  const pronoun = sex => (sex === "m" ? "Han" : sex === "f" ? "Hun" : "Personen");

  function relationLabel(n) {
    if (n === 1) return "Deg";
    const c = Math.floor(n / 2), role = n % 2 === 0 ? "far" : "mor";
    if (c === 1) return `Din ${role}`;
    return `${role === "far" ? "Far" : "Mor"} til ${first(person(c))}`;
  }

  function queryFor(n) {
    const p = person(n), f = person(2 * n), m = person(2 * n + 1), partner = n > 1 ? person(n ^ 1) : null;
    return {
      given_name: p.given_name || "", surname: p.surname || "", birth_year: p.birth_year || "", birthplace: p.birthplace || "",
      sex: sexOf(n), birth_year_tolerance: "2", county: "", name_variants: "",
      father_name: f ? fullName(f) : "", mother_name: m ? fullName(m) : "", spouse_name: partner ? fullName(partner) : "",
    };
  }

  /* ---------------- merker (ConfidenceBadge) ---------------- */
  const BADGE = {
    confirmed: ["Bekreftet", '<circle cx="8" cy="8" r="6.25"/><path d="M5.3 8.2l1.8 1.8 3.6-3.8"/>', 'stroke-linecap="round" stroke-linejoin="round"'],
    probable: ["Sannsynlig", '<circle cx="8" cy="8" r="6.25"/><path d="M8 1.75a6.25 6.25 0 0 1 0 12.5z" fill="currentColor" stroke="none"/>', ""],
    unverified: ["Ubekreftet", '<circle cx="8" cy="8" r="6.25"/>', 'stroke-dasharray="2.4 2.4"'],
    conflict: ["Motstridende kilder", '<circle cx="8" cy="8" r="6.25"/><path d="M8 4.8v3.6M8 11h0"/>', 'stroke-linecap="round"'],
  };
  function badge(kind) {
    const [word, inner, extra] = BADGE[kind];
    const s = el("span", `sp-badge sp-badge-${kind}`);
    s.innerHTML = `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" ${extra} aria-hidden="true">${inner}</svg>${word}`;
    return s;
  }
  const CHECK = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="8" r="6.25"/><path d="M5.3 8.2l1.8 1.8 3.6-3.8"/></svg>';

  /* ---------------- visninger ---------------- */
  function show(view) { for (const id of ["start-view", "tree-view", "search-view", "relatives-view"]) $("#" + id).hidden = id !== view; window.scrollTo(0, 0); }
  function route() {
    if (!person(1)) { show("start-view"); return; }
    if (!person(focus)) focus = 1;
    renderTree(); renderPane(); show("tree-view");
    const node = $(`.tnode[data-n="${focus}"]`); if (node) node.scrollIntoView({ block: "nearest", inline: "center" });
  }

  function cleanPerson(d) {
    const p = {};
    for (const k of ["given_name", "surname", "birth_year", "birthplace", "death_year"]) {
      const v = (d[k] || "").trim();
      if (v) p[k] = k.endsWith("_year") ? v.replace(/\D/g, "").slice(0, 4) : v;
    }
    return p;
  }

  $("#start-form").addEventListener("submit", ev => {
    ev.preventDefault();
    const d = cleanPerson(Object.fromEntries(new FormData(ev.target).entries()));
    if (!d.given_name) { ev.target.elements.given_name.focus(); return; }
    tree = { "1": d }; focus = 1; save(); route();
  });

  /* ---------------- treet (FamilyTree): eldste generasjon øverst ---------------- */
  const W = 164, H = 56, GX = 16, GY = 44;
  function renderTree() {
    const host = $("#tree");
    host.innerHTML = "";
    const ids = Object.keys(tree).map(Number);
    const maxGen = Math.max(...ids.map(gen));
    const x = {};
    let slot = 0;
    (function place(n) {
      const ps = [2 * n, 2 * n + 1].filter(p => person(p));
      ps.forEach(place);
      x[n] = ps.length ? ps.reduce((a, p) => a + x[p], 0) / ps.length : (slot++) * (W + GX);
    })(1);
    const y = n => (maxGen - gen(n)) * (H + GY);
    const width = Math.max(slot * (W + GX) - GX, W), height = (maxGen + 1) * (H + GY) - GY;
    host.style.width = width + "px"; host.style.height = height + "px";

    let d = "";
    for (const n of ids) {
      const ps = [2 * n, 2 * n + 1].filter(p => person(p));
      if (!ps.length) continue;
      const bar = y(ps[0]) + H + GY / 2;
      for (const p of ps) d += `M${x[p] + W / 2} ${y(p) + H}V${bar}`;
      if (ps.length === 2) d += `M${x[ps[0]] + W / 2} ${bar}H${x[ps[1]] + W / 2}`;
      d += `M${x[n] + W / 2} ${bar}V${y(n)}`;
    }
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "tree-lines"); svg.setAttribute("width", width); svg.setAttribute("height", height);
    svg.setAttribute("aria-hidden", "true");
    svg.innerHTML = `<path d="${d}"/>`;
    host.appendChild(svg);

    for (const n of ids.sort((a, b) => a - b)) {
      const p = person(n);
      const b = el("button", "tnode" + (n === focus ? " active" : ""));
      b.type = "button"; b.dataset.n = n;
      b.style.left = x[n] + "px"; b.style.top = y(n) + "px";
      b.setAttribute("aria-pressed", String(n === focus));
      b.setAttribute("aria-label", `${fullName(p)}, ${relationLabel(n).toLowerCase()}`);
      b.appendChild(el("span", "tn", fullName(p) || "(uten navn)"));
      const ty = el("span", "ty");
      const yrs = p.birth_year ? (p.death_year ? `${p.birth_year}–${p.death_year}` : `${p.birth_year}–`) : "?";
      ty.appendChild(nums("span", null, yrs));
      if (keptOf(p).length) { const ic = el("span"); ic.innerHTML = CHECK; ic.title = "Funnet i kildene"; ty.appendChild(ic); }
      b.appendChild(ty);
      b.addEventListener("click", () => { focus = n; save(); renderTree(); renderPane(); });
      host.appendChild(b);
    }
  }

  /* ---------------- personen (PersonCard) ---------------- */
  function renderPane() {
    const pane = $("#pane"), n = focus, p = person(n);
    pane.innerHTML = "";
    const card = el("article", "sp-card");
    const row = el("div", "sp-person");
    const portrait = el("div", "sp-portrait"); portrait.appendChild(art("art-portrait"));
    const body = el("div", "sp-person-body");
    body.appendChild(el("p", "rel", relationLabel(n)));
    body.appendChild(el("h2", "sp-name", fullName(p) || "(uten navn)"));
    const kept = keptOf(p);
    if (kept.length) { const bw = el("div"); bw.appendChild(badge("confirmed")); body.appendChild(bw); }
    const dl = el("dl", "sp-facts");
    const fact = (k, v) => { dl.appendChild(el("dt", null, k)); dl.appendChild(nums("dd", null, v)); };
    fact("Født", [p.birth_year || "?", p.birthplace].filter(Boolean).join(", "));
    if (p.death_year) fact("Død", p.death_year);
    const f = person(2 * n), m = person(2 * n + 1);
    fact("Foreldre", f || m ? [f && fullName(f), m && fullName(m)].filter(Boolean).join(" og ") : "Ikke lagt til ennå");
    body.appendChild(dl);
    if (kept.length && kept[0][1].source) body.appendChild(el("div", "sp-source", kept[0][1].source));
    row.append(portrait, body);
    card.appendChild(row);

    let state;
    if (!p.birth_year) state = "Legg til fødselsår, så ser vi om vi kan spore personen.";
    else if (!traceable(p)) state = `Levende minne. Personer født etter ${CUTOFF} søkes ikke opp.`;
    else if (kept.length) state = `Funnet i ${kept.length} ${kept.length === 1 ? "kilde" : "kilder"}. Let gjerne videre.`;
    else state = "Klar til å spores i folketellingene.";
    card.appendChild(el("p", "state", state));

    const acts = el("div", "sp-actions");
    if (traceable(p)) acts.appendChild(btn(kept.length ? "Let videre" : "Følg sporet", "sp-btn sp-btn-primary", () => openTrail(n)));
    if (traceable(p) && (!f || !m)) acts.appendChild(btn("Let etter foreldrene", "sp-btn", () => findRelatives([n])));
    if (!f) acts.appendChild(btn("Legg til far", "sp-btn", () => edit(2 * n)));
    if (!m) acts.appendChild(btn("Legg til mor", "sp-btn", () => edit(2 * n + 1)));
    acts.appendChild(btn("Endre", "sp-btn", () => edit(n)));
    if (kept.length) acts.appendChild(btn("Les kapittelet", "sp-btn sp-btn-quiet", () => chapter(n)));
    card.appendChild(acts);
    pane.appendChild(card);

    if (kept.length) {
      const sec = el("section", "sp-card");
      sec.appendChild(el("h3", "sp-eyebrow sp-muted", "Funnet i kildene"));
      const ul = el("ul", "found");
      for (const [, d] of kept.sort((a, b) => (a[1].year || 0) - (b[1].year || 0))) {
        const li = el("li");
        li.appendChild(nums("span", "data", [d.year && `Folketellingen ${d.year}`, d.place].filter(Boolean).join(" · ")));
        li.appendChild(el("span", "sp-name", d.name || ""));
        if (d.source) li.appendChild(el("span", "sp-source", d.source));
        ul.appendChild(li);
      }
      sec.appendChild(ul);
      pane.appendChild(sec);
    }
  }

  function btn(text, cls, fn) { const b = el("button", cls, text); b.type = "button"; b.addEventListener("click", fn); return b; }

  /* ---------------- redigering ---------------- */
  const dlg = $("#editor"), ef = $("#edit-form");
  let editing = null;
  function edit(n) {
    editing = n;
    const p = person(n) || {};
    let title;
    if (person(n)) title = `Endre ${fullName(p)}`;
    else if (n === 1) title = "Legg til deg";
    else if (Math.floor(n / 2) === 1) title = `Legg til din ${n % 2 === 0 ? "far" : "mor"}`;
    else title = `Legg til ${n % 2 === 0 ? "far" : "mor"} til ${first(person(Math.floor(n / 2)))}`;
    $("#edit-title").textContent = title;
    for (const k of ["given_name", "surname", "birth_year", "birthplace", "death_year"]) ef.elements[k].value = p[k] || "";
    $("#edit-remove").hidden = !person(n) || n === 1;
    dlg.returnValue = "";
    dlg.showModal();
    ef.elements.given_name.focus();
  }
  $("#edit-save").addEventListener("click", ev => { if (!ef.elements.given_name.value.trim()) { ev.preventDefault(); ef.elements.given_name.focus(); } });
  dlg.addEventListener("close", () => {
    if (dlg.returnValue === "save") {
      const d = cleanPerson(Object.fromEntries(new FormData(ef).entries()));
      if (d.given_name) { tree[String(editing)] = Object.assign(person(editing) || {}, d); focus = editing; save(); }
    } else if (dlg.returnValue === "remove" && editing !== 1) {
      for (const k of Object.keys(tree)) { let m = Number(k); while (m > editing) m = Math.floor(m / 2); if (m === editing) delete tree[k]; }
      focus = Math.floor(editing / 2); save();
    }
    renderTree(); renderPane();
  });
  $("#reset").addEventListener("click", () => {
    if (confirm("Begynne på nytt? Treet som er lagret i denne nettleseren, blir slettet.")) { tree = {}; focus = 1; save(); route(); }
  });

  /* ---------------- sporet ---------------- */
  const form = $("#search");
  function openTrail(n) {
    active = n; current = null; weakerOpen = false;
    $("#trail-name").textContent = fullName(person(n));
    for (const [k, v] of Object.entries(queryFor(n))) if (form.elements[k]) form.elements[k].value = v;
    $("#results").innerHTML = ""; $("#summary").hidden = true;
    show("search-view");
    search();
  }
  $("#back").addEventListener("click", () => { focus = active || focus; active = null; save(); route(); });

  async function search(ev) {
    ev && ev.preventDefault();
    const q = Object.fromEntries(new FormData(form).entries());
    for (const k of Object.keys(q)) q[k] = q[k].trim();
    const go = $("#go");
    go.disabled = true; go.textContent = "Leter…";
    try {
      const res = await fetch("/api/search", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(q) });
      const data = await res.json();
      if (!res.ok) { message(data.error || "Noe gikk galt."); return; }
      current = data; renderResults();
    } catch {
      message("Vi fikk ikke kontakt med arkivsøket akkurat nå. Prøv igjen om litt.");
    } finally { go.disabled = false; go.textContent = "Let på nytt"; }
  }
  form.addEventListener("submit", search);
  function message(t) { const s = $("#summary"); s.hidden = false; s.textContent = t; $("#results").innerHTML = ""; }

  const decisions = () => { const p = person(active); p.kept = p.kept || {}; return p.kept; };

  function badgeKind(x) {
    const d = decisions()[x.record_id];
    if (d && d.status === "confirmed") return "confirmed";
    if (x.notes.some(n => /^\d+ listed family member/.test(n))) return "conflict";
    return x.confidence === "high" ? "probable" : "unverified";
  }

  function renderResults() {
    const c = current, p = person(active), who = first(p) || c.query.given_name, host = $("#results");
    host.innerHTML = "";
    const sum = $("#summary");
    if (!c.candidates.length) { sum.hidden = true; host.appendChild(emptyState(c.query)); return; }
    const strong = c.candidates.filter(x => x.confidence === "high").length;
    sum.hidden = false;
    sum.textContent = `${c.total} spor funnet. ` + (strong
      ? `${strong} ${strong === 1 ? "peker" : "peker"} tydelig mot ${who}.`
      : "Ingen skiller seg ut ennå, så familieopplysningene er den beste veiviseren.") +
      (c.total > c.shown ? ` Viser de ${c.shown} nærmeste.` : "");

    const dec = decisions();
    const isAside = x => dec[x.record_id] && dec[x.record_id].status === "rejected";
    let rest = c.candidates.slice();
    const top = rest[0];
    if (top && top.confidence === "high" && !isAside(top)) { host.appendChild(findCard(top, p)); rest = rest.slice(1); }
    const main = rest.filter(x => x.confidence !== "low"), weak = rest.filter(x => x.confidence === "low");
    if (main.length) { const ol = el("ol", "cards"); main.forEach(x => ol.appendChild(resultCard(x))); host.appendChild(ol); }
    if (weak.length) {
      const det = el("details", "weaker"); det.open = weakerOpen;
      det.appendChild(el("summary", null, `Vis ${weak.length} svakere spor`));
      det.addEventListener("toggle", () => { weakerOpen = det.open; });
      const ol = el("ol", "cards"); weak.forEach(x => ol.appendChild(resultCard(x))); det.appendChild(ol);
      host.appendChild(det);
    }
  }

  /* Nytt spor: det beste treffet, med postens egne ord */
  function findCard(x, p) {
    const kept = (decisions()[x.record_id] || {}).status === "confirmed";
    const a = el("article", "sp-find");
    const head = el("div", "sp-find-head");
    head.appendChild(el("span", "sp-eyebrow", kept ? "Lagt til i treet" : "Nytt spor"));
    const bw = el("span"); bw.style.marginLeft = "auto"; bw.appendChild(badge(badgeKind(x))); head.appendChild(bw);
    const body = el("div", "sp-find-body");
    body.appendChild(el("h3", "sp-find-title", `${first(p)} står i folketellingen ${x.year}`));
    const place = [x.farm, x.municipality].filter(Boolean);
    let story = place.length > 1 ? `${pronoun(x.sex)} bor på ${x.farm} i ${x.municipality}` : `${pronoun(x.sex)} er oppført i ${place[0] || "en ukjent plass"}`;
    if (x.father && x.mother) story += `, sammen med foreldrene ${x.father} og ${x.mother}`;
    else if (x.spouse) story += `, sammen med ${x.spouse}`;
    story += ". Folketellingen skriver:";
    body.appendChild(el("p", "sp-find-story", story));
    body.appendChild(el("div", "sp-scan", "«" + [x.record_name, x.role, x.birth_year_in_record, x.birthplace].filter(v => v != null && v !== "").join(", ") + "»"));
    body.appendChild(el("div", "sp-source", `${x.source} · ${x.record_id}`));
    body.appendChild(clues(x));
    const acts = el("div", "sp-actions");
    acts.appendChild(btn(kept ? "Lagt til i treet" : "Legg til i treet", "sp-btn sp-btn-primary", () => decide(x, "confirmed")));
    acts.appendChild(sourceButton(x));
    acts.appendChild(btn("Ikke denne personen", "sp-btn sp-btn-quiet", () => decide(x, "rejected")));
    body.appendChild(acts);
    a.append(head, body);
    return a;
  }

  function resultCard(x) {
    const d = decisions()[x.record_id], kept = d && d.status === "confirmed", aside = d && d.status === "rejected";
    const li = el("li", "sp-card rcard" + (aside ? " aside" : ""));
    const top = el("div", "rcard-top");
    const who = el("div");
    who.appendChild(el("h3", "sp-name", x.record_name || "(uten navn)"));
    who.appendChild(nums("p", "data", [`Folketellingen ${x.year}`, [x.farm, x.municipality].filter(Boolean).join(", "), `f. ${x.birth_year_in_record ?? "?"}${x.birthplace ? " i " + x.birthplace : ""}`].filter(Boolean).join(" · ")));
    top.append(who, badge(badgeKind(x)));
    li.appendChild(top);
    li.appendChild(el("p", "clue", clueLine(x)));
    li.appendChild(clues(x));
    const acts = el("div", "sp-actions");
    acts.appendChild(btn(kept ? "Lagt til i treet" : "Legg til i treet", "sp-btn", () => decide(x, "confirmed")));
    acts.appendChild(sourceButton(x));
    acts.appendChild(btn(aside ? "Lagt til side" : "Ikke denne personen", "sp-btn sp-btn-quiet", () => decide(x, "rejected")));
    li.appendChild(acts);
    return li;
  }

  function sourceButton(x) {
    if (x.link) { const a = el("a", "sp-btn", "Se kilden"); a.href = x.link; a.target = "_blank"; a.rel = "noopener"; return a; }
    const b = el("button", "sp-btn", x.demo ? "Ingen kildeside (eksempel)" : "Ingen lenke"); b.type = "button"; b.disabled = true; return b;
  }

  function clues(x) {
    const det = el("details", "clues");
    det.appendChild(el("summary", null, "Se sporene"));
    const body = el("div", "clues-body");
    const why = el("div"); why.appendChild(el("h4", null, "Hvorfor dette sporet"));
    const ul = el("ul", "reasons");
    for (const part of x.explanation) {
      const li = el("li", part.score >= 0.9 ? "fits" : part.score >= 0.6 ? "partly" : "against");
      li.append(el("span", "lab", PART[part.name] || part.name), el("span", "txt", nb(part.explanation)));
      ul.appendChild(li);
    }
    why.appendChild(ul);
    if (x.notes.length) { const nl = el("ul", "notes"); x.notes.forEach(n => nl.appendChild(el("li", null, noteNb(n)))); why.appendChild(nl); }
    const house = el("div"); house.appendChild(el("h4", null, "Bodde samme sted"));
    const hh = x.household || [];
    if (hh.length <= 1) house.appendChild(el("p", "muted", "Ingen andre er oppført sammen med denne posten."));
    else {
      const t = el("table"); t.innerHTML = "<thead><tr><th>Navn</th><th>Født</th><th>Oppført som</th></tr></thead>";
      const tb = el("tbody");
      for (const h of hh) { const tr = el("tr", h.record_id === x.record_id ? "me" : null); [h.name, h.birth_year ?? "?", h.role || ""].forEach(v => tr.appendChild(el("td", null, v))); tb.appendChild(tr); }
      t.appendChild(tb); house.appendChild(t);
    }
    body.append(why, house);
    det.appendChild(body);
    return det;
  }

  function emptyState(q) {
    const p = person(active), box = el("div", "sp-empty");
    const a = el("div", "sp-art"); a.appendChild(art("art-route")); box.appendChild(a);
    box.appendChild(el("h3", null, "Sporet stopper her, foreløpig"));
    const where = q.birthplace ? ` i ${q.birthplace}` : "";
    box.appendChild(el("p", "sp-muted",
      `Vi fant ingen i folketellingene ${S.coverage.years.join(", ")} som passer ${fullName(p) || q.given_name}, født omkring ${q.birth_year}${where}. ` +
      `${pronoun(q.sex)} kan være oppført med et annet gårdsnavn eller farsnavn, eller ha bodd utenfor ${S.coverage.counties.join(", ")}.`));
    const acts = el("div", "sp-actions");
    if (String(q.birth_year_tolerance) !== "5") acts.appendChild(btn("Let med ± 5 år", "sp-btn sp-btn-primary", () => { form.elements.birth_year_tolerance.value = "5"; search(); }));
    else if (q.birthplace) acts.appendChild(btn("Let uten fødested", "sp-btn sp-btn-primary", () => { form.elements.birthplace.value = ""; search(); }));
    acts.appendChild(btn("Endre søket", "sp-btn sp-btn-quiet", () => form.elements.given_name.focus()));
    box.appendChild(acts);
    return box;
  }

  function decide(x, status) {
    const d = decisions(), prev = d[x.record_id];
    if (prev && prev.status === status) delete d[x.record_id];
    else d[x.record_id] = { status, confidence: x.confidence, year: x.year, name: x.record_name,
      place: [x.farm, x.municipality].filter(Boolean).join(", "), source: `${x.source} · ${x.record_id}`,
      reasons: x.explanation.map(p => `${PART[p.name] || p.name}: ${nb(p.explanation)}`) };
    save(); renderResults();
  }

  function chapter(n) {
    $("#payload").value = JSON.stringify({ query: queryFor(n), decisions: person(n).kept || {} });
    $("#report-form").submit();
  }

  /* ---------------- norsk tekst for motorens forklaringer ---------------- */
  const PART = { "given name": "Fornavn", surname: "Etternavn", "birth year": "Fødselsår", place: "Sted", family: "Familie" };
  const REL = { father: "far", mother: "mor", spouse: "ektefelle" };
  const RULES = [
    [/^same given name \((.*)\)$/, m => `samme fornavn (${m[1]})`],
    [/^(.*) and (.*) are spellings of the same name$/, m => `${m[1]} og ${m[2]} er skrivemåter av samme navn`],
    [/^no surname given$/, () => "etternavn ikke oppgitt"],
    [/^no surname match$/, () => "etternavnet stemmer ikke"],
    [/^same patronymic root \((.*)\), different form$/, m => `samme farsnavn (${m[1]}), annen form`],
    [/^same patronymic \((.*)\)$/, m => `samme farsnavn (${m[1]})`],
    [/^different patronymics \((.*)\)$/, m => `ulike farsnavn (${m[1]})`],
    [/^surname (\S+) matches farm name (.*)$/, m => `etternavnet ${m[1]} stemmer med gårdsnavnet ${m[2]}`],
    [/^surname (\S+) vs (.*)$/, m => `etternavn ${m[1]} mot ${m[2]}`],
    [/^record surname (.*) is her husband's surname$/, m => `etternavnet ${m[1]} er ektemannens`],
    [/^no surname in record; father (.*) implies the patronymic$/, m => `ikke etternavn i posten; faren ${m[1]} gir farsnavnet`],
    [/^no surname in record$/, () => "ikke etternavn i posten"],
    [/^record patronymic (\S+) fits father (.*)$/, m => `farsnavnet ${m[1]} passer med faren ${m[2]}`],
    [/^record has no birth year$/, () => "fødselsår mangler i posten"],
    [/^same birth year \((\d+)\)$/, m => `samme fødselsår (${m[1]})`],
    [/^born (\d+), (\d+) years? ?\(?s?\)? from (\d+) \(within ±(\d+)\)$/, m => `født ${m[1]}, ${m[2]} år fra ${m[3]} (innenfor ± ${m[4]})`],
    [/^born (\d+), (\d+) year\(s\) from (\d+) \(within ±(\d+)\)$/, m => `født ${m[1]}, ${m[2]} år fra ${m[3]} (innenfor ± ${m[4]})`],
    [/^born (\d+), (\d+) years from (\d+) \(outside ±(\d+)\)$/, m => `født ${m[1]}, ${m[2]} år fra ${m[3]} (utenfor ± ${m[4]})`],
    [/^record has no place$/, () => "sted mangler i posten"],
    [/^same place \((.*)\)$/, m => `samme sted (${m[1]})`],
    [/^(.*) vs (.*): likely the same place, spelled differently$/, m => `${m[1]} mot ${m[2]}: trolig samme sted, annen skrivemåte`],
    [/^same county \((.*)\), different parish$/, m => `samme fylke (${m[1]}), annet sogn`],
    [/^same county \((.*)\)$/, m => `samme fylke (${m[1]})`],
    [/^(.*) vs (.*): does not match$/, m => `${m[1]} mot ${m[2]}: stemmer ikke`],
    [/^(father|mother|spouse) not listed in record$/, m => `${REL[m[1]]} er ikke oppført`],
    [/^(father|mother|spouse) (.*) vs (.*): match \(first name; surname can change at marriage\)$/, m => `${REL[m[1]]} ${m[2]} mot ${m[3]}: stemmer (fornavn; etternavnet kan endres ved giftemål)`],
    [/^(father|mother|spouse) (.*) vs (.*): match$/, m => `${REL[m[1]]} ${m[2]} mot ${m[3]}: stemmer`],
    [/^(father|mother|spouse) (.*) vs (.*): CONFLICT$/, m => `${REL[m[1]]} ${m[2]} mot ${m[3]}: motstrid`],
    [/^(father|mother|spouse) (.*) vs (.*): similarity ([\d.]+)$/, m => `${REL[m[1]]} ${m[2]} mot ${m[3]}: likhet ${m[4].replace(".", ",")}`],
    [/^(.*) vs (.*): similarity ([\d.]+)$/, m => `${m[1]} mot ${m[2]}: likhet ${m[3].replace(".", ",")}`],
  ];
  const one = s => { for (const [re, f] of RULES) { const m = s.match(re); if (m) return f(m); } return s; };
  // family explanations join one clause per relative with "; " (a clause may itself contain "; ")
  const nb = s => String(s).split(/; (?=(?:father|mother|spouse) )/).map(one).join("; ");

  const NOTES = [
    [/^parents\/spouse in this record are inferred/, () => "Foreldre og ektefelle er lest ut fra hvem som bodde i husstanden, ikke fra en oppgitt kobling."],
    [/^birth year in record is computed from stated age/, () => "Fødselsåret er regnet ut fra oppgitt alder og kan bomme med et år."],
    [/^close rival: (\S+)/, m => `En annen post (${m[1]}) passer nesten like godt og ser ut til å være en annen person.`],
    [/^\d+ listed family member\(s\) conflict/, () => "Et familiemedlem i posten stemmer ikke med treet ditt."],
    [/^record lists none of the queried family members/, () => "Posten nevner ingen fra familien i treet ditt, så en navnebror kan ikke utelukkes."],
    [/^birth year outside tolerance/, () => "Fødselsåret ligger lenger unna enn slingringsmonnet."],
    [/^sex in record/, () => "Kjønnet i posten stemmer ikke."],
    [/^fields were extracted from the transcription by a model/, () => "Opplysningene er lest ut av transkripsjonen med en modell. Sjekk kilden."],
  ];
  const noteNb = n => { for (const [re, f] of NOTES) { const m = n.match(re); if (m) return f(m); } return n; };

  function clueLine(x) {
    const has = re => x.notes.some(n => re.test(n));
    if (has(/^\d+ listed family member/)) return "Et familiemedlem her stemmer ikke med treet ditt.";
    const weak = x.explanation.filter(p => p.score < 0.6).map(p => (PART[p.name] || p.name).toLowerCase());
    if (weak.length) return "Passer ikke på " + weak.join(" og ") + ".";
    if (has(/^close rival/)) return "Passer godt, men en navnebror i nærheten passer nesten like godt.";
    if (has(/^record lists none of the queried family/)) return "Passer, men nevner ingen fra familien i treet ditt.";
    if (x.explanation.find(p => p.name === "family" && p.score >= 0.9)) return "Navn, fødselsår og familie stemmer.";
    return "Navn, fødselsår og sted stemmer.";
  }

  /* ---------------- nye spor i slekta: foreldre fra husstanden ---------------- */
  const gen_s = name => (/[sxz]$/i.test(name) ? `${name}'` : `${name}s`);   // Norsk genitiv: Oles, Hans'
  const missingParents = n => !person(2 * n) || !person(2 * n + 1);
  const seekers = () => Object.keys(tree).map(Number)
    .filter(n => traceable(person(n)) && missingParents(n))
    .sort((a, b) => gen(b) - gen(a) || a - b);

  $("#find-relatives").addEventListener("click", () => findRelatives(seekers()));
  $("#rel-back").addEventListener("click", () => route());

  async function findRelatives(list) {
    show("relatives-view");
    const host = $("#rel-results"), prog = $("#rel-progress");
    host.innerHTML = ""; prog.textContent = "";
    if (!list.length) { host.appendChild(noSeekers()); return; }
    list = list.slice(0, 8);
    let any = false;
    for (const [i, n] of list.entries()) {
      const p = person(n);
      prog.textContent = `Leter etter foreldrene til ${fullName(p)} (${i + 1} av ${list.length}) …`;
      let data;
      try {
        const res = await fetch("/api/relatives", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ person: queryFor(n), kept: keptOf(p).map(([id]) => id) }) });
        data = await res.json();
        if (!res.ok) throw new Error(data.error);
      } catch { data = { suggestions: [] }; }
      const sugg = data.suggestions.filter(sg => (sg.relation === "father" ? !person(2 * n) : !person(2 * n + 1)));
      const group = el("section", "rel-group");
      group.appendChild(el("h2", null, `Foreldrene til ${fullName(p)}`));
      if (!sugg.length) group.appendChild(el("p", "muted", `Ingen nye spor etter foreldrene til ${first(p)}, foreløpig. Følg sporet til ${first(p)} for å se alle treffene.`));
      sugg.forEach((sg, j) => group.appendChild(relativeCard(n, sg, !any && j === 0 && sg.confidence === "high")));
      if (sugg.length) any = true;
      host.appendChild(group);
    }
    prog.textContent = any ? "Ferdig. Legg til dem som stemmer, og let igjen for neste generasjon." : "Ferdig. Ingen nye spor denne gangen.";
  }

  function noSeekers() {
    const box = el("div", "sp-empty");
    const a = el("div", "sp-art"); a.appendChild(art("art-route")); box.appendChild(a);
    const anyTraceable = Object.values(tree).some(traceable);
    if (anyTraceable) {
      box.appendChild(el("h3", null, "Alle som kan spores, har foreldre i treet"));
      box.appendChild(el("p", "sp-muted", "Legg til flere personer bakover, eller følg sporet til noen for å finne flere kilder."));
    } else {
      box.appendChild(el("h3", null, "Treet ditt når ikke folketellingene ennå"));
      box.appendChild(el("p", "sp-muted", `Vi kan bare lete etter personer født i ${CUTOFF} eller tidligere, i folketellingene for ${S.coverage.counties.join(", ")}. ` +
        "Legg til den eldste du vet om, gjerne en besteforelder eller oldeforelder, så leter vi videre derfra."));
    }
    const acts = el("div", "sp-actions");
    acts.appendChild(btn("Tilbake til treet", "sp-btn sp-btn-primary", () => route()));
    box.appendChild(acts);
    return box;
  }

  function relativeCard(n, sg, featured) {
    const child = person(n), ev = sg.evidence[0], isFather = sg.relation === "father";
    const word = isFather ? "far" : "mor";
    const card = el("article", (featured ? "sp-find" : "sp-card") + " rel-card");
    const head = el("div", featured ? "sp-find-head" : "rel-head");
    head.appendChild(el("span", "sp-eyebrow" + (featured ? "" : " sp-muted"), "Nytt spor"));
    const bw = el("span"); if (featured) bw.style.marginLeft = "auto";
    bw.appendChild(badge(sg.confidence === "high" ? "probable" : "unverified")); head.appendChild(bw);
    const body = featured ? el("div", "sp-find-body") : card;
    body.appendChild(el("h3", "sp-find-title", `Kanskje ${gen_s(first(child))} ${word}: ${sg.name}`));
    const born = sg.birth_year ? `, født ${sg.birth_year}${sg.birthplace ? " i " + sg.birthplace : ""}` : "";
    let story = `I folketellingen ${ev.year} bor ${first(child)} på ${ev.place || "et oppført sted"}, sammen med ${sg.name}${born}. ` +
      `Husstanden tyder på at ${isFather ? "han er faren" : "hun er moren"} til ${first(child)}.`;
    if (sg.evidence.length > 1) story += ` ${isFather ? "Han" : "Hun"} står sammen med ${first(child)} i ${sg.evidence.length} folketellinger (${sg.evidence.map(e => e.year).join(" og ")}).`;
    if (sg.also_written && sg.also_written.length) story += ` Navnet er også skrevet ${sg.also_written.map(v => "«" + v + "»").join(", ")}.`;
    if (ev.how === "kept") story += ` Posten er en du allerede har lagt til.`;
    if (sg.rivals) story += ` Det finnes ${sg.rivals + 1} mulige ${isFather ? "fedre" : "mødre"} i kildene, fordi flere med samme navn passer. Velg den som stemmer med det du vet.`;
    body.appendChild(el("p", "sp-find-story", story));
    body.appendChild(el("div", "sp-scan", "«" + [sg.name, sg.role, sg.birth_year, sg.birthplace].filter(v => v != null && v !== "").join(", ") + "»"));
    body.appendChild(el("div", "sp-source", ev.source));
    const acts = el("div", "sp-actions");
    const add = btn("Legg til i treet", featured ? "sp-btn sp-btn-primary" : "sp-btn", () => addParent(n, sg, card));
    acts.appendChild(add);
    if (ev.link) { const a = el("a", "sp-btn", "Se kilden"); a.href = ev.link; a.target = "_blank"; a.rel = "noopener"; acts.appendChild(a); }
    acts.appendChild(btn("Ikke denne", "sp-btn sp-btn-quiet", () => { card.classList.add("aside"); }));
    body.appendChild(acts);
    if (featured) card.append(head, body); else card.prepend(head);
    return card;
  }

  function addParent(n, sg, card) {
    const slot = sg.relation === "father" ? 2 * n : 2 * n + 1;
    if (person(slot)) { card.classList.add("aside"); return; }
    const ev = sg.evidence[0];
    const parent = cleanPerson({ given_name: sg.given_name, surname: sg.surname, birth_year: String(sg.birth_year || ""), birthplace: sg.birthplace || "" });
    if (sg.record_id) parent.kept = { [sg.record_id]: { status: "confirmed", confidence: sg.confidence, year: ev.year, name: sg.name,
      place: ev.place, source: ev.source.replace(ev.child_record_id, sg.record_id), reasons: ["Funnet i husstanden til " + ev.child_name] } };
    tree[String(slot)] = parent;
    const child = person(n); child.kept = child.kept || {};
    if (!child.kept[ev.child_record_id]) child.kept[ev.child_record_id] = { status: "confirmed", confidence: sg.confidence, year: ev.year,
      name: ev.child_name, place: ev.place, source: ev.source, reasons: [] };
    save();
    card.classList.add("done");
    const b = card.querySelector(".sp-actions .sp-btn"); b.textContent = "Lagt til i treet"; b.disabled = true;
    // rivals for the same parent are now set aside
    card.parentElement.querySelectorAll(".rel-card").forEach(c => { if (c !== card && c.querySelector(".sp-find-title").textContent.includes(` ${sg.relation === "father" ? "far" : "mor"}:`)) c.classList.add("aside"); });
  }

  /* ---------------- eksempelfamilien (oppdiktet) ---------------- */
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
  if (ex) ex.addEventListener("click", () => { tree = JSON.parse(JSON.stringify(EXAMPLE)); focus = 32; save(); route(); });

  route();
})();
