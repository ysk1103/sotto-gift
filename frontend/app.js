// ===== 定数 =====
const RELATIONS = {mother:"母",father:"父",grandmother:"祖母",grandfather:"祖父",
  partner:"パートナー",friend:"友人",child:"子ども",grandchild:"孫",sibling:"きょうだい",other:"その他"};
const AGE_BANDS = ["10s","20s","30s","40s","50s","60s","70s","80s"];
// 予算スライダーの停止点：2000円〜1万円は1000刻み、1万円超は5000刻み
const BUDGET_STEPS = [2000,3000,4000,5000,6000,7000,8000,9000,10000,15000,20000,25000,30000,35000,40000,45000,50000];
const BUDGET_DEFAULT = 8000;
const GENDERS = {female:"女性", male:"男性", other:"その他"};
// 関係から性別が自明に決まるもの（このとき入力欄は出さない）
const AUTO_GENDER = {mother:"female", grandmother:"female", father:"male", grandfather:"male"};
const ICONS = AVATARS;   // icons.js のSVGアバターキー
const COLORS = ["#e8638c","#5b8def","#36b37e","#9b59b6","#f39c12","#16a5a5"];
const TYPE_LABEL = {buy:"買えるもの",experience:"体験",make:"手作り"};
// 一回きりの予定の選択肢（手打ちは「その他」のみ）
const ONE_TIME_OCCASIONS = ["出産祝い","結婚祝い","新築・引っ越し祝い","就職祝い","入学祝い","卒業祝い","還暦祝い","開店・開業祝い","その他"];

// ===== 状態 =====
let people = [];
let selectedPersonId = null;
let calDate = new Date(); calDate.setDate(1);

// ===== API =====
const api = {
  get: (u) => fetch(u).then(r => r.json()),
  post: (u, b) => fetch(u, {method:"POST",headers:{"Content-Type":"application/json"},
    body: JSON.stringify(b)}).then(r => r.json()),
  del: (u) => fetch(u, {method:"DELETE"}).then(r => r.json()),
};

// ===== テーマ（案B=light / 案D=dark） =====
function applyTheme(t){ document.body.classList.toggle("theme-dark", t === "dark"); }
function currentTheme(){ return localStorage.getItem("theme") || "light"; }
applyTheme(currentTheme());

function openSettings(){
  const t = currentTheme();
  modal(`
    <h2>⚙️ 設定</h2>
    <label>デザイン</label>
    <div class="theme-opts">
      <div class="theme-opt ${t==="light"?"sel":""}" data-theme="light">
        <div class="sw light"></div>
        <div><div class="tn">クリーム（標準）</div><div class="td">明るく上品な生成り色</div></div>
      </div>
      <div class="theme-opt ${t==="dark"?"sel":""}" data-theme="dark">
        <div class="sw dark"></div>
        <div><div class="tn">ダーク</div><div class="td">暗い背景＋ゴールドの特別感</div></div>
      </div>
    </div>
    <div class="modal-actions"><button class="ghost" onclick="closeModal()">閉じる</button></div>`);
  document.querySelectorAll(".theme-opt").forEach(el => el.onclick = () => {
    const theme = el.dataset.theme;
    localStorage.setItem("theme", theme);
    applyTheme(theme);
    document.querySelectorAll(".theme-opt").forEach(x => x.classList.remove("sel"));
    el.classList.add("sel");
  });
}

// ===== 起動 =====
init();
async function init(){
  document.querySelectorAll("[data-icon]").forEach(el => el.innerHTML = icon(el.dataset.icon, 24));
  document.getElementById("open-settings").onclick = openSettings;
  setupBudgetRange();
  fillSelect("s-age", AGE_BANDS);
  document.querySelectorAll(".tabbar button").forEach(b =>
    b.onclick = () => switchView(b.dataset.view));
  document.getElementById("s-go").onclick = runSuggest;
  document.getElementById("s-person").onchange = onSuggestPersonChange;
  document.getElementById("cal-prev").onclick = () => { calDate.setMonth(calDate.getMonth()-1); renderCalendar(); };
  document.getElementById("cal-next").onclick = () => { calDate.setMonth(calDate.getMonth()+1); renderCalendar(); };
  document.getElementById("pd-add-event").onclick = () => openEventForm();
  document.getElementById("pd-add-occasion").onclick = () => openOccasionForm();
  document.getElementById("pd-edit").onclick = () => openPersonForm(currentPerson());
  document.getElementById("pd-del").onclick = deleteCurrentPerson;
  await loadPeople();
  await loadReminders();
}

