// ===== 定数 =====
const RELATIONS = {mother:"母",father:"父",grandmother:"祖母",grandfather:"祖父",
  partner:"パートナー",friend:"友人",child:"子ども",grandchild:"孫",sibling:"きょうだい",other:"その他"};
const AGE_BANDS = ["10s","20s","30s","40s","50s","60s","70s","80s"];
// 予算スライダーの停止点：2000〜1万円は1000刻み、1万円超は5000刻みで10万まで。
// 最上段(10万)は「10万円以上＝上限なし」扱い。
const BUDGET_STEPS = (() => {
  const a = [];
  for (let v = 2000; v <= 10000; v += 1000) a.push(v);
  for (let v = 15000; v <= 100000; v += 5000) a.push(v);
  return a;
})();
const BUDGET_TOP = BUDGET_STEPS.length - 1;       // 10万円＝上限なしの位置
const BUDGET_DEFAULT = 8000;
// 非線形配分：大半の人が収まる1万円以下を“広く”取る（低予算に見せない）。
// 1万円以下の停止点は幅4、1万円超は幅1 → バーの約6割が1万円以下になる。
const BUDGET_W = BUDGET_STEPS.map(v => v <= 10000 ? 4 : 1);
const BUDGET_POS = (() => { let acc = 0; return BUDGET_W.map((w, i) => (acc += (i ? w : 0))); })();
const BUDGET_POS_MAX = BUDGET_POS[BUDGET_POS.length - 1];
function _posToIdx(p){
  let best = 0, bd = Infinity;
  for (let i = 0; i < BUDGET_POS.length; i++){ const d = Math.abs(BUDGET_POS[i] - p); if (d < bd){ bd = d; best = i; } }
  return best;
}
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
let calMarks = {};               // 表示中の月の {日: [イベント]}
let isSubscribed = false;        // 有料会員か
let freeVisible = 2;             // 無料で表示する提案件数
let freePeopleLimit = 2;         // 無料で登録できる人数

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
    <h2 style="display:flex;align-items:center;gap:8px">${icon("settings",20)} 設定</h2>
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
    <label style="margin-top:16px">会員（動作確認用トグル）</label>
    <div class="theme-opt" id="sub-row">
      <div class="sw" style="background:linear-gradient(135deg,#cda46a,#b58a48)"></div>
      <div style="flex:1"><div class="tn">${isSubscribed?"プレミアム会員":"無料会員"}</div>
        <div class="td">${isSubscribed?"広告なし・無制限・記録/写真OK":`広告あり・${freePeopleLimit}人まで・提案${freeVisible}件まで`}</div></div>
      <button class="ghost" id="sub-btn" style="margin:0">${isSubscribed?"無料に戻す":"プレミアムにする"}</button>
    </div>
    <div class="modal-actions"><button class="ghost" onclick="closeModal()">閉じる</button></div>`);
  document.querySelectorAll(".theme-opt[data-theme]").forEach(el => el.onclick = () => {
    const theme = el.dataset.theme;
    localStorage.setItem("theme", theme);
    applyTheme(theme);
    document.querySelectorAll(".theme-opt[data-theme]").forEach(x => x.classList.remove("sel"));
    el.classList.add("sel");
  });
  document.getElementById("sub-btn").onclick = async () => {
    await api.post("/api/settings", {subscribed: !isSubscribed});
    isSubscribed = !isSubscribed;
    renderAds();
    await loadPeople();
    closeModal();
  };
}

// ===== 起動 =====
init();
async function init(){
  document.querySelectorAll("[data-icon]").forEach(el => el.innerHTML = icon(el.dataset.icon, +el.dataset.size || 24));
  document.getElementById("open-settings").onclick = openSettings;
  const logo = document.querySelector(".appbar .logo");
  if (logo){ logo.style.cursor = "pointer"; logo.onclick = surpriseGift; }   // 隠しギミック
  setupBudgetRange();
  fillSelect("s-age", AGE_BANDS);
  document.querySelectorAll(".tabbar button").forEach(b =>
    b.onclick = () => switchView(b.dataset.view));
  document.getElementById("s-go").onclick = runSuggest;
  document.getElementById("s-person").onchange = onSuggestPersonChange;
  document.getElementById("cal-prev").onclick = () => { calDate.setMonth(calDate.getMonth()-1); renderCalendar(); };
  document.getElementById("cal-next").onclick = () => { calDate.setMonth(calDate.getMonth()+1); renderCalendar(); };
  document.getElementById("cal-prev-year").onclick = () => { calDate.setFullYear(calDate.getFullYear()-1); renderCalendar(); };
  document.getElementById("cal-next-year").onclick = () => { calDate.setFullYear(calDate.getFullYear()+1); renderCalendar(); };
  document.getElementById("cal-today").onclick = () => { calDate = new Date(); calDate.setDate(1); renderCalendar(); };
  document.getElementById("pd-add-event").onclick = () => openEventForm();
  document.getElementById("pd-add-occasion").onclick = () => openOccasionForm();
  document.getElementById("pd-edit").onclick = () => openPersonForm(currentPerson());
  document.getElementById("pd-del").onclick = deleteCurrentPerson;
  await loadSettings();
  await loadPeople();
  await loadReminders();
}

// ===== 会員状態・広告 =====
async function loadSettings(){
  const s = await api.get("/api/settings");
  isSubscribed = !!s.subscribed;
  freeVisible = s.free_suggest_visible ?? 2;
  freePeopleLimit = s.free_people_limit ?? 2;
  renderAds();
}
function renderAds(){
  document.getElementById("ad-banner").classList.toggle("hidden", isSubscribed);
}
async function subscribe(){
  await api.post("/api/settings", {subscribed: true});
  isSubscribed = true;
  renderAds();
  await loadPeople();
}
// 隠しギミック：タイトルタップでランダム1点。連打対策で4回目以降はタップ広告に。
let surpriseTaps = 0;
const SURPRISE_FREE = 3;
const AD_URL = "https://www.rakuten.co.jp/";   // TODO: 本番はアフィリエイト広告リンクに差し替え
function openAdModal(){
  modal(`
    <h2 style="display:flex;align-items:center;gap:8px">${icon("gift",20)} スポンサー</h2>
    <div class="ad" id="ad-go" style="cursor:pointer">
      <span class="ad-tag">広告</span>
      <span>提携ショップでギフトをもっと探す →</span>
    </div>
    <p class="sub" style="margin:8px 0 0">※ひらめきギフトの連続表示は3回まで。プレミアムなら無制限・広告なし。</p>
    <div class="modal-actions">
      <button class="ghost" onclick="closeModal()">閉じる</button>
      <button class="primary" style="margin:0" id="ad-premium">プレミアムにする</button>
    </div>`);
  document.getElementById("ad-go").onclick = () => window.open(AD_URL, "_blank", "noopener");
  document.getElementById("ad-premium").onclick = () => openUpsell("ひらめきギフトを無制限・広告なしで。");
}
async function surpriseGift(){
  surpriseTaps++;
  if (!isSubscribed && surpriseTaps > SURPRISE_FREE){ openAdModal(); return; }  // 連打→広告
  const c = await api.get("/api/surprise");
  if (!c || c.detail) return;
  modal(`
    <h2 style="display:flex;align-items:center;gap:8px">${icon("sparkle",20)} ひらめきギフト</h2>
    <div class="gift" style="box-shadow:none;border:1px solid var(--line)">
      <div class="top-row">
        <img src="${c.image_url}" alt="" />
        <div class="body">
          <span class="type ${c.type==="experience"?"experience":""}">${TYPE_LABEL[c.type]||c.type}</span>
          <h3 title="${esc(c.name)}">${esc(c.name)}</h3>
          <div class="reason">${esc(c.reason)}</div>
          <div class="evi">${(c.evidence||[]).map(e=>`<span>${e}</span>`).join("")}</div>
          <div class="buy-row">${priceHTML(c)}<a class="buy" href="${c.url}" target="_blank" rel="noopener">商品を見る →</a></div>
        </div>
      </div>
    </div>
    <div class="modal-actions">
      <button class="ghost" onclick="closeModal()">閉じる</button>
      <button class="primary" style="margin:0" id="sp-again">もう一回</button>
    </div>`);
  document.getElementById("sp-again").onclick = surpriseGift;
}

function openUpsell(msg){
  modal(`
    <h2 style="display:flex;align-items:center;gap:8px">${icon("sparkle",20)} プレミアム</h2>
    <p class="sub">${esc(msg || "プレミアム会員の機能です。")}</p>
    <ul style="font-size:13px;color:var(--muted);line-height:2;margin:6px 0">
      <li>提案をすべて表示（無料は${freeVisible}件まで）</li>
      <li>相手を無制限に登録（無料は${freePeopleLimit}人まで）</li>
      <li>あげた／もらったを写真付きで記録</li>
      <li>広告なし</li>
    </ul>
    <div class="modal-actions">
      <button class="ghost" onclick="closeModal()">閉じる</button>
      <button class="primary" style="margin:0" id="up-go">プレミアムにする（体験）</button>
    </div>`);
  document.getElementById("up-go").onclick = async () => { await subscribe(); closeModal(); };
}

// ===== 🔔 リマインド =====
async function loadReminders(){
  const box = document.getElementById("reminders");
  const list = await api.get("/api/reminders");
  if (!list.length){ box.innerHTML = ""; return; }
  box.innerHTML = list.map(r => {
    const person = r.person_id ? people.find(p => p.id === r.person_id) : null;
    const ic = person ? avatarHTML(person, person.photo_url ? 38 : 22)
                      : icon(OCCASION_ICON[r.occasion] || "gift", 22);
    return `
    <div class="remind ${r.stage}" ${r.person_id?`data-pid="${r.person_id}"`:""}>
      <div class="ric" style="background:${r.color}22;color:${r.color}">${ic}</div>
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
  [lo, hi].forEach(s => { s.min = 0; s.max = BUDGET_POS_MAX; s.step = 1; });
  lo.value = BUDGET_POS[BUDGET_STEPS.indexOf(2000)];
  hi.value = BUDGET_POS[BUDGET_STEPS.indexOf(BUDGET_DEFAULT)];
  const fill = document.getElementById("budget-fill"), label = document.getElementById("budget-label");
  const update = (e) => {
    let ai = _posToIdx(+lo.value), bi = _posToIdx(+hi.value);
    if (e && e.target === lo && ai > bi) bi = ai;          // 上限は下限を下回らない
    if (e && e.target === hi && bi < ai) bi = ai;
    lo.value = BUDGET_POS[ai]; hi.value = BUDGET_POS[bi];  // 停止点にスナップ
    const hiLabel = bi === BUDGET_TOP ? `${BUDGET_STEPS[BUDGET_TOP].toLocaleString()}円以上`
                                      : `${BUDGET_STEPS[bi].toLocaleString()}円`;
    label.textContent = `${BUDGET_STEPS[ai].toLocaleString()}円 〜 ${hiLabel}`;
    const pa = BUDGET_POS[ai] / BUDGET_POS_MAX * 100, pb = BUDGET_POS[bi] / BUDGET_POS_MAX * 100;
    fill.style.left = pa + "%"; fill.style.width = (pb - pa) + "%";
  };
  lo.oninput = update; hi.oninput = update;
  update();
}
function _curIdx(id){ return _posToIdx(+document.getElementById(id).value); }
function budgetMin(){ return BUDGET_STEPS[_curIdx("s-bmin-r")]; }
function budgetMax(){
  const i = _curIdx("s-bmax-r");
  return i === BUDGET_TOP ? 99999999 : BUDGET_STEPS[i];    // 最上段＝上限なし
}
function setBudgetMax(v){
  let idx = BUDGET_STEPS.findIndex(x => x >= v);
  if (idx < 0) idx = BUDGET_TOP;
  const loIdx = _curIdx("s-bmin-r");
  if (idx < loIdx) idx = loIdx;
  const hi = document.getElementById("s-bmax-r");
  hi.value = BUDGET_POS[idx]; hi.dispatchEvent(new Event("input"));
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
    people.map(p => `<option value="${p.id}">${displayName(p)}（${RELATIONS[p.relation]||p.relation}）</option>`).join("");
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
    // 無料の1日上限：コストを使わず即・アップセル
    if (data.limited){
      status.innerHTML = `
        <div class="panel" style="text-align:center">
          <div style="font-weight:700">${esc(data.limit_message)}</div>
          <button class="primary" id="lim-go" style="margin-top:12px">プレミアムにする</button>
        </div>`;
      document.getElementById("lim-go").onclick = () => openUpsell("回数制限なしで使えます。");
      return;
    }
    let notes = "";
    if (data.remaining_today !== null && data.remaining_today !== undefined){
      notes += `<p class="sub" style="margin:0 0 8px">今日の無料提案：あと${data.remaining_today}回</p>`;
    }
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
    const locKed = !data.subscribed ? (data.free_visible ?? freeVisible) : Infinity;
    (data.cards||[]).forEach((c, idx) => {
      const evi = (c.evidence||[]).map(e => `<span>${e}</span>`).join("");
      const isTop = idx === 0;
      const typeCls = c.type === "experience" ? "experience" : "";
      const locked = idx >= locKed;
      results.insertAdjacentHTML("beforeend", `
        <div class="gift ${isTop?"top":""} ${locked?"locked":""}">
          ${isTop && !locked?`<span class="rank">★ イチオシ</span>`:""}
          <div class="top-row">
            <img src="${c.image_url}" alt="" />
            <div class="body">
              <span class="type ${typeCls}">${TYPE_LABEL[c.type]||c.type}</span>
              <h3 title="${esc(c.name)}">${esc(c.name)}</h3>
              <div class="reason">${esc(c.reason)}</div>
              <div class="evi">${evi}</div>
              <div class="buy-row">${priceHTML(c)}<a class="buy" href="${c.url}" target="_blank" rel="noopener">商品を見る →</a></div>
            </div>
          </div>
          ${locked?`<div class="lock-ov"><div class="lock-msg">${icon("sparkle",16)}プレミアムで全部見る</div><button class="ghost up-btn">プレミアムにする</button></div>`:""}
        </div>`);
    });
    results.querySelectorAll(".up-btn").forEach(b =>
      b.onclick = () => openUpsell(`提案は無料だと${data.free_visible ?? freeVisible}件まで。続きはプレミアムで。`));
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
    <h2 style="display:flex;align-items:center;gap:8px">${icon("palette",20)} 手作りで贈る</h2>
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
    <div class="person ${p.id===selectedPersonId?'sel':''}" data-id="${p.id}" draggable="true">
      <div class="avatar" style="background:${p.color}22;color:${p.color}">${avatarHTML(p,p.photo_url?56:36)}</div>
      <div class="name">${esc(displayName(p))}</div>
      <div class="meta">${RELATIONS[p.relation]||p.relation}・${p.age_band}</div>
      <div class="meta">${[
        p.birthday?`<span style="display:inline-flex;align-items:center;gap:2px">${icon("birthday",12)}${fmtMD(p.birthday)}</span>`:"",
        p.anniversary?`<span style="display:inline-flex;align-items:center;gap:2px">${icon("heart",12)}${fmtMD(p.anniversary)}</span>`:""
      ].filter(Boolean).join(" ")}</div>
    </div>`).join("") +
    `<div class="add-person" id="add-person">＋ 人を登録</div>`;
  let dragId = null;
  grid.querySelectorAll(".person").forEach(el => {
    el.onclick = () => { if (!el.classList.contains("was-dragged")) selectPerson(el.dataset.id); };
    el.addEventListener("dragstart", () => { dragId = el.dataset.id; el.classList.add("dragging"); });
    el.addEventListener("dragend", () => { el.classList.remove("dragging");
      setTimeout(() => el.classList.remove("was-dragged"), 50); });
    el.addEventListener("dragover", e => e.preventDefault());
    el.addEventListener("drop", e => {
      e.preventDefault();
      el.classList.add("was-dragged");            // ドロップ直後の誤クリック選択を抑止
      if (dragId && dragId !== el.dataset.id) reorderPeople(dragId, el.dataset.id);
    });
  });
  document.getElementById("add-person").onclick = addPerson;
}

async function reorderPeople(dragId, targetId){
  const ids = people.map(p => p.id);
  const from = ids.indexOf(dragId), to = ids.indexOf(targetId);
  if (from < 0 || to < 0) return;
  ids.splice(to, 0, ids.splice(from, 1)[0]);      // ドラッグした人を相手の位置へ挿入
  await api.post("/api/people/reorder", {ids});
  await loadPeople();
}

function addPerson(){
  if (!isSubscribed && people.length >= freePeopleLimit){
    openUpsell(`無料会員は${freePeopleLimit}人まで。プレミアムで無制限に登録できます。`); return;
  }
  openPersonForm(null);
}

function currentPerson(){ return people.find(p => p.id === selectedPersonId); }
// 名前が未入力なら関係名（「母」など）で成り立たせる
function displayName(p){ return (p.name && p.name.trim()) || RELATIONS[p.relation] || "相手"; }
// 価格を大きく表示（セールなら通常価格に取り消し線）
function priceHTML(c){
  if (c.list_price && c.list_price > c.price){
    return `<span class="price"><span class="was">¥${c.list_price.toLocaleString()}</span>`
      + `<span class="now">¥${c.price.toLocaleString()}</span><span class="sale">セール</span></span>`;
  }
  return `<span class="price">¥${(c.price||0).toLocaleString()}</span>`;
}
// 顔写真があれば写真、無ければアイコン（顔写真は無料機能）
function avatarHTML(p, size){
  if (p.photo_url) return `<img src="${p.photo_url}" alt="" style="width:${size}px;height:${size}px;border-radius:50%;object-fit:cover;display:block" />`;
  return icon(p.icon, size);
}

async function selectPerson(id){
  selectedPersonId = id;
  renderPeopleGrid();
  const p = currentPerson();
  document.getElementById("person-detail").classList.remove("hidden");
  document.getElementById("pd-title").textContent = `${displayName(p)}さんの予定・記録`;
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
    <h2 style="display:flex;align-items:center;gap:8px">${icon("calendar",20)} 予定を追加</h2>
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
      ${e.photo_url?`<img class="ev-thumb" src="${e.photo_url}" alt="" />`:""}
      <span class="dir ${e.direction}">${e.direction==="gave"?"あげた":"もらった"}</span>
      <span class="t">${esc(e.title)}${e.category?`<span class="d">（${esc(e.category)}）</span>`:""}</span>
      <span class="d">${e.date||""}</span>
      <button class="mini" data-del="${e.id}">✕</button>
    </div>`).join("");
  box.querySelectorAll("[data-del]").forEach(b =>
    b.onclick = async () => { await api.del("/api/events/"+b.dataset.del); renderEvents(); });
}

