const $ = (id) => document.getElementById(id);
const el = (tag, text, cls) => {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (cls) n.className = cls;
  return n;
};
let config,
  configId = null,
  catalog = [],
  roles = [],
  sections = [],
  selectedRun = null,
  runData = null,
  cursor = 0,
  follow = true,
  playback = null,
  poll = null;
let editingRef = null,
  editingPlayer = null,
  editorMode = "guided";

async function api(path, body) {
  const response = await fetch(
    "/api/" + path,
    body === undefined
      ? {}
      : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
  );
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || data.detail || `Request failed (${response.status})`);
  return data;
}
function notice(message, error = false) {
  $("notice").hidden = false;
  $("notice").textContent = message;
  $("notice").className = error ? "error" : "";
}
function task(fn) {
  return async (event) => {
    try {
      await fn(event);
    } catch (error) {
      notice(error.message, true);
    }
  };
}
function tab(name) {
  document.querySelectorAll(".page").forEach((n) => (n.hidden = n.id !== name));
  document
    .querySelectorAll("[data-tab]")
    .forEach((n) => n.classList.toggle("active", n.dataset.tab === name));
}
function option(value, text) {
  const n = el("option", text);
  n.value = value;
  return n;
}
function field(parent, title, value, onChange, type = "text") {
  const label = el("label", title),
    input = el("input");
  input.type = type;
  input.value = value ?? "";
  input.addEventListener("change", () =>
    onChange(type === "number" ? (input.value === "" ? null : Number(input.value)) : input.value),
  );
  label.append(input);
  parent.append(label);
  return input;
}
function choice(parent, title, value, items, onChange) {
  const label = el("label", title),
    select = el("select");
  for (const [v, t] of items) select.append(option(v, t));
  select.value = value;
  select.addEventListener(
    "change",
    task(() => onChange(select.value)),
  );
  label.append(select);
  parent.append(label);
  return select;
}
function btn(text, action, cls) {
  const n = el("button", text, cls);
  n.type = "button";
  n.addEventListener("click", task(action));
  return n;
}
function download(filename, value, type = "application/json") {
  const blob = new Blob([typeof value === "string" ? value : JSON.stringify(value, null, 2)], { type });
  const url = URL.createObjectURL(blob),
    a = el("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
const providerOptions = [
  ["mock", "Demo / offline"],
  ["openai", "OpenAI"],
  ["anthropic", "Anthropic"],
  ["einfra", "e-INFRA"],
  ["compatible", "OpenAI-compatible"],
];
const modelPlaceholders = {
  mock: "demo",
  openai: "gpt-4.1-mini",
  anthropic: "claude-sonnet-4-5",
  einfra: "mini",
  compatible: "your-model",
};
function modelEditor(parent, model, inherited = {}) {
  const effective = () => ({
    ...inherited,
    ...model,
    generation: Object.fromEntries(
      Object.entries({ ...inherited.generation, ...model.generation }).filter(([, v]) => v !== null),
    ),
  });
  choice(parent, "Provider", effective().provider, providerOptions, (value) => {
    model.provider = value;
    model.model = modelPlaceholders[value];
    model.generation = Object.fromEntries(Object.keys(inherited.generation || {}).map((k) => [k, null]));
    delete model.base_url;
    parent.replaceChildren();
    modelEditor(parent, model, inherited);
  });
  const modelInput = field(parent, "Model", effective().model, (v) => (model.model = v));
  modelInput.required = true;
  const advanced = el("details"),
    summary = el("summary", "Endpoint, generation & memory");
  advanced.append(summary);
  parent.append(advanced);
  field(advanced, "Endpoint base URL (optional)", effective().base_url, (v) => (model.base_url = v || null));
  field(
    advanced,
    "Credential environment variable",
    effective().credential_env,
    (v) => (model.credential_env = v || null),
  );
  const two = el("div", undefined, "two");
  advanced.append(two);
  for (const [key, label, fallback] of [
    ["max_output_tokens", "Output token limit", 512],
    ["context_tokens", "Context token limit", 16000],
    ["timeout_seconds", "Timeout (seconds)", 60],
    ["retries", "Network retries", 2],
  ])
    field(two, label, effective()[key] ?? fallback, (v) => (model[key] = v), "number");
  choice(
    advanced,
    "Memory policy",
    effective().memory || "recent",
    [
      ["recent", "Recent conversation + private information"],
      ["full", "Full history (stop at context limit)"],
      ["notes", "Private notes + recent conversation"],
    ],
    (v) => (model.memory = v),
  );
  const gen = el("details");
  gen.append(el("summary", "Generation parameters"));
  advanced.append(gen);
  const generation = () => model.generation || (model.generation = {});
  const unset = (k) => {
    if (Object.hasOwn(inherited.generation || {}, k)) generation()[k] = null;
    else delete generation()[k];
  };
  for (const [key, label] of [
    ["temperature", "Temperature"],
    ["top_p", "Top P"],
    ["top_k", "Top K (Anthropic)"],
    ["seed", "Generation seed"],
    ["frequency_penalty", "Frequency penalty"],
    ["presence_penalty", "Presence penalty"],
  ])
    field(
      gen,
      label,
      effective().generation[key],
      (v) => {
        if (v === null) unset(key);
        else generation()[key] = v;
      },
      "number",
    );
  field(gen, "Stop sequences (separate with |)", effective().generation.stop?.join("|") || "", (v) => {
    if (v) generation().stop = v.split("|");
    else unset("stop");
  });
  choice(
    gen,
    "Reasoning effort (supported OpenAI models)",
    effective().generation.reasoning_effort || "",
    [
      ["", "Provider default"],
      ["low", "Low"],
      ["medium", "Medium"],
      ["high", "High"],
    ],
    (v) => {
      if (v) generation().reasoning_effort = v;
      else unset("reasoning_effort");
    },
  );
  field(
    advanced,
    "Input price / million tokens (optional)",
    effective().input_cost_per_million,
    (v) => (model.input_cost_per_million = v),
    "number",
  );
  field(
    advanced,
    "Output price / million tokens (optional)",
    effective().output_cost_per_million,
    (v) => (model.output_cost_per_million = v),
    "number",
  );
  advanced.append(
    btn("List endpoint models", async () => {
      const names = await api("models", effective());
      const list = el("datalist");
      list.id = "models-" + crypto.randomUUID();
      names.forEach((n) => list.append(option(n, n)));
      parent.append(list);
      modelInput.setAttribute("list", list.id);
      notice(`${names.length} models loaded. Choose in the Model field.`);
    }),
  );
}
function renderPlayers() {
  $("players").replaceChildren();
  $("player-total").textContent = `(${config.players.length})`;
  config.players.forEach((p, index) => {
    const card = el("article", undefined, "player"),
      top = el("div", undefined, "player-top");
    top.append(el("span", String(index + 1).padStart(2, "0"), "seat-number"));
    const name = el("input");
    name.value = p.name;
    name.setAttribute("aria-label", `Seat ${index + 1} name`);
    name.onchange = () => (p.name = name.value);
    top.append(name);
    for (const [label, delta] of [
      ["↑", -1],
      ["↓", 1],
    ]) {
      const b = btn(
        label,
        () => {
          const other = index + delta;
          if (other >= 0 && other < config.players.length) {
            [config.players[index], config.players[other]] = [config.players[other], config.players[index]];
            if (config.roles)
              [config.roles[index], config.roles[other]] = [config.roles[other], config.roles[index]];
            renderPlayers();
          }
        },
        "move",
      );
      b.setAttribute("aria-label", `Move seat ${index + 1} ${delta < 0 ? "up" : "down"}`);
      top.append(b);
    }
    card.append(top);
    const body = el("div", undefined, "player-body");
    modelEditor(body, p.model, config.defaults);
    const row = el("div", undefined, "persona-row");
    choice(
      row,
      "Persona",
      p.persona,
      catalog.map((item) => [item.ref, item.name + (item.builtin ? " · template" : "")]),
      async (v) => {
        const source = await api("persona?ref=" + encodeURIComponent(v));
        const copied = await api("personas", {
          text: source.text,
          ref: "players/" + crypto.randomUUID() + ".md",
        });
        p.persona = copied.ref;
        await refreshCatalog();
        renderPlayers();
      },
    );
    row.append(btn("Edit", () => openPersona(p.persona, p.id)));
    body.append(row);
    if (config.roles)
      choice(
        body,
        "Character",
        config.roles[index] || "",
        [["", "Choose character"], ...roles.map((r) => [r.id, r.name + " · " + r.team])],
        (v) => (config.roles[index] = v),
      );
    card.append(body);
    $("players").append(card);
  });
}
const bindings = {
  "config-name": ["name"],
  seed: ["seed"],
  rounds: ["conversations", "rounds"],
  "max-days": ["limits", "max_days"],
  "max-turns": ["limits", "max_turns"],
  "max-tokens": ["limits", "max_tokens"],
  runtime: ["limits", "runtime_seconds"],
  "action-retries": ["limits", "action_retries"],
  "max-message": ["conversations", "max_message_chars"],
  whispers: ["conversations", "whispers"],
  misinformation: ["policy", "misinformation"],
  registration: ["policy", "registration"],
  "mayor-bounce": ["policy", "mayor_bounce"],
  "imp-successor": ["policy", "imp_successor"],
  "shuffle-roles": ["shuffle_roles"],
};
function renderConfig() {
  for (const [id, path] of Object.entries(bindings)) {
    const n = $(id),
      value = path.reduce((o, k) => o[k], config);
    if (n.type === "checkbox") n.checked = value;
    else n.value = value;
  }
  $("player-count").value = config.players.length;
  $("manual-roles").checked = !!config.roles;
  $("defaults-editor").replaceChildren();
  modelEditor($("defaults-editor"), config.defaults);
  renderPlayers();
}
async function refreshConfigs() {
  const selected = $("saved-config").value;
  $("saved-config").replaceChildren(option("", "Choose configuration…"));
  (await api("configs")).forEach((c) => $("saved-config").append(option(c.id, c.name)));
  $("saved-config").value = configId || selected;
}
async function saveConfig(duplicate = false) {
  const saved = await api("configs", { id: duplicate ? null : configId, config, duplicate });
  config = saved.config;
  configId = saved.id;
  await refreshCatalog();
  renderConfig();
  await refreshConfigs();
  notice(
    duplicate
      ? "Configuration duplicated with independent personas."
      : "Configuration saved. Every player has an independent persona file.",
  );
  return saved;
}
async function refreshCatalog() {
  catalog = await api("personas");
  renderLibrary();
}
function renderLibrary() {
  $("persona-library").replaceChildren();
  catalog
    .filter((p) => p.builtin || !p.ref.startsWith("players/"))
    .forEach((p) => {
      const card = el("article", undefined, "panel");
      card.append(el("small", p.builtin ? "BUILT-IN TEMPLATE" : "CUSTOM PERSONA"), el("h3", p.name));
      card.append(btn(p.builtin ? "Preview & customize" : "Edit persona", () => openPersona(p.ref)));
      $("persona-library").append(card);
    });
}
function getSection(text, section) {
  const escaped = section.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return (
    text
      .match(new RegExp("^## " + escaped + "\\s*\\n([\\s\\S]*?)(?=^## |$(?![\\s\\S]))", "m"))?.[1]
      ?.trim() || ""
  );
}
function setSection(text, section, value) {
  const start = text.indexOf("## " + section + "\n");
  if (start < 0) return text + "\n\n## " + section + "\n" + value + "\n";
  const next = text.indexOf("\n## ", start + 4);
  return text.slice(0, start) + "## " + section + "\n" + value + "\n" + (next < 0 ? "" : text.slice(next));
}
function renderGuided() {
  const text = $("persona-markdown").value;
  $("guided-editor").replaceChildren();
  field($("guided-editor"), "Persona name", text.match(/^# (.+)$/m)?.[1] || "", (v) => {
    $("persona-markdown").value = $("persona-markdown").value.replace(/^# .*$/m, "# " + v);
  });
  sections.forEach((s) => {
    const label = el("label", s),
      area = el("textarea");
    area.rows = 4;
    area.value = getSection(text, s);
    area.oninput = () => {
      $("persona-markdown").value = setSection($("persona-markdown").value, s, area.value);
    };
    label.append(area);
    $("guided-editor").append(label);
  });
}
function renderPreview() {
  const article = $("persona-preview");
  article.replaceChildren();
  let paragraph = [];
  const flush = () => {
    if (paragraph.length) {
      article.append(el("p", paragraph.join("\n")));
      paragraph = [];
    }
  };
  for (const line of $("persona-markdown").value.split("\n")) {
    if (line.startsWith("# ")) {
      flush();
      article.append(el("h1", line.slice(2)));
    } else if (line.startsWith("## ")) {
      flush();
      article.append(el("h2", line.slice(3)));
    } else if (!line.trim()) flush();
    else paragraph.push(line);
  }
  flush();
}
function editorTab(mode) {
  editorMode = mode;
  $("guided-editor").hidden = mode !== "guided";
  $("markdown-editor").hidden = mode !== "markdown";
  $("persona-preview").hidden = mode !== "preview";
  if (mode === "guided") renderGuided();
  if (mode === "preview") renderPreview();
}
async function openPersona(ref, player = null) {
  editingRef = ref;
  editingPlayer = player;
  const data = await api("persona?ref=" + encodeURIComponent(ref));
  $("persona-markdown").value = data.text;
  $("persona-title").textContent = player ? "Edit this player’s persona" : "Persona workshop";
  editorTab("guided");
  $("persona-dialog").showModal();
}
async function savePersona(copy = false) {
  const shared = editingPlayer && config.players.filter((p) => p.persona === editingRef).length > 1;
  const newCopy = copy || !editingRef || editingRef.startsWith("builtin:") || shared;
  const ref = newCopy ? (editingPlayer ? "players/" + crypto.randomUUID() + ".md" : null) : editingRef;
  const saved = await api("personas", { text: $("persona-markdown").value, ref });
  if (editingPlayer) config.players.find((p) => p.id === editingPlayer).persona = saved.ref;
  editingRef = saved.ref;
  await refreshCatalog();
  renderPlayers();
  $("persona-dialog").close();
  notice("Persona saved as Markdown.");
}
async function refreshRuns() {
  const runs = await api("runs");
  $("run-list").replaceChildren();
  if (!runs.length)
    $("run-list").append(el("p", "No runs yet. Assemble a town and start your first game.", "muted"));
  runs.forEach((r) => {
    const card = el("article", undefined, "panel");
    card.append(
      el("small", `${r.status} · ${new Date(r.created).toLocaleString()}`),
      el("h3", r.name),
      el("p", r.result?.reason || "Game in progress", "muted"),
      btn("Open replay", () => openRun(r.id)),
    );
    $("run-list").append(card);
  });
}
async function openRun(id) {
  selectedRun = id;
  follow = true;
  cursor = 0;
  $("event-filter").value = "all";
  tab("viewer");
  $("perspective").value = "public";
  await updateRun(true);
  if (poll) clearInterval(poll);
  poll = setInterval(() => updateRun().catch((e) => notice(e.message, true)), 700);
}
async function updateRun(initial = false) {
  if (!selectedRun) return;
  const id = selectedRun,
    view = $("perspective").value;
  const data = await api(`runs/${id}?view=${encodeURIComponent(view)}`);
  if (id !== selectedRun || view !== $("perspective").value) return;
  runData = data;
  if (initial) {
    $("perspective").replaceChildren(option("public", "Public"), option("omniscient", "Omniscient"));
    data.players.forEach((p) => $("perspective").append(option(p.id, p.name)));
  }
  if (follow) cursor = data.events.length;
  else cursor = Math.min(cursor, data.events.length);
  renderRun();
  if (data.status !== "running" && poll) {
    clearInterval(poll);
    poll = null;
  }
}
function eventText(event) {
  const d = event.data,
    name = (id) => runData.players.find((p) => p.id === id)?.name || id;
  switch (event.kind) {
    case "setup":
      return `${d.players.length} players take their seats.`;
    case "phase":
      return `${d.phase === "night" ? "Night" : "Day"} ${d.day}`;
    case "message":
      return `${name(d.player)}${d.target ? " → " + name(d.target) : ""}: ${d.text}`;
    case "nomination":
      return `${name(d.nominator)} nominates ${name(d.nominee)}.`;
    case "vote":
      return (
        `${d.tally} votes for ${name(d.nominee)} (needs ${d.threshold}). ${d.block ? name(d.block) + " is on the block." : "No player on the block."}\n` +
        Object.entries(d.votes)
          .map(([p, v]) => `${name(p)}: ${v ? "yes" : "no"}`)
          .join(" · ")
      );
    case "dawn":
      return d.deaths.length
        ? `Dawn: ${d.deaths.map(name).join(", ")} died in the night.`
        : "Dawn: nobody died.";
    case "death":
      return `${name(d.player)} died (${d.cause}).`;
    case "execution":
      return `${name(d.player)} is executed.`;
    case "role":
      return `${name(d.player)}: ${d.role.replaceAll("_", " ")} · ${d.alignment}`;
    case "slayer":
      return `${name(d.player)} claims a Slayer shot at ${name(d.target)}.`;
    case "no_execution":
      return "The day ends without an execution.";
    case "result":
      return `${d.winner ? d.winner.toUpperCase() + " wins." : "Interrupted."} ${d.reason}`;
    default:
      return JSON.stringify(d, null, 2);
  }
}
function renderRun() {
  const d = runData;
  if (!d) return;
  const events = d.events.slice(0, cursor),
    last = events.at(-1),
    result = events.findLast((e) => e.kind === "result");
  $("run-title").textContent = d.name;
  $("run-status").textContent = `${d.status.toUpperCase()} · ${d.id.slice(0, 8)}`;
  $("stop-run").hidden = d.status !== "running";
  $("result-banner").hidden = !result;
  $("result-banner").textContent = result ? eventText(result) : "";
  $("scrubber").max = d.events.length;
  $("scrubber").value = cursor;
  $("position").textContent = `${cursor} / ${d.events.length} events`;
  $("phase-label").textContent = last ? `${last.phase} ${last.day}` : "Before setup";
  const state = Object.fromEntries(
    d.players.map((p) => [p.id, { ...p, alive: true, dead_vote: true, role: null }]),
  );
  for (const e of events) {
    const v = e.data;
    if (e.kind === "death" && state[v.player]) state[v.player].alive = false;
    if (e.kind === "dawn")
      v.deaths.forEach((id) => {
        if (state[id]) state[id].alive = false;
      });
    if ((e.kind === "role" || e.kind === "transformation") && state[v.player]) state[v.player].role = v.role;
    if (e.kind === "grimoire") v.players.forEach((p) => Object.assign(state[p.id], p));
    if (e.kind === "vote")
      Object.entries(v.votes).forEach(([id, yes]) => {
        if (yes && !state[id].alive) state[id].dead_vote = false;
      });
  }
  $("seating").classList.toggle("dense", d.players.length > 10);
  $("seating").replaceChildren();
  const center = el("div", ` ${last?.phase === "night" ? "Night" : "Day"} ${last?.day || 0}`, "table-center");
  center.append(el("small", `${Object.values(state).filter((p) => p.alive).length} alive`));
  $("seating").append(center);
  Object.values(state).forEach((p, i) => {
    const angle = (2 * Math.PI * i) / d.players.length - Math.PI / 2,
      seat = el("div", undefined, "seat" + (p.alive ? "" : " dead"));
    seat.style.left = `${50 + 38 * Math.cos(angle)}%`;
    seat.style.top = `${50 + 39 * Math.sin(angle)}%`;
    seat.append(
      el("div", p.alive ? String(i + 1) : "†", "avatar"),
      el("strong", p.name),
      el("small", `${p.provider} · ${p.model}`),
    );
    if (p.role) seat.append(el("small", p.role.replaceAll("_", " "), "role"));
    if (!p.alive) seat.append(el("small", p.dead_vote ? "Dead vote available" : "Dead vote spent"));
    $("seating").append(seat);
  });
  const filter = $("event-filter").value;
  $("timeline").replaceChildren();
  events
    .filter((e) => filter === "all" || e.kind === filter || (filter === "death" && e.kind === "dawn"))
    .forEach((e) => {
      const article = el("article", undefined, "event " + e.kind);
      article.append(
        el("div", `${e.seq} · ${e.phase} ${e.day} · ${e.kind.replaceAll("_", " ")}`, "meta"),
        el(["grimoire", "action", "information", "usage"].includes(e.kind) ? "pre" : "p", eventText(e)),
      );
      $("timeline").append(article);
    });
  if (follow || playback) $("timeline").scrollTop = $("timeline").scrollHeight;
  $("usage").hidden = !d.usage;
  if (d.usage) {
    $("usage").replaceChildren(el("h2", "Usage"));
    for (const [id, u] of Object.entries(d.usage))
      $("usage").append(
        el(
          "p",
          `${state[id].name}: ${u.input_tokens + u.output_tokens} tokens${u.estimated ? " (estimated)" : ""} · ${u.requests} requests · ${u.cost === null ? "cost unavailable" : "$" + u.cost.toFixed(4)}`,
        ),
      );
  }
}
function stopPlayback() {
  if (playback) clearInterval(playback);
  playback = null;
  $("play").textContent = "Play";
}
function startPlayback() {
  follow = false;
  if (cursor >= runData.events.length) cursor = 0;
  $("play").textContent = "Pause";
  playback = setInterval(
    () => {
      cursor++;
      renderRun();
      if (cursor >= runData.events.length) stopPlayback();
    },
    Number($("speed").value),
  );
}

for (const [id, path] of Object.entries(bindings))
  $(id).addEventListener("change", () => {
    const n = $(id),
      parent = path.slice(0, -1).reduce((o, k) => o[k], config);
    parent[path.at(-1)] = n.type === "checkbox" ? n.checked : n.type === "number" ? Number(n.value) : n.value;
  });
$("defaults-editor").addEventListener("change", renderPlayers);
$("player-count").onchange = () => {
  const count = Math.max(5, Math.min(15, Number($("player-count").value) || 7));
  while (config.players.length < count) {
    let i = 1;
    while (config.players.some((p) => p.id === "p" + i)) i++;
    config.players.push({ id: "p" + i, name: "Player " + i, persona: "builtin:analyst", model: {} });
  }
  config.players.length = count;
  if (config.roles) config.roles.length = count;
  renderPlayers();
};
$("manual-roles").onchange = () => {
  config.roles = $("manual-roles").checked ? config.players.map(() => "") : null;
  renderPlayers();
};
$("save-config").onclick = task(() => saveConfig());
$("duplicate-config").onclick = task(() => {
  config.name += " (copy)";
  return saveConfig(true);
});
$("load-config").onclick = task(async () => {
  const id = $("saved-config").value;
  if (!id) throw new Error("Choose a saved configuration first.");
  config = await api("configs/" + id);
  configId = id;
  renderConfig();
  notice("Configuration loaded.");
});
$("export-config").onclick = task(async () => {
  await saveConfig();
  download("clocktower-config.json", config);
});
$("import-config").onchange = task(async (e) => {
  if (!e.target.files[0]) return;
  const value = JSON.parse(await e.target.files[0].text());
  await api("validate", value);
  config = value;
  configId = null;
  renderConfig();
  notice("Configuration imported.");
});
$("validate").onclick = task(async () => {
  await api("validate", config);
  notice("Configuration and persona references are valid.");
});
$("launch").onclick = task(async () => {
  await saveConfig();
  const run = await api("runs", config);
  await openRun(run.id);
});
$("new-persona").onclick = task(() => openPersona("builtin:analyst"));
$("close-persona").onclick = () => $("persona-dialog").close();
$("persona-form").onsubmit = task(async (e) => {
  e.preventDefault();
  await savePersona();
});
$("copy-persona").onclick = task(() => savePersona(true));
$("import-persona").onchange = task(async (e) => {
  if (e.target.files[0]) {
    $("persona-markdown").value = await e.target.files[0].text();
    editingRef = null;
    editorTab(editorMode);
  }
});
$("refresh-runs").onclick = task(refreshRuns);
$("perspective").onchange = task(async () => {
  stopPlayback();
  follow = true;
  await updateRun();
});
$("event-filter").onchange = renderRun;
$("stop-run").onclick = task(async () => {
  await api(`runs/${selectedRun}/stop`, {});
  await updateRun();
});
$("download-run").onclick = () =>
  download(`clocktower-${selectedRun}-${$("perspective").value}.json`, runData);
$("scrubber").oninput = () => {
  stopPlayback();
  follow = false;
  cursor = Number($("scrubber").value);
  renderRun();
};
$("rewind").onclick = () => {
  stopPlayback();
  follow = false;
  cursor = 0;
  renderRun();
};
$("step").onclick = () => {
  stopPlayback();
  follow = false;
  cursor = Math.min(cursor + 1, runData.events.length);
  renderRun();
};
$("live").onclick = () => {
  stopPlayback();
  follow = true;
  cursor = runData.events.length;
  renderRun();
};
$("play").onclick = () => {
  if (playback) stopPlayback();
  else startPlayback();
};
$("speed").onchange = () => {
  if (playback) {
    stopPlayback();
    startPlayback();
  }
};
document.querySelectorAll("[data-tab]").forEach(
  (n) =>
    (n.onclick = task(async () => {
      tab(n.dataset.tab);
      if (n.dataset.tab === "runs") await refreshRuns();
      if (n.dataset.tab === "personas") await refreshCatalog();
    })),
);
document.querySelectorAll("[data-editor]").forEach((n) => (n.onclick = () => editorTab(n.dataset.editor)));
try {
  const data = await api("bootstrap");
  config = data.config;
  catalog = data.personas;
  roles = data.roles;
  sections = data.sections;
  renderConfig();
  renderLibrary();
  await refreshConfigs();
} catch (error) {
  notice(error.message, true);
}