// ===== 🔔 リマインド =====
async function loadReminders(){
  const box = document.getElementById("reminders");
  const list = await api.get("/api/reminders");
  if (!list.length){ box.innerHTML = ""; return; }
  box.innerHTML = list.map(r => {
    const key = r.person_id ? (people.find(p=>p.id===r.person_id)?.icon || "gift")
                            : (OCCASION_ICON[r.occasion] || "gift");
    return `
    <div class="remind ${r.stage}" ${r.person_id?`data-pid="${r.person_id}"`:""}>
      <div class="ric" style="background:${r.color}22;color:${r.color}">${icon(key,22)}</div>
      <div class="rtext">${esc(r.message)}</div>
      ${r.stage!=="today"?`<div class="rday">あと${r.days}日</div>`:""}
    </div>`;}).join("");
  box.querySelectorAll(".remind[data-pid]").forEach(el => el.onclick = () => {
    selectedPersonId = el.dataset.pid;
    switchView("suggest");
    renderSuggestPersonSelect();
    onSuggestPersonChange();
  });
}

function setupBudgetRange(){
  const lo = document.getElementById("s-bmin-r"), hi = document.getElementById("s-bmax-r");
  const N = BUDGET_STEPS.length - 1;
  [lo, hi].forEach(s => { s.min = 0; s.max = N; s.step = 1; });
  lo.value = Math.max(0, BUDGET_STEPS.indexOf(2000));
  hi.value = Math.max(0, BUDGET_STEPS.indexOf(BUDGET_DEFAULT));
  const fill = document.getElementById("budget-fill"), label = document.getElementById("budget-label");
  const update = (e) => {
    let a = +lo.value, b = +hi.value;
    // 上限は下限を下回らない。下限を上げたら上限も連れて上がる。
    if (e && e.target === lo && a > b){ hi.value = a; b = a; }
    if (e && e.target === hi && b < a){ hi.value = a; b = a; }
    label.textContent = `${BUDGET_STEPS[a].toLocaleString()}円 〜 ${BUDGET_STEPS[b].toLocaleString()}円`;
    fill.style.left = (a / N * 100) + "%";
    fill.style.width = ((b - a) / N * 100) + "%";
  };
  lo.oninput = update; hi.oninput = update;
  update();
}
function budgetMin(){ return BUDGET_STEPS[+document.getElementById("s-bmin-r").value]; }
function budgetMax(){ return BUDGET_STEPS[+document.getElementById("s-bmax-r").value]; }
function setBudgetMax(v){
  let idx = BUDGET_STEPS.findIndex(x => x >= v);
  if (idx < 0) idx = BUDGET_STEPS.length - 1;
  const lo = +document.getElementById("s-bmin-r").value;
  if (idx < lo) idx = lo;
  const hi = document.getElementById("s-bmax-r");
  hi.value = idx; hi.dispatchEvent(new Event("input"));
}

function fillSelect(id, arr, labelFn){
  const el = document.getElementById(id);
  el.innerHTML = arr.map(v => `<option value="${v}">${labelFn?labelFn(v):v}</option>`).join("");
}

async function loadPeople(){
  people = await api.get("/api/people");
  renderSuggestPersonSelect();
  renderPeopleGrid();
}

// ===== ビュー切替 =====
function switchView(v){
  document.querySelectorAll(".tabbar button").forEach(b =>
    b.classList.toggle("active", b.dataset.view === v));
  document.getElementById("view-suggest").classList.toggle("hidden", v!=="suggest");
  document.getElementById("view-people").classList.toggle("hidden", v!=="people");
  document.getElementById("view-cal").classList.toggle("hidden", v!=="cal");
  if (v==="cal") renderCalendar();
}