async function deleteCurrentPerson(){
  if (!confirm(`${displayName(currentPerson())} を削除しますか？（贈答記録も消えます）`)) return;
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
    <label>名前（任意）</label><input id="f-name" value="${esc(e.name||"")}" placeholder="未入力でOK（「母」などで表示）" />
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
    <label>顔写真（任意・無料）</label>
    <input class="ev-photo-input" id="f-photo" type="file" accept="image/*" />
    <div id="f-photo-preview">${e.photo_url?`<img src="${e.photo_url}" style="margin-top:8px;width:72px;height:72px;border-radius:50%;object-fit:cover" />`:""}</div>
    <label style="margin-top:8px">アイコン（写真が無い時に表示）</label>
    <div class="icon-pick" id="f-icons">${ICONS.map(i=>`<span class="${i===e.icon?"sel":""}" data-i="${i}" title="${(typeof AVATAR_LABELS!=='undefined'&&AVATAR_LABELS[i])||i}">${icon(i,22)}</span>`).join("")}</div>
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

  let pickedIcon=e.icon, color=e.color, photoData=e.photo_url||"";   // ローカル名はグローバルicon()と衝突させない
  document.getElementById("f-photo").onchange = (ev) => {
    const f = ev.target.files[0]; if (!f) return;
    resizeImage(f, 512, (d) => {
      photoData = d;
      document.getElementById("f-photo-preview").innerHTML =
        `<img src="${d}" style="margin-top:8px;width:72px;height:72px;border-radius:50%;object-fit:cover" />`;
    });
  };
  document.querySelectorAll("#f-icons span").forEach(s => s.onclick = () => {
    pickedIcon=s.dataset.i; document.querySelectorAll("#f-icons span").forEach(x=>x.classList.remove("sel")); s.classList.add("sel");
  });
  document.querySelectorAll("#f-colors span").forEach(s => s.onclick = () => {
    color=s.dataset.c; document.querySelectorAll("#f-colors span").forEach(x=>x.classList.remove("sel")); s.classList.add("sel");
  });
  document.getElementById("f-save").onclick = async () => {
    const name = document.getElementById("f-name").value.trim();   // 任意（空でOK）
    const rel = document.getElementById("f-rel").value;
    const gender = AUTO_GENDER[rel] || document.getElementById("f-gender").value;
    if (!gender){ alert("性別を選んでください"); return; }
    const body = {
      id: p?.id || null, name,
      relation: rel, gender,
      age_band: document.getElementById("f-age").value,
      birthday: document.getElementById("f-bday").value,
      anniversary: document.getElementById("f-anniv").value,
      icon: pickedIcon, color, photo_url: photoData,
      notes: document.getElementById("f-notes").value,
      avoid: splitCsv(document.getElementById("f-avoid").value),
      likes: e.likes||[],
    };
    const saved = await api.post("/api/people", body);
    if (saved && saved.detail){ openUpsell(saved.detail); return; }   // 上限などはアップセル
    closeModal();
    selectedPersonId = saved.id;
    await loadPeople();
    selectPerson(saved.id);
  };
}

