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
  const LAST_CENSUS = S.coverage.years.length ? Math.max(...S.coverage.years) : 1910;
  const COUNTIES = S.coverage.counties.length ? S.coverage.counties.join(", ") : "ingen fylker ennå";
  // born after the last census we have, but old enough: they aren't in it, their parents probably are
  const afterCensus = p => traceable(p) && Number(p.birth_year) > LAST_CENSUS;
  const objPron = n => (sexOf(n) === "m" ? "ham" : sexOf(n) === "f" ? "henne" : "personen");
  const subjPron = n => (sexOf(n) === "m" ? "han" : sexOf(n) === "f" ? "hun" : "personen");
  /* parent birth year estimated from the child's: fathers about 30, mothers about 27 years older */
  const estimateFor = n => { const c = person(Math.floor(n / 2)); return n > 1 && c && c.birth_year ? Number(c.birth_year) - (n % 2 === 0 ? 30 : 27) : null; };
  const bornText = p => (p.birth_year ? (p.birth_year_estimated ? `omkr. ${p.birth_year}` : p.birth_year) : "?");
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
      sex: sexOf(n), birth_year_tolerance: p.birth_year_estimated ? "5" : "2", county: "", name_variants: "",
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
  function show(view) { for (const id of ["start-view", "tree-view", "search-view", "relatives-view", "investigate-view"]) $("#" + id).hidden = id !== view; window.scrollTo(0, 0); }
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
      const b = el("button", "tnode" + (n === focus ? " active" : "") + (p.uncertain ? " uncertain" : ""));
      b.type = "button"; b.dataset.n = n;
      b.style.left = x[n] + "px"; b.style.top = y(n) + "px";
      b.setAttribute("aria-pressed", String(n === focus));
      b.setAttribute("aria-label", `${fullName(p)}, ${relationLabel(n).toLowerCase()}`);
      b.appendChild(el("span", "tn", fullName(p) || "(uten navn)"));
      const ty = el("span", "ty");
      const yrs = p.birth_year ? (p.death_year ? `${bornText(p)}–${p.death_year}` : `${bornText(p)}–`) : "?";
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
    fact("Født", [p.birth_year ? (p.birth_year_estimated ? `omkring ${p.birth_year} (anslått)` : p.birth_year) : "?", p.birthplace].filter(Boolean).join(", "));
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
    else if (afterCensus(p)) state = `Født etter siste folketelling vi har (${LAST_CENSUS}), så ${subjPron(n)} står ikke i den. Foreldrene gjør trolig det.`;
    else if (kept.length) state = `Funnet i ${kept.length} ${kept.length === 1 ? "kilde" : "kilder"}. Let gjerne videre.`;
    else state = "Klar til å spores i folketellingene.";
    if (p.uncertain) state = "Usikker: lagt til uten nok bevis. " + state;
    card.appendChild(el("p", "state", state));

    const acts = el("div", "sp-actions");
    if (afterCensus(p) && (!f || !m)) acts.appendChild(btn(`Let etter familien i ${LAST_CENSUS}`, "sp-btn sp-btn-primary", () => findRelatives([n])));
    else if (traceable(p) && !afterCensus(p)) acts.appendChild(btn(kept.length ? "Let videre" : "Følg sporet", "sp-btn sp-btn-primary", () => openTrail(n)));
    if (traceable(p) && !afterCensus(p) && (!f || !m)) acts.appendChild(btn("Let etter foreldrene", "sp-btn", () => findRelatives([n])));
    if (!f) acts.appendChild(btn("Legg til far", "sp-btn", () => edit(2 * n)));
    if (!m) acts.appendChild(btn("Legg til mor", "sp-btn", () => edit(2 * n + 1)));
    acts.appendChild(btn("Endre", "sp-btn", () => edit(n)));
    if (kept.length) acts.appendChild(btn("Les kapittelet", "sp-btn sp-btn-quiet", () => chapter(n)));
    card.appendChild(acts);
    pane.appendChild(card);

    if ((p.research || []).length) {
      const sec = el("details", "sp-card research-log");
      sec.appendChild(el("summary", "sp-eyebrow sp-muted", `Forskningslogg (${p.research.length})`));
      const ul = el("ul", "inv-log");
      p.research.slice().reverse().forEach(r => ul.appendChild(el("li", null, `${r.date}: ${r.text}`)));
      sec.appendChild(ul); pane.appendChild(sec);
    }

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
      if (d.given_name) {
        const old = person(editing) || {};
        if (old.birth_year_estimated && d.birth_year !== old.birth_year) delete old.birth_year_estimated;   // typed a real year
        if (!d.birth_year) { delete old.birth_year; delete old.birth_year_estimated; }
        tree[String(editing)] = Object.assign(old, d); focus = editing; save();
      }
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
      for (const h of hh) { const tr = el("tr", h.record_id === x.record_id ? "me" : null); [h.name, h.birth_year ?? "?", roleText(h.role)].forEach(v => tr.appendChild(el("td", null, v))); tb.appendChild(tr); }
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
      `${pronoun(q.sex)} kan være oppført med et annet gårdsnavn eller farsnavn, eller ha bodd utenfor ${COUNTIES}.`));
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
  // everyone missing a parent, oldest generation first
  const seekers = () => Object.keys(tree).map(Number).filter(missingParents).sort((a, b) => gen(b) - gen(a) || a - b);

  $("#find-relatives").addEventListener("click", () => findRelatives(seekers()));
  $("#rel-back").addEventListener("click", () => route());

  let lastList = [];
  async function findRelatives(list) {
    lastList = list;
    show("relatives-view");
    const host = $("#rel-results"), prog = $("#rel-progress");
    host.innerHTML = ""; prog.textContent = "";
    if (!list.length) { host.appendChild(noSeekers()); return; }
    list = list.slice(0, 10);
    let any = false;
    for (const [i, n] of list.entries()) {
      const p = person(n);
      if (!p) continue;
      prog.textContent = `Ser på ${fullName(p)} (${i + 1} av ${list.length}) …`;
      const group = el("section", "rel-group");
      host.appendChild(group);
      group.appendChild(el("h2", null, fullName(p)));
      group.appendChild(el("p", "rel", relationLabel(n)));
      if (!p.birth_year) {
        // no year: estimate one from the child rather than stop here
        const est = estimateFor(n);
        if (!est) { group.appendChild(yearHint(n)); continue; }
        Object.assign(p, { birth_year: String(est), birth_year_estimated: true }); save(); renderTree();
        group.appendChild(estimateNote(n));
      }
      let found = false;
      const dk = danishPlace(n), uncertain = !traceable(p) || afterCensus(p);
      if (dk || swedishPlace(n)) group.appendChild(elsewhereCard(n));
      if (!traceable(p)) {
        found = await leadsGroup(n, group, true);
        if (!found && !group.querySelector(".rel-card")) group.appendChild(livingHint(n));
      } else if (afterCensus(p)) {
        found = await familyGroup(n, group) || await leadsGroup(n, group, false);
      } else {
        found = await relativesGroup(n, group, any);
      }
      if (found) any = true;
      if (!dk && !swedishPlace(n) && (!found || uncertain)) {
        const e = elsewhereCard(n);
        if (found) { const d = el("details", "more-places"); d.appendChild(el("summary", null, "Andre steder å lete")); d.appendChild(e); group.appendChild(d); }
        else group.appendChild(e);
      }
      if (!group.dataset.state) group.dataset.state = found ? "clear" : "none";
    }
    const count = st => host.querySelectorAll(`.rel-group[data-state="${st}"]`).length;
    const parts = [count("clear") && `${count("clear")} med et tydelig beste spor`, count("unclear") && `${count("unclear")} der du kan hjelpe oss å velge`,
      count("none") && `${count("none")} uten spor i Spor ennå`].filter(Boolean);
    prog.textContent = `Ferdig: ${parts.join(", ")}.`;
    renderSummary(host);
  }

  async function relativesGroup(n, group, any) {
    const p = person(n);
    let data;
      try {
        const res = await fetch("/api/relatives", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ person: queryFor(n), kept: keptOf(p).map(([id]) => id) }) });
        data = await res.json();
        if (!res.ok) throw new Error(data.error);
      } catch { data = { suggestions: [] }; }
      const gone = new Set(p.rejected || []);
      const sugg = data.suggestions.filter(sg => (sg.relation === "father" ? !person(2 * n) : !person(2 * n + 1)) && !gone.has(sg.record_id));
      if (!sugg.length) group.appendChild(el("p", "muted", `Ingen nye spor etter foreldrene til ${first(p)} i husstandene ${subjPron(n)} står i, foreløpig. Følg sporet til ${first(p)} for å se alle treffene.`));
      sugg.forEach((sg, j) => group.appendChild(relativeCard(n, sg, !any && j === 0 && sg.confidence === "high")));
      if (sugg.length) group.dataset.state = sugg.some(sg => sg.confidence === "high" && !sg.rivals) ? "clear" : "unclear";
      return sugg.length > 0;
  }

  function hintCard(title, text, actions) {
    const c = el("article", "sp-card rel-card");
    c.appendChild(el("span", "sp-eyebrow sp-muted", "Neste steg"));
    c.appendChild(el("h3", "sp-find-title", title));
    c.appendChild(el("p", "sp-muted", text));
    const a = el("div", "sp-actions"); actions.forEach(x => a.appendChild(x)); c.appendChild(a);
    return c;
  }

  function yearHint(n) {
    const p = person(n);
    return hintCard(`Når ble ${first(p)} født?`, "Legg til et fødselsår, gjerne et anslag, så ser vi om vi kan lete etter familien.",
      [btn(`Endre ${first(p)}`, "sp-btn", () => edit(n))]);
  }

  function estimateNote(n) {
    const p = person(n), child = person(Math.floor(n / 2));
    const box = el("p", "muted");
    box.append(`Vi vet ikke når ${first(p)} ble født, så vi har satt omkring ${p.birth_year} ut fra ${first(child)} (født ${child.birth_year}) og leter med god slingring. `);
    const b = btn("Skriv inn riktig år", "sp-btn sp-btn-quiet inline", () => edit(n));
    box.appendChild(b);
    return box;
  }

  function livingHint(n) {
    const p = person(n), by = Number(p.birth_year), fy = by - 30, my = by - 27;
    const old = Math.min(fy, my) <= CUTOFF;
    const acts = [];
    if (!person(2 * n)) acts.push(btn("Legg til far", "sp-btn", () => edit(2 * n)));
    if (!person(2 * n + 1)) acts.push(btn("Legg til mor", "sp-btn", () => edit(2 * n + 1)));
    return hintCard(`Foreldrene til ${first(p)}`,
      `${first(p)} er født ${bornText(p)}, innenfor levende minne, så vi søker ikke etter ${objPron(n)}. Foreldrene er trolig født omkring ${Math.min(fy, my)}–${Math.max(fy, my)}` +
      (old ? `, gamle nok til at vi kan lete etter dem. Legg dem til hvis du vet hvem de er, også uten fødselsår.` : `. Legg dem til hvis du vet hvem de er.`), acts);
  }

  // Census role codes, written out. Unknown codes are shown as they stand.
  const ROLES = { hf: "husfar", hm: "husmor", s: "sønn", d: "datter", tj: "tjener", tjd: "tjenestejente", tjg: "tjenestegutt",
    fl: "losjerende", b: "barn", sb: "sønnebarn", db: "datterbarn", fs: "føderådsmann", fk: "føderådskone" };
  const roleText = r => ROLES[(r || "").trim().toLowerCase()] || r || "";

  async function familyGroup(n, group) {
    const p = person(n);
    if (!p.surname) {
      group.appendChild(hintCard("Vi trenger et etternavn", `${first(p)} er født ${bornText(p)}, etter siste folketelling vi har. For å finne familien i ${LAST_CENSUS} leter vi etter navnet, så legg til etternavnet.`,
        [btn(`Endre ${first(p)}`, "sp-btn", () => edit(n))]));
      return false;
    }
    let data;
    try {
      const res = await fetch("/api/families", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ surname: p.surname, birth_year: p.birth_year, birthplace: p.birthplace || "" }) });
      data = await res.json();
      if (!res.ok) throw new Error(data.error);
    } catch { data = { families: [] }; }
    if (!data.families.length) {
      group.appendChild(el("p", "muted", `${first(p)} er født ${bornText(p)}, etter siste folketelling vi har, så vi lette etter foreldrene: familier med navnet ${p.surname} i folketellingen ${data.year || LAST_CENSUS}. Vi fant ingen. Spor har foreløpig folketellingene for ${COUNTIES}${p.birthplace ? `, så bodde familien i ${p.birthplace} eller et annet sted utenfor, finner vi den ikke her ennå` : `. Bodde familien et annet sted, finner vi den ikke her ennå`}.`));
      return false;
    }
    group.appendChild(el("p", "muted", `${first(p)} er født ${bornText(p)}, etter siste folketelling vi har (${data.year || LAST_CENSUS}). Vi lette etter familier med navnet ${p.surname} der foreldrene har riktig alder.`));
    choiceList(n, group, data.families, "family", data.total);
    return true;
  }

  function familyCard(n, fam) {
    const p = person(n), card = el("article", "sp-card rel-card");
    const head = el("div", "rel-head");
    head.appendChild(el("span", "sp-eyebrow sp-muted", "Mulig familie"));
    head.appendChild(badge("unverified"));
    card.appendChild(head);
    card.appendChild(el("h3", "sp-find-title", `${fam.farm ? `På ${fam.farm}, ` : "I "}${fam.place} i ${fam.year}`));
    const who = [fam.father && `${fam.father.name}, født ${fam.father.birth_year ?? "?"}`, fam.mother && `${fam.mother.name}, født ${fam.mother.birth_year ?? "?"}`].filter(Boolean);
    const kids = fam.members.filter(m => /^(s|d|søn|sønn|datter|deres|hans|hendes)/i.test(m.role || "")).length;
    card.appendChild(el("p", "sp-find-story", `${who.join(" og ")} bor her${kids ? ` med ${kids} barn` : ""}. Hvis ${first(p)} er født ${p.birth_year} i denne familien, kan de være foreldrene.`));
    const t = el("table"); t.innerHTML = "<thead><tr><th>Navn</th><th>Født</th><th>Oppført som</th></tr></thead>";
    const tb = el("tbody"); fam.members.forEach(m => { const tr = el("tr"); [m.name, m.birth_year ?? "?", roleText(m.role)].forEach(v => tr.appendChild(el("td", null, v))); tb.appendChild(tr); });
    t.appendChild(tb); card.appendChild(t);
    card.appendChild(el("div", "sp-source", fam.source));
    const acts = el("div", "sp-actions");
    acts.appendChild(btn("Undersøk nærmere", "sp-btn", () => investigate({ n, kind: "family", item: fam, card })));
    if (fam.link) { const a = el("a", "sp-btn", "Se kilden"); a.href = fam.link; a.target = "_blank"; a.rel = "noopener"; acts.appendChild(a); }
    acts.appendChild(btn("Ikke denne", "sp-btn sp-btn-quiet", () => reject(n, fam.source, card)));
    card.appendChild(acts);
    return card;
  }


  /* The father as a young man: born around 1900, he is a child in the last
     census, living with his own parents, so one find can add two generations. */
  async function leadsGroup(n, group, includeHeads) {
    const p = person(n), by = Number(p.birth_year);
    if (person(2 * n) || !p.surname || by - 55 > LAST_CENSUS) return false;
    const partner = n > 1 ? person(n ^ 1) : null;
    if (sexOf(n) === "f" && partner && partner.surname && partner.surname === p.surname) {
      group.appendChild(hintCard(`Pikenavnet til ${first(p)}`,
        `${p.surname} er trolig navnet ${first(p)} fikk da ${subjPron(n)} giftet seg med ${first(partner)}. Faren hennes bar et annet navn. ` +
        `Vet du pikenavnet, kan vi lete etter ham.`, [btn("Legg til pikenavnet", "sp-btn", () => edit(n))]));
      return false;
    }
    let data;
    try {
      const res = await fetch("/api/parent-leads", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ surname: p.surname, birth_year: by, birthplace: p.birthplace || birthplaceNear(n), include_heads: includeHeads }) });
      data = await res.json();
      if (!res.ok) throw new Error(data.error);
    } catch { data = { leads: [] }; }
    if (!data.leads.length) return false;
    const patr = data.leads.some(l => l.why === "given");
    group.appendChild(el("p", "muted",
      `Faren til ${first(p)} er trolig født omkring ${by - 30}, og står da i folketellingen ${data.year}` +
      `${includeHeads ? ", ofte som barn hos sine egne foreldre" : ""}. Vi lette etter menn i riktig alder med navnet ${p.surname}` +
      `${patr ? " eller et fornavn navnet kan komme av" : ""}.`));
    choiceList(n, group, data.leads, "lead", data.total);
    return true;
  }

  // a place to rank by when the person has none: the nearest descendant's birthplace
  function birthplaceNear(n) { for (let c = Math.floor(n / 2); c >= 1; c = Math.floor(c / 2)) if (person(c) && person(c).birthplace) return person(c).birthplace; return ""; }

  function leadCard(n, l) {
    const p = person(n), card = el("article", "sp-card rel-card"), m = l.person, by = Number(p.birth_year);
    const head = el("div", "rel-head");
    head.appendChild(el("span", "sp-eyebrow sp-muted", `Kanskje ${gen_s(first(p))} far`));
    head.appendChild(badge("unverified"));
    card.appendChild(head);
    card.appendChild(el("h3", "sp-find-title", `${m.name}, født ${m.birth_year}`));
    const at = `${l.farm ? `på ${l.farm}, ` : "i "}${l.place}`;
    const parents = [l.father, l.mother].filter(Boolean);
    let story = l.head ? `I ${l.year} er han husfar ${at}${l.wife ? `, gift med ${l.wife.name}, født ${l.wife.birth_year ?? "?"}` : ""}.`
      : parents.length ? `I ${l.year} bor han ${at} hos ${parents.length === 2 ? "foreldrene" : l.father ? "faren" : "moren"} ${parents.map(x => `${x.name} (født ${x.birth_year ?? "?"})`).join(" og ")}.`
      : `I ${l.year} bor han ${at}, oppført som ${roleText(m.role) || "ukjent"}.`;
    story += l.why === "given" ? ` Navnet ${p.surname} kan komme av fornavnet hans.` : ` Han bærer navnet ${p.surname}.`;
    story += ` Han er ${by - m.birth_year} år eldre enn ${first(p)}${p.birth_year_estimated ? " (ut fra anslaget)" : ""}.`;
    if (parents.length) story += ` Stemmer det, får du også ${gen_s(first(p))} besteforeldre.`;
    card.appendChild(el("p", "sp-find-story", story));
    card.appendChild(el("div", "sp-source", l.source));
    const acts = el("div", "sp-actions");
    acts.appendChild(btn("Undersøk nærmere", "sp-btn", () => investigate({ n, kind: "lead", item: l, card })));
    if (l.link) { const a = el("a", "sp-btn", "Se kilden"); a.href = l.link; a.target = "_blank"; a.rel = "noopener"; acts.appendChild(a); }
    acts.appendChild(btn("Ikke denne", "sp-btn sp-btn-quiet", () => reject(n, l.source, card)));
    card.appendChild(acts);
    return card;
  }

  function addLead(n, l, card, withGrandparents, withWife) {
    const place = [l.farm, l.place].filter(Boolean).join(", ");
    const put = (slot, x, why) => {
      if (!x || person(slot)) return;
      const np = cleanPerson({ given_name: x.given_name, surname: x.surname, birth_year: String(x.birth_year || ""), birthplace: x.birthplace || "" });
      np.kept = { [x.record_id]: { status: "confirmed", confidence: "medium", year: l.year, name: x.name, place,
        source: l.source.replace(/ · \S+$/, ` · ${x.record_id}`), reasons: [why] } };
      tree[String(slot)] = np;
    };
    put(2 * n, l.person, `Mulig far til ${fullName(person(n))}`);
    if (withWife) put(2 * n + 1, l.wife, `Mulig mor til ${fullName(person(n))}`);
    if (withGrandparents) { put(4 * n, l.father, `Foreldre til ${l.person.name} i ${l.year}`); put(4 * n + 1, l.mother, `Foreldre til ${l.person.name} i ${l.year}`); }
    save();
    card.classList.add("done");
    card.querySelectorAll(".sp-actions button").forEach(b => { b.disabled = true; });
    card.querySelector(".sp-actions .sp-btn").textContent = "Lagt til i treet";
    card.parentElement.querySelectorAll(".rel-card").forEach(c => { if (c !== card && !c.classList.contains("done")) c.classList.add("aside"); });
  }

  /* When Spor's own censuses run out, say where the trail goes on. Spor never
     fetches these sites; the links are for the reader. */
  const DK_PLACES = new Set(("danmark denmark københavn kjøbenhavn aarhus århus odense aalborg ålborg randers esbjerg kolding horsens vejle viborg silkeborg " +
    "herning roskilde næstved fredericia helsingør svendborg holstebro haderslev skive sønderborg frederikshavn hjørring thisted nykøbing " +
    "slagelse holbæk hillerød grenaa grenå struer lemvig ribe tønder aabenraa middelfart nyborg faaborg skagen").split(" "));
  function danishPlace(n) {
    for (let c = n; c >= 1; c = Math.floor(c / 2)) {
      const bp = person(c) && person(c).birthplace;
      if (bp && bp.toLowerCase().split(/[^a-zæøåäö]+/).some(w => DK_PLACES.has(w))) return bp;
    }
    return "";
  }


  // Swedish birthplaces: many Østfold and Trøndelag families came from Bohuslän,
  // Värmland, Jämtland and Dalsland for the stone and timber work
  const SE_PLACES = new Set(("sverige sverge sweden bohuslän bohuslen bohus värmland vermland jämtland jemtland dalsland härjedalen " +
    "skee tanum ed näsinge idefjorden strömstad göteborg gøteborg stockholm nyköping södermanland sødermanland skaraborg " +
    "älvsborg elfsborg uddevalla karlstad arvika glava stugun östersund kalmar malmö").split(" "));
  function swedishPlace(n) {
    for (let c = n; c >= 1; c = Math.floor(c / 2)) {
      const bp = person(c) && person(c).birthplace;
      if (bp && bp.toLowerCase().split(/[^a-zæøåäö]+/).some(w => SE_PLACES.has(w))) return bp;
    }
    return "";
  }


  /* One suggestion at a time. The best one is shown as a card with a plain
     verdict; when several fit about equally, a question the reader may know
     the answer to narrows them down; the rest wait in a compact table. */
  // "Ikke denne" is remembered on the person, so a rejected suggestion doesn't come back
  const keyOf = src => src.split(" · ").pop();
  function reject(n, src, card) {
    const p = person(n); p.rejected = [...new Set([...(p.rejected || []), keyOf(src)])]; save();
    card.classList.add("aside");
  }

  function choiceList(n, group, items, kind, total) {
    const p = person(n), box = el("div", "choice");
    const gone = new Set(p.rejected || []);
    const hidden = items.filter(it => gone.has(keyOf(it.source))).length;
    items = items.filter(it => !gone.has(keyOf(it.source)));
    if (hidden) group.appendChild(el("p", "choice-filter", `${hidden} forslag du har avvist tidligere, er skjult.`));
    if (!items.length) { group.appendChild(el("p", "muted", "Du har avvist alle forslagene vi har.")); group.dataset.state = "none"; return; }
    group.appendChild(box);
    const make = it => (kind === "lead" ? leadCard(n, it) : familyCard(n, it));
    const parentOf = it => (kind === "lead" ? it.person : it.father || it.mother);
    const firstName = x => ((x && x.given_name) || "").split(" ")[0];
    const facets = [
      { id: "place", q: `Vet du hvor familien til ${first(p)} bodde rundt ${items[0].year}?`, key: it => it.place },
      { id: "name", q: `Vet du hva faren til ${first(p)} het til fornavn?`, key: it => firstName(kind === "lead" ? it.person : it.father) },
    ];
    const render = (list, answers) => {
      box.innerHTML = "";
      // clear only when the best is a strong match (place, name and family fit) and well ahead of the next
      const strong = list[0].score >= 3, clear = strong && (list.length === 1 || list[0].score - list[1].score >= 2);
      group.dataset.state = clear ? "clear" : "unclear";
      if (answers.length) {
        const f = el("p", "choice-filter");
        f.append(`Du svarte: ${answers.map(a => a.label).join(" · ")}. `);
        f.appendChild(btn("Nullstill", "sp-btn sp-btn-quiet inline", () => render(items, [])));
        box.appendChild(f);
      }
      if (!list.length) { box.appendChild(el("p", "muted", "Ingen av forslagene passer med det du vet. Da bodde familien trolig et annet sted enn Spor dekker ennå.")); return; }
      const more = !answers.length && total > 1 ? ` (av ${total} mulige)` : "";
      box.appendChild(el("p", "choice-verdict", clear
        ? (list.length === 1 ? "Bare ett forslag passer, og det passer godt." : `Beste spor. Det passer klart bedre enn de ${list.length - 1} andre.`)
        : list.length === 1 ? `Bare ett forslag, og det er svakt. Sjekk kilden før du legger det til.`
        : (() => { const k = list.filter(x => list[0].score - x.score <= 1).length;
            return k > 8 ? `Mange forslag passer omtrent like godt${more}. Svar på spørsmålet, så snevrer vi det inn.`
              : `${k} forslag passer omtrent like godt${more}. Dette er det best rangerte, men det er ikke sikkert.`; })()));
      // when it's unclear, ask first: the answer decides which card is worth reading
      if (!clear) {
        const asked = answers.map(a => a.id);
        const f = facets.find(f => !asked.includes(f.id) && new Set(list.map(f.key).filter(Boolean)).size >= 2);
        if (f) box.appendChild(questionCard(f, list, answers, render));
      }
      let top = make(list[0]);
      box.appendChild(top);
      if (list.length > 1) {
        const d = el("details", "choice-others");
        d.appendChild(el("summary", null, `Se ${list.length - 1} andre forslag`));
        const t = el("table");
        t.innerHTML = `<thead><tr><th>${kind === "lead" ? "Mulig far" : "Foreldre"}</th><th>Født</th><th>Bodde</th><th></th></tr></thead>`;
        const tb = el("tbody");
        list.slice(1).forEach(it => {
          const tr = el("tr");
          const who = kind === "lead" ? it.person.name : [it.father, it.mother].filter(Boolean).map(x => x.name).join(" og ");
          const born = kind === "lead" ? it.person.birth_year : [it.father, it.mother].filter(Boolean).map(x => x.birth_year ?? "?").join(", ");
          [who, born, [it.farm, it.place].filter(Boolean).join(", ")].forEach(v => tr.appendChild(el("td", null, v)));
          const td = el("td");
          td.appendChild(btn("Vis", "sp-btn sp-btn-quiet inline", () => { const c = make(it); top.replaceWith(c); top = c; c.scrollIntoView({ block: "nearest", behavior: "smooth" }); }));
          tr.appendChild(td); tb.appendChild(tr);
        });
        t.appendChild(tb); d.appendChild(t); box.appendChild(d);
      }
    };
    render(items, []);
  }

  function questionCard(f, list, answers, render) {
    const c = el("div", "choice-q");
    c.appendChild(el("span", "sp-eyebrow sp-muted", "Hjelp oss å velge"));
    c.appendChild(el("p", "choice-q-text", f.q));
    const counts = new Map();
    list.forEach(it => { const v = f.key(it); if (v) counts.set(v, (counts.get(v) || 0) + 1); });
    const acts = el("div", "sp-actions");
    [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6).forEach(([v, k]) =>
      acts.appendChild(btn(`${v}${k > 1 ? ` (${k})` : ""}`, "sp-btn", () => render(list.filter(it => f.key(it) === v), [...answers, { id: f.id, label: v }]))));
    acts.appendChild(btn("Et annet", "sp-btn sp-btn-quiet", () => render(list.filter(it => !counts.has(f.key(it))), [...answers, { id: f.id, label: "et annet" }])));
    acts.appendChild(btn("Vet ikke", "sp-btn sp-btn-quiet", () => render(list, [...answers, { id: f.id, label: "vet ikke" }])));
    c.appendChild(acts);
    return c;
  }

  /* A line per person at the top, so the reader sees where to start. */
  function renderSummary(host) {
    const groups = [...host.querySelectorAll(".rel-group")];
    if (groups.length < 2) return;
    const nav = el("nav", "rel-summary");
    nav.setAttribute("aria-label", "Oversikt");
    const label = { clear: "Tydelig spor", unclear: "Trenger svar fra deg", none: "Se neste steg" };
    groups.forEach((g, i) => {
      g.id = g.id || `rel-${i}`;
      const a = el("a", `rel-chip ${g.dataset.state}`);
      a.href = "#" + g.id;
      a.appendChild(el("b", null, g.querySelector("h2").textContent));
      a.appendChild(el("span", null, label[g.dataset.state] || ""));
      nav.appendChild(a);
    });
    host.prepend(nav);
  }


  /* ---------------- undersøk nærmere: bygg bevis før noe legges til ---------------- */
  // A suggestion is only a lead. Here the reader sees what the tree knows next to
  // what the source says, Spor looks for the same person in other censuses, and
  // the reader answers what only the family knows. Adding is offered once the
  // evidence reaches "Sannsynlig"; below that it can only be added marked uncertain.
  let invReturnY = 0;
  $("#inv-back").addEventListener("click", () => { show("relatives-view"); window.scrollTo(0, invReturnY); });

  function candidateOf({ n, kind, item }) {
    if (kind === "lead") return { rec: item.person, rel: "far", people: [["far", item.person]],
      grand: [["farfar", item.father], ["farmor", item.mother]].filter(([, x]) => x), year: item.year, place: item.place, farm: item.farm, link: item.link };
    if (kind === "family") return { rec: item.father || item.mother, rel: item.father && item.mother ? "foreldre" : item.father ? "far" : "mor",
      people: [["far", item.father], ["mor", item.mother]].filter(([, x]) => x), grand: [], year: item.year, place: item.place, farm: item.farm, link: item.link };
    const ev = item.evidence[0], rel = item.relation === "father" ? "far" : "mor";
    return { rec: item, rel, people: [[rel, item]], grand: [], year: ev.year, place: ev.place, farm: "", link: ev.link, sameHouse: true };
  }

  const norm = s => (s || "").toLowerCase().normalize("NFKD").replace(/[^a-zæøå]/g, "");
  const firstOf = x => ((x && (x.given_name || x.name)) || "").split(" ")[0];

  async function investigate(inv) {
    invReturnY = window.scrollY;
    const { n } = inv, p = person(n), c = candidateOf(inv), rid = c.rec.record_id;
    const store = ((p.investigations = p.investigations || {})[rid] = (p.investigations || {})[rid] || { answers: {}, sourceChecked: false });
    show("investigate-view");
    const host = $("#inv"); host.innerHTML = "";
    const who = c.people.map(([, x]) => x.name).join(" og ");
    host.appendChild(el("span", "sp-eyebrow sp-muted", "Undersøker et spor"));
    host.appendChild(el("h1", "title", `Er ${who} ${c.rel === "foreldre" ? "foreldrene" : c.rel === "far" ? "faren" : "moren"} til ${first(p)}?`));
    const meter = el("div", "inv-meter"); host.appendChild(meter);
    const body = el("div", "inv-body"); host.appendChild(body);
    body.appendChild(el("p", "muted", "Ser etter den samme personen i de andre folketellingene …"));

    let data = { elsewhere: [], household: [] };
    try {
      const res = await fetch("/api/investigate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ record_id: rid }) });
      if (res.ok) data = await res.json();
    } catch { /* keep going with what we have */ }
    body.innerHTML = "";

    // 1. what the tree knows next to what the source says
    const by = Number(p.birth_year), est = !!p.birth_year_estimated, rows = [];
    const surnameHit = c.people.some(([, x]) => norm(x.surname || x.name).includes(norm(p.surname)) && norm(p.surname));
    rows.push(["Navn", p.surname ? `${first(p)} heter ${p.surname}` : "Ukjent etternavn",
      c.people.map(([, x]) => x.name).join(", "),
      c.sameHouse ? ["ok", `${first(p)} står i samme husstand`] : surnameHit ? ["ok", "Samme navn"]
        : inv.kind === "lead" && inv.item.why === "given" ? ["part", `${p.surname} kan komme av fornavnet hans`] : ["part", "Navnet kan være et gårdsnavn"]]);
    const ages = c.people.map(([r, x]) => [r, x.birth_year ? by - x.birth_year : null]).filter(([, a]) => a != null);
    const ageOk = ages.length && ages.every(([r, a]) => (r === "mor" ? a >= 18 && a <= 42 : a >= 20 && a <= 45));
    rows.push(["Alder", `${first(p)} født ${bornText(p)}`, c.people.map(([r, x]) => `${r} født ${x.birth_year ?? "?"}`).join(", "),
      !ages.length ? ["unknown", "Ukjent alder"] : ageOk ? (est ? ["part", "Passer, men året er et anslag"] : ["ok", `${ages.map(([, a]) => a).join(" og ")} år eldre`])
        : ["part", `${ages.map(([, a]) => a).join(" og ")} år eldre, uvanlig`]]);
    const known = p.birthplace || birthplaceNear(n);
    const placeHit = known && (norm(c.place).includes(norm(known)) || norm(known).includes(norm(c.place)));
    rows.push(["Sted", known ? `${p.birthplace ? "Født" : "Slekta fra"} ${known}` : "Ukjent", [c.farm, c.place].filter(Boolean).join(", ") + ` (${c.year})` + (c.rec.birthplace && norm(c.rec.birthplace) !== norm(c.place) ? `, født ${c.rec.birthplace}` : ""),
      !known ? ["unknown", "Vi vet ikke hvor familien bodde"] : placeHit ? ["ok", "Samme sted"] : ["part", "Annet sted, folk flyttet"]]);
    const ns = data.namesakes;
    if (ns && ns.place) rows.push(["Navnelikhet", "", ns.count ? `${ns.count} ${ns.count === 1 ? "annen" : "andre"} ${ns.given_name} på samme alder i ${ns.place} i ${ns.year}` +
        (ns.examples.length ? `: ${ns.examples.map(x => [x.name, x.farm].filter(Boolean).join(", ")).join("; ")}` : "")
        : `Ingen andre ${ns.given_name} på samme alder i ${ns.place} i ${ns.year}`,
      !ns.count ? ["ok", "Den eneste med dette navnet og alderen der"] : ns.count === 1 ? ["part", "Én navnelik, sjekk at du har riktig"] : ["unknown", "Flere navnelike, familien må skille dem"]]);
    const same = data.elsewhere.filter(e => e.same_family);
    rows.push(["Andre tellinger", "", same.length ? same.map(e => `${e.year}: ${e.name}, ${e.place}`).join("; ") : "Ikke funnet med samme familie",
      same.length ? ["ok", `Samme familie i ${same.map(e => e.year).join(" og ")}`] : ["unknown", "Ingen bekreftelse fra andre år"]]);

    const sec1 = section(body, "Det treet vet, og det kilden sier");
    const t = el("table", "evidence");
    t.innerHTML = "<thead><tr><th></th><th>Treet ditt</th><th>Kilden</th><th>Vurdering</th></tr></thead>";
    const tb = el("tbody");
    const MARK = { ok: "✓", part: "≈", unknown: "?", no: "✗" };
    rows.forEach(([k, a, b, [st, why]]) => {
      const tr = el("tr"); tr.appendChild(el("th", null, k)); tr.appendChild(el("td", null, a)); tr.appendChild(el("td", null, b));
      const td = el("td", "ev-" + st); td.appendChild(el("span", "ev-mark", MARK[st])); td.append(" " + why); tr.appendChild(td); tb.appendChild(tr);
    });
    t.appendChild(tb); sec1.appendChild(t);

    // 2. what only the family knows
    const qs = [];
    if (inv.kind === "lead") {
      qs.push(["fname", `Het faren til ${first(p)} ${firstOf(c.rec)}?`]);
      c.grand.forEach(([r, x]) => qs.push([r, `Het ${gen_s(first(p))} ${r} ${firstOf(x)}?`]));
    } else if (inv.kind === "family") {
      qs.push(["names", `Het foreldrene til ${first(p)} ${c.people.map(([, x]) => firstOf(x)).join(" og ")}?`]);
    } else qs.push(["name", `Het ${c.rel === "far" ? "faren" : "moren"} til ${first(p)} ${firstOf(c.rec)}?`]);
    if (c.place) qs.push(["place", `Har familien røtter i ${c.place}${c.farm ? ` eller på ${c.farm}` : ""}?`]);
    const sec2 = section(body, "Det bare du eller familien vet");
    sec2.appendChild(el("p", "muted", "Svar bare på det du vet. Spør gjerne eldre slektninger. Hvert ja styrker sporet, et nei stopper det."));
    qs.forEach(([id, q]) => {
      const row = el("div", "inv-q"); row.appendChild(el("p", null, q));
      const acts = el("div", "seg");
      [["yes", "Ja"], ["no", "Nei"], ["unknown", "Vet ikke"]].forEach(([v, label]) => {
        const b = btn(label, "seg-btn" + (store.answers[id] === v ? " on" : ""), () => { store.answers[id] = v; save(); acts.querySelectorAll("button").forEach(x => x.classList.toggle("on", x === b)); update(); });
        b.setAttribute("aria-pressed", String(store.answers[id] === v)); acts.appendChild(b);
      });
      row.appendChild(acts); sec2.appendChild(row);
    });

    // 3. the source itself
    const sec3 = section(body, "Les kilden selv");
    sec3.appendChild(el("p", "muted", `Folketellingen ${c.year}, ${[c.farm, c.place].filter(Boolean).join(", ")}. Se om navn, alder og fødested er lest riktig, og hvem andre som bor der.`));
    if (data.household.length) {
      const ht = el("table"); ht.innerHTML = "<thead><tr><th>Navn</th><th>Født</th><th>Oppført som</th><th>Fødested</th></tr></thead>";
      const hb = el("tbody");
      data.household.forEach(h => { const tr = el("tr", c.people.some(([, x]) => x.record_id === h.record_id) ? "me" : null);
        [h.name, h.birth_year ?? "?", roleText(h.role), h.birthplace || ""].forEach(v => tr.appendChild(el("td", null, v))); hb.appendChild(tr); });
      ht.appendChild(hb); sec3.appendChild(ht);
    }
    const srcRow = el("div", "sp-actions");
    if (c.link) { const a = el("a", "sp-btn", "Åpne kilden ↗"); a.href = c.link; a.target = "_blank"; a.rel = "noopener"; srcRow.appendChild(a); }
    sec3.appendChild(srcRow);
    const chk = el("label", "inv-check"); const box = el("input"); box.type = "checkbox"; box.checked = store.sourceChecked;
    box.addEventListener("change", () => { store.sourceChecked = box.checked; save(); update(); });
    chk.append(box, " Jeg har lest oppføringen i kilden selv, og den stemmer"); sec3.appendChild(chk);

    // 4. decision
    const dec = el("div", "inv-decide"); body.appendChild(dec);
    // research log
    if ((p.research || []).length) {
      const sec5 = section(body, `Notater om ${first(p)}`);
      const ul = el("ul", "inv-log"); p.research.slice(-8).reverse().forEach(r => ul.appendChild(el("li", null, `${r.date}: ${r.text}`))); sec5.appendChild(ul);
    }

    function level() {
      const a = Object.values(store.answers);
      if (a.includes("no")) return ["conflict", 0];
      let pts = 0;
      rows.forEach(([, , , [st]]) => { pts += st === "ok" ? 1 : st === "part" ? 0.5 : 0; });
      if (same.length) pts += 1;   // the census row already gave 1
      const yes = a.filter(v => v === "yes").length;
      pts += 2 * yes + (store.sourceChecked ? 1 : 0);
      const independent = yes > 0 || same.length > 0;
      if (independent && store.sourceChecked && pts >= 7) return ["confirmed", pts];
      if (independent && pts >= 4.5) return ["probable", pts];
      return ["unverified", pts];
    }
    function missing(lv) {
      const out = [];
      if (lv === "conflict") return ["Du har svart nei på noe. Da er dette trolig ikke riktig familie."];
      if (!same.length && !Object.values(store.answers).includes("yes")) out.push("Noe uavhengig som bekrefter sporet: et ja på et spørsmål over, eller samme familie i en annen folketelling.");
      if (!store.sourceChecked) out.push("Les oppføringen i kilden selv.");
      return out;
    }
    function update() {
      const [lv] = level();
      const word = { confirmed: "Bekreftet", probable: "Sannsynlig", unverified: "Ubekreftet", conflict: "Motstridende kilder" }[lv];
      const step = { conflict: 0, unverified: 1, probable: 2, confirmed: 3 }[lv];
      meter.innerHTML = "";
      meter.appendChild(badge(lv));
      const bar = el("div", "inv-bar"); for (let i = 1; i <= 3; i++) bar.appendChild(el("span", i <= step ? "on" : null)); meter.appendChild(bar);
      meter.appendChild(el("p", "muted", lv === "confirmed" ? "Sterke bevis fra flere kanter. Trygt å legge til."
        : lv === "probable" ? (store.sourceChecked ? "Godt nok til å legge til. Ett ja til, eller samme familie i en annen telling, gjør det bekreftet." : "Godt nok til å legge til. Les kilden selv for å bekrefte.")
        : lv === "conflict" ? "Noe stemmer ikke." : "Ikke nok ennå til å legge til i treet."));
      dec.innerHTML = "";
      dec.appendChild(el("h2", null, "Din beslutning"));
      const acts = el("div", "sp-actions");
      const ready = lv === "confirmed" || lv === "probable";
      if (ready) {
        if (inv.kind === "lead" && c.grand.length) {
          acts.appendChild(btn("Legg til far og besteforeldre", "sp-btn sp-btn-primary", () => commit(lv, { grand: true })));
          acts.appendChild(btn("Bare faren", "sp-btn", () => commit(lv, {})));
        } else acts.appendChild(btn("Legg til i treet", "sp-btn sp-btn-primary", () => commit(lv, {})));
      } else {
        const ul = el("ul", "inv-missing"); missing(lv).forEach(m => ul.appendChild(el("li", null, m)));
        dec.appendChild(el("p", null, lv === "conflict" ? "Dette sporet stopper her." : "Før du legger til trenger vi:")); dec.appendChild(ul);
        if (lv !== "conflict") acts.appendChild(btn("Legg til likevel, merket som usikker", "sp-btn sp-btn-quiet", () => commit(lv, { uncertain: true })));
      }
      acts.appendChild(btn("Ikke denne", "sp-btn " + (lv === "conflict" ? "sp-btn-primary" : "sp-btn-quiet"), () => {
        log(p, `Avviste ${who} (${c.year}, ${c.place})${lv === "conflict" ? ": svarte nei på et spørsmål" : ""}.`);
        reject(n, rid, inv.card); show("relatives-view"); window.scrollTo(0, invReturnY);
      }));
      dec.appendChild(acts);
    }
    function commit(lv, opt) {
      if (inv.kind === "lead") addLead(n, inv.item, inv.card, !!opt.grand);
      else if (inv.kind === "family") addFamily(n, inv.item, inv.card);
      else addParent(n, inv.item, inv.card);
      const conf = lv === "confirmed" ? "high" : lv === "probable" ? "medium" : "low";
      const slots = inv.kind === "lead" ? [2 * n, ...(opt.grand ? [4 * n, 4 * n + 1] : [])]
        : inv.kind === "family" ? [2 * n, 2 * n + 1] : [inv.item.relation === "father" ? 2 * n : 2 * n + 1];
      slots.forEach(sl => { const x = person(sl); if (!x) return; Object.values(x.kept || {}).forEach(k => { k.confidence = conf; });
        if (opt.uncertain) x.uncertain = true; else delete x.uncertain; });
      const yes = Object.entries(store.answers).filter(([, v]) => v === "yes").length;
      log(p, `La til ${who} som ${c.rel} (${c.year}, ${c.place}). ${{ confirmed: "Bekreftet", probable: "Sannsynlig", unverified: "Usikker" }[lv] || "Usikker"}: ` +
        [same.length && `samme familie i ${same.map(e => e.year).join(", ")}`, yes && `${yes} ja fra deg`, store.sourceChecked && "kilden lest"].filter(Boolean).join(", ") + ".");
      save(); renderTree();
      show("relatives-view"); window.scrollTo(0, invReturnY);
    }
    update();
  }

  function section(parent, title) { const s = el("section", "inv-sec"); s.appendChild(el("h2", null, title)); parent.appendChild(s); return s; }
  function log(p, text) { (p.research = p.research || []).push({ date: new Date().toISOString().slice(0, 10), text }); save(); }

  function elsewhereCard(n) {
    const p = person(n), by = Number(p.birth_year) || null, dk = danishPlace(n), items = [];
    if (dk) items.push(["Danske kilder", `${dk} ligger i Danmark, så ${p.birthplace === dk ? first(p) : "familien"} står trolig i danske kirkebøker og folketellinger. De er gratis å søke i hos Danish Family Search. Treff i norske kilder er derfor mindre sannsynlige.`,
      "https://www.danishfamilysearch.dk/", "danishfamilysearch.dk"]);
    if (!dk && by && by <= 1960) items.push(["Folketellingen 1920",
      (by <= 1920 ? `${first(p)} står trolig selv i folketellingen 1920, sammen med foreldrene.` : `Foreldrene til ${first(p)} var trolig ${by - 1920 > 25 ? "barn" : "unge"} i 1920 og står i folketellingen det året.`) +
      " Den dekker hele landet og er søkbar hos Digitalarkivet, men er ikke i Spor ennå.", "https://www.digitalarkivet.no/census/search/1920", "digitalarkivet.no"]);
    const se = swedishPlace(n);
    if (se) items.push(["Svenske folketellinger", `${se} ligger i Sverige. Riksarkivet har gratis søk i de svenske folketellingene 1880, 1890, 1900, 1910 og 1930, med foreldre og søsken i samme hus. ` +
      "Svensker som flyttet til Norge ble ofte aldri meldt ut, og står fortsatt hjemme med merknaden «I Norge» eller i boka over fraværende. " +
      "Digitalarkivet har også registeret «Innflyttede svensker til Østfold 1812–1920» og statsborgerskapsbevillinger.",
      "https://sok.riksarkivet.se/folkrakningar", "riksarkivet.se"]);
    if (!dk && p.given_name && (!by || by >= 1815)) {
      const q = new URLSearchParams({ firstname: first(p), lastname: (p.surname || "").split(" ").pop() });
      if (by) { q.set("birth_year_from", by - 2); q.set("birth_year_to", by + 2); }
      items.push(["Kirkebøker og dødsregister", `Dåpen gir begge foreldrene, vielsen fedrene, og registeret over døde 1951–2017 gir fødsels- og dødsdato. ` +
        `Søket hos Digitalarkivet er fylt ut for ${fullName(p)}. Prøv også andre stavemåter, og fødestedet hvis ${first(p)} kom fra et annet prestegjeld.`,
        `https://www.digitalarkivet.no/search/persons/advanced?${q}`, "digitalarkivet.no"]);
    }
    if (!dk && p.given_name && p.surname && (!by || (by >= 1840 && by <= 1990))) items.push(["Gamle aviser",
      `Dødsannonser lister barn og svigerbarn, og lysninger nevner brudeparet med bosted og yrke. Søk etter «${fullName(p)}» i avisene hos Nasjonalbiblioteket. ` +
      "Nyere aviser kan bare leses fra Norge.",
      `https://www.nb.no/search?${new URLSearchParams({ q: `"${fullName(p)}"`, mediatype: "aviser" })}`, "nb.no"]);
    if (!dk && (!by || by > CUTOFF || p.birth_year_estimated)) items.push(["Gravminner",
      `Gravsteiner viser fødsels- og dødsår. Søk etter ${fullName(p)} i gravminnebasen til Slekt og Data.`, "https://www.slektogdata.no/gravminner", "slektogdata.no"]);
    items.push(["Spør i familien", `Eldre slektninger, dødsannonser, gamle brev og konfirmasjonsbilder gir ofte fødselsår, fødested og pikenavn. Det er nøkkelen til neste spor.`]);
    const c = el("article", "sp-card rel-card");
    c.appendChild(el("span", "sp-eyebrow sp-muted", "Andre steder å lete"));
    c.appendChild(el("h3", "sp-find-title", `Sporet etter ${gen_s(first(p))} familie går videre her`));
    const ul = el("ul", "elsewhere");
    for (const [t, text, href, host] of items) {
      const li = el("li"); li.appendChild(el("b", null, t)); li.appendChild(el("span", "sp-muted", text));
      if (href) { const a = el("a", null, `Gå til ${host} ↗`); a.href = href; a.target = "_blank"; a.rel = "noopener"; li.appendChild(a); }
      ul.appendChild(li);
    }
    c.appendChild(ul);
    return c;
  }

  function addFamily(n, fam, card) {
    for (const [slot, par] of [[2 * n, fam.father], [2 * n + 1, fam.mother]]) {
      if (!par || person(slot)) continue;
      const np = cleanPerson({ given_name: par.given_name, surname: par.surname, birth_year: String(par.birth_year || ""), birthplace: par.birthplace || "" });
      np.kept = { [par.record_id]: { status: "confirmed", confidence: "medium", year: fam.year, name: par.name,
        place: [fam.farm, fam.place].filter(Boolean).join(", "), source: fam.source.replace(/ · \S+$/, ` · ${par.record_id}`),
        reasons: [`Mulig familie til ${fullName(person(n))}`] } };
      tree[String(slot)] = np;
    }
    save();
    card.classList.add("done");
    const b = card.querySelector(".sp-actions .sp-btn"); b.textContent = "Lagt til i treet"; b.disabled = true;
    card.parentElement.querySelectorAll(".rel-card").forEach(c => { if (c !== card) c.classList.add("aside"); });
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
      box.appendChild(el("p", "sp-muted", `Vi kan bare lete etter personer født i ${CUTOFF} eller tidligere, i folketellingene for ${COUNTIES}. ` +
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
    const add = btn("Undersøk nærmere", featured ? "sp-btn sp-btn-primary" : "sp-btn", () => investigate({ n, kind: "relative", item: sg, card }));
    acts.appendChild(add);
    if (ev.link) { const a = el("a", "sp-btn", "Se kilden"); a.href = ev.link; a.target = "_blank"; a.rel = "noopener"; acts.appendChild(a); }
    acts.appendChild(btn("Ikke denne", "sp-btn sp-btn-quiet", () => reject(n, sg.record_id, card)));
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