// ===== 🎁 提案 =====
function renderSuggestPersonSelect(){
  const el = document.getElementById("s-person");
  el.innerHTML = `<option value="">（指定なし・フォーム入力）</option>` +
    people.map(p => `<option value="${p.id}">${p.icon} ${p.name}（${RELATIONS[p.relation]||p.relation}）</option>`).join("");
  if (selectedPersonId) el.value = selectedPersonId;
}
function onSuggestPersonChange(){
  const p = people.find(x => x.id === document.getElementById("s-person").value);
  if (p) document.getElementById("s-age").value = p.age_band;
}

async function runSuggest(){
  const btn = document.getElementById("s-go");
  const status = document.getElementById("s-status");
  const results = document.getElementById("s-results");
  btn.disabled = true; results.innerHTML = ""; status.innerHTML = `<p class="loading">提案を考えています…</p>`;
  const body = {
    person_id: document.getElementById("s-person").value || null,
    age_band: document.getElementById("s-age").value,
    budget_min: budgetMin(),
    budget_max: budgetMax(),
    free_text: document.getElementById("s-free").value,
  };
  try{
    const data = await api.post("/api/suggest", body);
    let notes = "";
    if (data.relax_note){
      notes += `<div class="note" style="display:flex;align-items:center;gap:7px;background:var(--surface);color:var(--muted)">${icon("bulb",16)}<span>${esc(data.relax_note)}</span></div>`;
    }
    if (data.learned_from_history?.length || data.avoided_count){
      const bits = [];
      if (data.learned_from_history?.length) bits.push(`もらった履歴から学習：${data.learned_from_history.slice(0,5).join("・")}`);
      if (data.avoided_count) bits.push(`去年あげた${data.avoided_count}件は被り回避`);
      notes += `<div class="note" style="display:flex;align-items:center;gap:7px">${icon("sparkle",16)}<span>${bits.join(" ／ ")}</span></div>`;
    }
    status.innerHTML = notes;
    // ★ 行き止まりにしない：万一ゼロなら追い質問→ワンタップで再提案
    if (!data.cards?.length && data.followup){
      const f = data.followup;
      status.insertAdjacentHTML("beforeend", `
        <div class="panel" style="text-align:center">
          <div style="font-weight:700">${esc(f.message)}</div>
          <p class="sub" style="margin:6px 0 10px">${esc(f.question)}</p>
          <button class="primary" id="fu-go" style="margin-top:6px">予算を広げて提案する</button>
        </div>`);
      document.getElementById("fu-go").onclick = () => {
        setBudgetMax(f.suggest_budget_max);
        runSuggest();
      };
    }
    (data.cards||[]).forEach((c, idx) => {
      const evi = (c.evidence||[]).map(e => `<span>${e}</span>`).join("");
      const isTop = idx === 0;
      const typeCls = c.type === "experience" ? "experience" : "";
      results.insertAdjacentHTML("beforeend", `
        <div class="gift ${isTop?"top":""}">
          ${isTop?`<span class="rank">★ イチオシ</span>`:""}
          <div class="top-row">
            <img src="${c.image_url}" alt="" />
            <div class="body">
              <span class="type ${typeCls}">${TYPE_LABEL[c.type]||c.type}</span>
              <h3>${esc(c.name)}</h3>
              <div class="reason">${esc(c.reason)}</div>
              <div class="evi">${evi}</div>
              <a class="buy" href="${c.url}" target="_blank" rel="noopener">商品を見る →</a>
            </div>
          </div>
        </div>`);
    });
    // 手作りは商品提案しない → 別導線（儲けゼロ・一緒に考える）
    results.insertAdjacentHTML("beforeend", `
      <div class="panel" style="text-align:center">
        <div style="display:flex;align-items:center;justify-content:center;gap:6px;font-weight:700;color:var(--accent-deep)">${icon("palette",18)} 手作りで贈るのもいい</div>
        <p class="sub" style="margin:6px 0 10px">商品は出しません。何を作りたいか、一緒に考えます。</p>
        <button class="ghost" id="hm-open">手作りを一緒に考える →</button>
      </div>`);
    document.getElementById("hm-open").onclick = openHandmade;
  }catch(e){ status.innerHTML = `<p class="loading">エラー：${e}</p>`; }
  finally{ btn.disabled = false; }
}