function openEventForm(){
  if (!isSubscribed){     // 記録は有料会員のみ
    openUpsell("「あげた／もらった」を写真付きで記録できるのはプレミアム会員です。記録するほど提案が当たります。");
    return;
  }
  let photoData = "";     // 縮小後の data URL
  modal(`
    <h2 style="display:flex;align-items:center;gap:8px">${icon("gift",20)} 贈答を記録</h2>
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
    <label>写真（任意）</label>
    <input class="ev-photo-input" id="ev-photo" type="file" accept="image/*" />
    <div id="ev-preview"></div>
    <div class="modal-actions">
      <button class="ghost" onclick="closeModal()">キャンセル</button>
      <button class="primary" style="margin:0" id="ev-save">保存</button>
    </div>`);
  document.getElementById("ev-photo").onchange = (ev) => {
    const file = ev.target.files[0];
    if (!file) return;
    resizeImage(file, 640, (dataUrl) => {
      photoData = dataUrl;
      document.getElementById("ev-preview").innerHTML = `<img src="${dataUrl}" alt="プレビュー" />`;
    });
  };
  document.getElementById("ev-save").onclick = async () => {
    const title = document.getElementById("ev-title").value.trim();
    if (!title){ alert("品名を入れてください"); return; }
    const res = await api.post("/api/events", {
      person_id: selectedPersonId,
      direction: document.getElementById("ev-dir").value,
      title,
      category: document.getElementById("ev-cat").value,
      price: Number(document.getElementById("ev-price").value)||0,
      reaction: document.getElementById("ev-react").value,
      date: document.getElementById("ev-date").value,
      photo_url: photoData,
    });
    if (res && res.detail){ openUpsell(res.detail); return; }
    closeModal();
    renderEvents();
  };
}

// 写真をクライアントで縮小して data URL に（store.json肥大を防ぐ）
function resizeImage(file, max, cb){
  const fr = new FileReader();
  fr.onload = () => {
    const img = new Image();
    img.onload = () => {
      const s = Math.min(1, max / Math.max(img.width, img.height));
      const c = document.createElement("canvas");
      c.width = Math.round(img.width * s); c.height = Math.round(img.height * s);
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      cb(c.toDataURL("image/jpeg", 0.8));
    };
    img.src = fr.result;
  };
  fr.readAsDataURL(file);
}

// ===== 📅 カレンダー =====
async function renderCalendar(){
  const y = calDate.getFullYear(), m = calDate.getMonth();
  document.getElementById("cal-title").textContent = `${y}年 ${m+1}月`;
  const marksList = await api.get(`/api/calendar?y=${y}&m=${m+1}`);   // 当月の全イベント
  const byDay = {};
  marksList.forEach(mk => (byDay[mk.day] = byDay[mk.day] || []).push(mk));
  calMarks = byDay;
  const first = new Date(y, m, 1).getDay();
  const days = new Date(y, m+1, 0).getDate();
  const today = new Date();
  const dows = ["日","月","火","水","木","金","土"];
  const hol = getHolidays(y);
  let html = dows.map((d, i) => `<div class="dow ${i===0?'sun':i===6?'sat':''}">${d}</div>`).join("");
  for (let i=0;i<first;i++) html += `<div class="cell empty"></div>`;
  for (let d=1; d<=days; d++){
    const wd = new Date(y, m, d).getDay();
    const holName = hol[`${m+1}-${d}`];
    const isToday = today.getFullYear()===y && today.getMonth()===m && today.getDate()===d;
    const marks = (byDay[d] || []).map(markHTML).join("");
    const cls = [isToday?'today':'', wd===0?'sun':'', wd===6?'sat':'', holName?'holiday':''].filter(Boolean).join(' ');
    html += `<div class="cell ${cls}" data-day="${d}"><span class="num">${d}</span>`
      + (holName?`<span class="hol-name" title="${holName}">${holName}</span>`:"")
      + `<div class="marks">${marks}</div></div>`;
  }
  const grid = document.getElementById("cal-grid");
  grid.innerHTML = html;
  grid.querySelectorAll(".cell[data-day]").forEach(el =>
    el.onclick = () => openDayModal(y, m, +el.dataset.day));   // 日タップ→メモ／提案
}