// ===== 🎨 手作り（商品提案しない / 一緒に考える） =====
function openHandmade(){
  modal(`
    <h2>🎨 手作りで贈る</h2>
    <p class="sub">商品は出しません。一緒に“何を作るか”から考えましょう。</p>
    <label>作りたいもの（決まっていれば）</label>
    <input id="hm-want" placeholder="例：フォトブック（空欄なら一緒に考えます）" />
    <div class="modal-actions">
      <button class="ghost" id="hm-ideas">決まってない→一緒に考える</button>
      <button class="primary" style="margin:0" id="hm-plan">これで進める</button>
    </div>
    <div id="hm-out"></div>`);
  document.getElementById("hm-ideas").onclick = () => loadHandmade("");
  document.getElementById("hm-plan").onclick = () =>
    loadHandmade(document.getElementById("hm-want").value.trim());
}

async function loadHandmade(want){
  const out = document.getElementById("hm-out");
  out.innerHTML = `<p class="loading">考えています…</p>`;
  const data = await api.post("/api/handmade", {
    person_id: document.getElementById("s-person").value || null,
    free_text: document.getElementById("s-free").value,
    want,
  });
  if (data.mode === "ideas"){
    out.innerHTML = `<p class="sub" style="margin-top:14px">相手に合いそうな“作る方向”です。気になるものから一緒に詰めましょう。</p>`
      + data.ideas.map(renderIdea).join("");
  } else {
    out.innerHTML = renderPlan(data.plan);
  }
}
function renderIdea(i){
  return `<div class="panel" style="margin:10px 0">
    <div style="font-weight:700">${esc(i.title)}</div>
    <p style="font-size:13px;margin:6px 0">${esc(i.why)}</p>
    <div class="sub">材料：${(i.materials||[]).map(esc).join("、")}</div>
    <ol style="font-size:13px;margin:6px 0 0;padding-left:18px">${(i.steps||[]).map(s=>`<li>${esc(s)}</li>`).join("")}</ol>
    <div class="note" style="margin-top:8px;display:flex;align-items:center;gap:7px">${icon("bulb",16)}<span>${esc(i.tip||"")}</span></div>
  </div>`;
}
function renderPlan(p){
  return `<div class="panel" style="margin:10px 0">
    <div style="font-weight:700">${esc(p.title)}</div>
    <p style="font-size:13px;margin:6px 0">${esc(p.why)}</p>
    <div class="sub">一緒に決めたいこと：</div>
    <ul style="font-size:13px;margin:6px 0;padding-left:18px">${(p.questions||[]).map(q=>`<li>${esc(q)}</li>`).join("")}</ul>
    <div class="note">${esc(p.next||"")}</div>
  </div>`;
}

// ===== 👪 人 =====
function renderPeopleGrid(){
  const grid = document.getElementById("people-grid");
  grid.innerHTML = people.map(p => `
    <div class="person ${p.id===selectedPersonId?'sel':''}" data-id="${p.id}">
      <div class="avatar" style="background:${p.color}22;color:${p.color}">${icon(p.icon,36)}</div>
      <div class="name">${esc(p.name)}</div>
      <div class="meta">${RELATIONS[p.relation]||p.relation}・${p.age_band}</div>
      <div class="meta">${[p.birthday?("🎂"+fmtMD(p.birthday)):"", p.anniversary?("💕"+fmtMD(p.anniversary)):""].filter(Boolean).join(" ")}</div>
    </div>`).join("") +
    `<div class="add-person" id="add-person">＋ 人を登録</div>`;
  grid.querySelectorAll(".person").forEach(el =>
    el.onclick = () => selectPerson(el.dataset.id));
  document.getElementById("add-person").onclick = () => openPersonForm(null);
}

function currentPerson(){ return people.find(p => p.id === selectedPersonId); }

async function selectPerson(id){
  selectedPersonId = id;
  renderPeopleGrid();
  const p = currentPerson();
  document.getElementById("person-detail").classList.remove("hidden");
  document.getElementById("pd-avatar").innerHTML = icon(p.icon, 32);
  document.getElementById("pd-avatar").style.background = p.color+"22";
  document.getElementById("pd-avatar").style.color = p.color;
  document.getElementById("pd-name").textContent = p.name;
  document.getElementById("pd-meta").textContent =
    `${RELATIONS[p.relation]||p.relation}・${p.age_band}`
    + (p.birthday?("・🎂"+fmtMD(p.birthday)):"")
    + (p.anniversary?("・💕"+fmtMD(p.anniversary)):"")
    + (p.notes?`　／　${p.notes}`:"");
  await renderOccasions();
  await renderEvents();
}

async function renderOccasions(){
  const occ = await api.get("/api/occasions?person_id="+selectedPersonId);
  const box = document.getElementById("pd-occasions");
  if (!occ.length){ box.innerHTML = `<p class="loading">予定はまだありません。</p>`; return; }
  occ.sort((a,b)=>(a.date||"").localeCompare(b.date||""));
  box.innerHTML = occ.map(o => `
    <div class="event">
      <span class="dir gave" style="background:#fff0e6;color:#d2691e">予定</span>
      <span class="t">${esc(o.label)}</span>
      <span class="d">${o.date||""}</span>
      <button class="mini" data-delocc="${o.id}">✕</button>
    </div>`).join("");
  box.querySelectorAll("[data-delocc]").forEach(b =>
    b.onclick = async () => { await api.del("/api/occasions/"+b.dataset.delocc); renderOccasions(); loadReminders(); });
}

function openOccasionForm(){
  modal(`
    <h2>🗓 予定を追加</h2>
    <p class="sub">出産祝いなどの一回きりの予定。選択肢から選べます（自由入力は「その他」）。</p>
    <label>種類</label>
    <select id="oc-label">${ONE_TIME_OCCASIONS.map(o=>`<option>${o}</option>`).join("")}</select>
    <div id="oc-custom-wrap" class="hidden">
      <label>内容（自由入力）</label>
      <input id="oc-custom" placeholder="例：金婚式のお祝い" />
    </div>
    <label>日付</label><input id="oc-date" type="date" />
    <div class="modal-actions">
      <button class="ghost" onclick="closeModal()">キャンセル</button>
      <button class="primary" style="margin:0" id="oc-save">保存</button>
    </div>`);
  const sel = document.getElementById("oc-label");
  const customWrap = document.getElementById("oc-custom-wrap");
  sel.onchange = () => customWrap.classList.toggle("hidden", sel.value !== "その他");
  document.getElementById("oc-save").onclick = async () => {
    let label = sel.value;
    if (label === "その他"){
      label = document.getElementById("oc-custom").value.trim();
      if (!label){ alert("内容を入力してください"); return; }
    }
    const datev = document.getElementById("oc-date").value;
    if (!datev){ alert("日付を入れてください"); return; }
    await api.post("/api/occasions", {person_id: selectedPersonId, label, date: datev});
    closeModal();
    renderOccasions();
    loadReminders();
  };
}

async function renderEvents(){
  const events = await api.get("/api/events?person_id="+selectedPersonId);
  const box = document.getElementById("pd-events");
  if (!events.length){ box.innerHTML = `<p class="loading">まだ記録がありません。</p>`; return; }
  box.innerHTML = events.map(e => `
    <div class="event">
      <span class="dir ${e.direction}">${e.direction==="gave"?"あげた":"もらった"}</span>
      <span class="t">${esc(e.title)}${e.category?`<span class="d">（${esc(e.category)}）</span>`:""}</span>
      <span class="d">${e.date||""}</span>
      <button class="mini" data-del="${e.id}">✕</button>
    </div>`).join("");
  box.querySelectorAll("[data-del]").forEach(b =>
    b.onclick = async () => { await api.del("/api/events/"+b.dataset.del); renderEvents(); });
}

async function deleteCurrentPerson(){
  if (!confirm(`${currentPerson().name} を削除しますか？（贈答記録も消えます）`)) return;
  await api.del("/api/people/"+selectedPersonId);
  selectedPersonId = null;
  document.getElementById("person-detail").classList.add("hidden");
  await loadPeople();
}

// ===== モーダル =====
function modal(html){
  const root = document.getElementById("modal-root");
  root.innerHTML = `<div class="modal-bg"><div class="modal">${html}</div></div>`;
  root.querySelector(".modal-bg").onclick = (e) => { if (e.target.classList.contains("modal-bg")) closeModal(); };
}
function closeModal(){ document.getElementById("modal-root").innerHTML = ""; }