// 日付タップ：イベントがある日は「提案」と「メモ」を両方選べる
async function openDayModal(y, m, d){
  const dateStr = `${y}-${String(m+1).padStart(2,"0")}-${String(d).padStart(2,"0")}`;
  const evs = (calMarks[d] || []).filter(x => x.kind !== "memo");
  const mm = await api.get("/api/memos?date=" + dateStr);
  const persons = [...new Set(evs.filter(e => e.person_id).map(e => e.person_id))]
    .map(id => people.find(p => p.id === id)).filter(Boolean);
  const evList = evs.length
    ? `<div style="margin:4px 0 10px;font-size:13px;line-height:1.8">${evs.map(e =>
        "・" + esc((e.person_id ? displayName(people.find(p=>p.id===e.person_id)) + "：" : "") + e.label)).join("<br>")}</div>`
    : `<p class="sub" style="margin:4px 0 10px">この日の予定はありません。</p>`;
  const suggestBtns = persons.map(p =>
    `<button class="ghost dm-suggest" data-pid="${p.id}" style="width:100%;margin-top:8px">${esc(displayName(p))}への提案を見る</button>`).join("");
  modal(`
    <h2>${y}年${m+1}月${d}日</h2>
    ${evList}
    ${suggestBtns}
    <label style="margin-top:12px">メモ</label>
    <textarea id="dm-memo" placeholder="この日のメモ（買うもの・アイデアなど）">${esc(mm.text||"")}</textarea>
    <div class="modal-actions">
      <button class="ghost" onclick="closeModal()">閉じる</button>
      <button class="primary" style="margin:0" id="dm-save">メモを保存</button>
    </div>`);
  document.querySelectorAll(".dm-suggest").forEach(b => b.onclick = () => {
    selectedPersonId = b.dataset.pid;
    closeModal(); switchView("suggest"); renderSuggestPersonSelect(); onSuggestPersonChange();
  });
  document.getElementById("dm-save").onclick = async () => {
    await api.post("/api/memos", {date: dateStr, text: document.getElementById("dm-memo").value});
    closeModal(); renderCalendar();
  };
}