function openPersonForm(p){
  const e = p || {icon:"person",color:COLORS[0],age_band:"60s",relation:"mother"};
  modal(`
    <h2>${p?"相手を編集":"相手を登録"}</h2>
    <label>名前</label><input id="f-name" value="${esc(e.name||"")}" placeholder="お母さん" />
    <div class="row">
      <div><label>関係</label><select id="f-rel">${Object.entries(RELATIONS).map(([k,v])=>`<option value="${k}" ${k===e.relation?"selected":""}>${v}</option>`).join("")}</select></div>
      <div><label>年代</label><select id="f-age">${AGE_BANDS.map(a=>`<option ${a===e.age_band?"selected":""}>${a}</option>`).join("")}</select></div>
    </div>
    <div id="f-gender-wrap" class="hidden">
      <label>性別</label>
      <select id="f-gender">
        <option value="">選択してください</option>
        ${Object.entries(GENDERS).map(([k,v])=>`<option value="${k}" ${k===e.gender?"selected":""}>${v}</option>`).join("")}
      </select>
    </div>
    <div class="row">
      <div><label>誕生日</label><input id="f-bday" type="date" value="${e.birthday||""}" /></div>
      <div><label>記念日（結婚・交際など）</label><input id="f-anniv" type="date" value="${e.anniversary||""}" /></div>
    </div>
    <label>アイコン</label>
    <div class="icon-pick" id="f-icons">${ICONS.map(i=>`<span class="${i===e.icon?"sel":""}" data-i="${i}">${icon(i,22)}</span>`).join("")}</div>
    <label>色</label>
    <div class="color-pick" id="f-colors">${COLORS.map(c=>`<span class="${c===e.color?"sel":""}" data-c="${c}" style="background:${c}"></span>`).join("")}</div>
    <label>メモ（好きなこと・最近こぼしてたこと）</label>
    <textarea id="f-notes" placeholder="音楽、お茶、甘いもの">${esc(e.notes||"")}</textarea>
    <label>避けたいもの（任意・カンマ区切り）</label>
    <input id="f-avoid" value="${esc((e.avoid||[]).join(","))}" placeholder="香水, アルコール" />
    <div class="modal-actions">
      <button class="ghost" onclick="closeModal()">キャンセル</button>
      <button class="primary" style="margin:0" id="f-save">保存</button>
    </div>`);
  // 関係で性別が確定する時は性別欄を隠す（自明なので入力不要）
  const genderWrap = document.getElementById("f-gender-wrap");
  const toggleGender = () => {
    const rel = document.getElementById("f-rel").value;
    genderWrap.classList.toggle("hidden", rel in AUTO_GENDER);
  };
  document.getElementById("f-rel").onchange = toggleGender;
  toggleGender();

  let icon=e.icon, color=e.color;
  document.querySelectorAll("#f-icons span").forEach(s => s.onclick = () => {
    icon=s.dataset.i; document.querySelectorAll("#f-icons span").forEach(x=>x.classList.remove("sel")); s.classList.add("sel");
  });
  document.querySelectorAll("#f-colors span").forEach(s => s.onclick = () => {
    color=s.dataset.c; document.querySelectorAll("#f-colors span").forEach(x=>x.classList.remove("sel")); s.classList.add("sel");
  });
  document.getElementById("f-save").onclick = async () => {
    const name = document.getElementById("f-name").value.trim();
    if (!name){ alert("名前を入れてください"); return; }
    const rel = document.getElementById("f-rel").value;
    const gender = AUTO_GENDER[rel] || document.getElementById("f-gender").value;
    if (!gender){ alert("性別を選んでください"); return; }
    const body = {
      id: p?.id || null, name,
      relation: rel, gender,
      age_band: document.getElementById("f-age").value,
      birthday: document.getElementById("f-bday").value,
      anniversary: document.getElementById("f-anniv").value,
      icon, color,
      notes: document.getElementById("f-notes").value,
      avoid: splitCsv(document.getElementById("f-avoid").value),
      likes: e.likes||[],
    };
    const saved = await api.post("/api/people", body);
    closeModal();
    selectedPersonId = saved.id;
    await loadPeople();
    selectPerson(saved.id);
  };
}