// カレンダーの1イベントを描画
function markHTML(mk){
  const p = mk.person_id ? people.find(x => x.id === mk.person_id) : null;
  const pid = p ? `data-pid="${p.id}"` : "";
  if (mk.kind === "birthday" && p)
    return `<span class="bday" style="background:${p.color}22;color:${p.color}" ${pid} title="${esc(displayName(p))}の誕生日">${avatarHTML(p, p.photo_url?24:16)}</span>`;
  if (mk.kind === "anniversary")
    return `<span class="bday" style="background:#f0ddd2;color:#c25a3c" ${pid} title="${esc((p?displayName(p):"")+"との記念日")}">${icon("heart",15)}</span>`;
  if (mk.kind === "gift")
    return `<span class="gift-dot" title="${esc(mk.label)}">${icon("gift",14)}</span>`;
  if (mk.kind === "memo")
    return `<span class="cal-occ" title="メモ" style="background:var(--surface);color:var(--muted)">${icon("memo",14)}</span>`;
  // occasion（母の日・行事・カスタム予定・入学/成人 など）
  const key = OCCASION_ICON[mk.label] || "gift";
  const title = (p ? displayName(p) + "：" : "") + mk.label;
  return `<span class="cal-occ" ${pid} title="${esc(title)}">${icon(key,15)}</span>`;
}

// ===== ユーティリティ =====
function fmtMD(b){ // "YYYY-MM-DD" or "MM-DD" → "MM/DD"
  const md = b.length>=10 ? b.slice(5) : b;
  return pretty(md);
}
function pretty(md){ return md.replace("-","/"); }
function splitCsv(s){ return (s||"").split(/[、,]/).map(x=>x.trim()).filter(Boolean); }
function esc(s){ return (s||"").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c])); }