function openEventForm(){
  modal(`
    <h2>🎁 贈答を記録</h2>
    <div class="row">
      <div><label>どっち？</label>
        <select id="ev-dir"><option value="gave">あげた</option><option value="received">もらった</option></select></div>
      <div><label>日付</label><input id="ev-date" type="date" /></div>
    </div>
    <label>品名</label><input id="ev-title" placeholder="今治タオルセット" />
    <div class="row">
      <div><label>カテゴリ（任意）</label><input id="ev-cat" placeholder="タオル・日用品" /></div>
      <div><label>価格（任意）</label><input id="ev-price" type="number" placeholder="4800" /></div>
    </div>
    <label>反応・メモ（任意）</label><input id="ev-react" placeholder="すごく喜んでた" />
    <div class="modal-actions">
      <button class="ghost" onclick="closeModal()">キャンセル</button>
      <button class="primary" style="margin:0" id="ev-save">保存</button>
    </div>`);
  document.getElementById("ev-save").onclick = async () => {
    const title = document.getElementById("ev-title").value.trim();
    if (!title){ alert("品名を入れてください"); return; }
    await api.post("/api/events", {
      person_id: selectedPersonId,
      direction: document.getElementById("ev-dir").value,
      title,
      category: document.getElementById("ev-cat").value,
      price: Number(document.getElementById("ev-price").value)||0,
      reaction: document.getElementById("ev-react").value,
      date: document.getElementById("ev-date").value,
    });
    closeModal();
    renderEvents();
  };
}

// ===== 📅 カレンダー =====
async function renderCalendar(){
  const y = calDate.getFullYear(), m = calDate.getMonth();
  document.getElementById("cal-title").textContent = `${y}年 ${m+1}月`;
  const allEvents = await api.get("/api/events");
  const first = new Date(y, m, 1).getDay();
  const days = new Date(y, m+1, 0).getDate();
  const today = new Date();
  const dows = ["日","月","火","水","木","金","土"];
  let html = dows.map(d => `<div class="dow">${d}</div>`).join("");
  for (let i=0;i<first;i++) html += `<div class="cell empty"></div>`;
  for (let d=1; d<=days; d++){
    const md = `${String(m+1).padStart(2,"0")}-${String(d).padStart(2,"0")}`;
    const iso = `${y}-${md}`;
    const bdayPeople = people.filter(p => p.birthday && fmtMD(p.birthday) === pretty(md));
    const annivPeople = people.filter(p => p.anniversary && fmtMD(p.anniversary) === pretty(md));
    const hasGift = allEvents.some(e => e.date === iso);
    const isToday = today.getFullYear()===y && today.getMonth()===m && today.getDate()===d;
    const marks = bdayPeople.map(p =>
      `<span class="bday" style="background:${p.color}22;color:${p.color}" data-pid="${p.id}" title="${p.name}の誕生日">${icon(p.icon,16)}</span>`).join("")
      + annivPeople.map(p =>
      `<span class="bday" style="background:#f0ddd2;color:#c25a3c" data-pid="${p.id}" title="${p.name}との記念日">${icon("heart",15)}</span>`).join("")
      + (hasGift?`<span class="gift-dot" style="color:var(--muted)">${icon("gift",14)}</span>`:"");
    html += `<div class="cell ${isToday?'today':''}"><span class="num">${d}</span><div class="marks">${marks}</div></div>`;
  }
  const grid = document.getElementById("cal-grid");
  grid.innerHTML = html;
  grid.querySelectorAll(".bday[data-pid]").forEach(el => el.onclick = () => {
    selectedPersonId = el.dataset.pid;
    switchView("suggest");
    renderSuggestPersonSelect();
    onSuggestPersonChange();
  });
}

// ===== ユーティリティ =====
function fmtMD(b){ // "YYYY-MM-DD" or "MM-DD" → "MM/DD"
  const md = b.length>=10 ? b.slice(5) : b;
  return pretty(md);
}
function pretty(md){ return md.replace("-","/"); }
function splitCsv(s){ return (s||"").split(/[、,]/).map(x=>x.trim()).filter(Boolean); }
function esc(s){ return (s||"").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c])); }
