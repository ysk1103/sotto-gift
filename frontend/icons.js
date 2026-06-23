// オリジナル線画アイコン（SVG）。1色 currentColor でテーマに自動追従。
// icon(key, size) で <svg> 文字列を返す。未知キーは gift にフォールバック。

const SVG_ICON_PATHS = {
  // --- UI ---
  gift: `<rect x="3" y="8" width="18" height="4" rx="1"/><rect x="4.5" y="12" width="15" height="8" rx="1"/><line x1="12" y1="8" x2="12" y2="20"/><path d="M12 8C9.5 4 6 5.5 12 8"/><path d="M12 8C14.5 4 18 5.5 12 8"/>`,
  people: `<circle cx="8.5" cy="8" r="2.8"/><path d="M4 19c0-2.7 2-4.5 4.5-4.5S13 16.3 13 19"/><circle cx="16" cy="8.5" r="2.3"/><path d="M14.8 14.7c2.2.2 4.2 2 4.2 4.3"/>`,
  calendar: `<rect x="3.5" y="5" width="17" height="15" rx="2"/><line x1="3.5" y1="9.5" x2="20.5" y2="9.5"/><line x1="8" y1="3" x2="8" y2="6"/><line x1="16" y1="3" x2="16" y2="6"/><circle cx="9" cy="14" r="1"/><circle cx="15" cy="14" r="1"/>`,
  settings: `<line x1="4" y1="6.5" x2="20" y2="6.5"/><circle cx="9" cy="6.5" r="2"/><line x1="4" y1="12" x2="20" y2="12"/><circle cx="15" cy="12" r="2"/><line x1="4" y1="17.5" x2="20" y2="17.5"/><circle cx="8" cy="17.5" r="2"/>`,
  bell: `<path d="M6 9a6 6 0 0 1 12 0c0 4 1.5 5 2 6H4c.5-1 2-2 2-6z"/><path d="M10 19a2 2 0 0 0 4 0"/>`,
  palette: `<path d="M12 3a9 9 0 1 0 0 18c1.5 0 2-1 1.5-2-.6-1.2.3-2.5 1.5-2.5H17a4 4 0 0 0 4-4c0-4.7-4-7.5-9-7.5z"/><circle cx="7.8" cy="11.5" r="1" fill="currentColor" stroke="none"/><circle cx="10" cy="7.8" r="1" fill="currentColor" stroke="none"/><circle cx="14.5" cy="7.8" r="1" fill="currentColor" stroke="none"/>`,
  bulb: `<path d="M9.5 17h5"/><path d="M10 20h4"/><path d="M12 3a6 6 0 0 0-3.5 10.9c.6.5.9 1 1 2.1h5c.1-1.1.4-1.6 1-2.1A6 6 0 0 0 12 3z"/>`,
  sparkle: `<path d="M12 4l1.6 4.4L18 10l-4.4 1.6L12 16l-1.6-4.4L6 10l4.4-1.6z"/><path d="M18.2 14.5l.6 1.7 1.7.6-1.7.6-.6 1.7-.6-1.7-1.7-.6 1.7-.6z" fill="currentColor" stroke="none"/>`,
  plus: `<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>`,

  // --- 行事 ---
  birthday: `<line x1="3.5" y1="20.5" x2="20.5" y2="20.5"/><path d="M5.5 20.5v-7c0-1 .8-1.8 1.8-1.8h9.4c1 0 1.8.8 1.8 1.8v7"/><path d="M5.5 15c1.3 1.3 2.8 1.3 4 0s2.8-1.3 4 0 2.8 1.3 4 0"/><line x1="12" y1="7" x2="12" y2="11"/><path d="M12 4.5c1.2 1 1.2 2.5 0 2.5s-1.2-1.5 0-2.5z"/>`,
  heart: `<path d="M12 20s-7-4.6-7-9.7a3.9 3.9 0 0 1 7-2.4 3.9 3.9 0 0 1 7 2.4C19 15.4 12 20 12 20z"/>`,
  christmas: `<path d="M12 3.5l-4 6h8z"/><path d="M12 7l-5.5 8h11z"/><rect x="10.5" y="15" width="3" height="3.5"/><circle cx="12" cy="3" r="0.7" fill="currentColor" stroke="none"/>`,
  kimono: `<path d="M12 4 9 5.8 8.3 20h7.4L15 5.8z"/><path d="M12 4 9 5.8M12 4l3 1.8"/><path d="M9 6 5.5 8.5 6.8 14.5M15 6l3.5 2.5-1.3 6"/><rect x="8.3" y="11.5" width="7.4" height="2.4"/><path d="M11 13.9l-1 2.5M13 13.9l1 2.5"/>`,
  flower: `<line x1="12" y1="21" x2="12" y2="12"/><path d="M7 8c0 3.5 2.2 5 5 5s5-1.5 5-5c-1.6 0-2.8.7-3.5 1.8C13 7.5 12.6 6 12 4.5 11.4 6 11 7.5 10.5 9.8 9.8 8.7 8.6 8 7 8z"/><path d="M9.5 16c1.5 0 2.5 1 2.5 2.5M14.5 16c-1.5 0-2.5 1-2.5 2.5"/>`,
  tie: `<path d="M10 4h4l-1 3h-2z"/><path d="M11 7h2l1.2 8-2.2 4-2.2-4z"/>`,
  candy: `<circle cx="12" cy="12" r="3.6"/><path d="M8.6 9.4 5.4 7.9 6.7 11.2M15.4 14.6l3.2 1.5-1.3-3.3M15.4 9.4l3.2-1.5-1.3 3.3M8.6 14.6l-3.2 1.5 1.3-3.3"/>`,
  tea: `<path d="M5 9h12v4a5 5 0 0 1-5 5h-2a5 5 0 0 1-5-5z"/><path d="M17 10h2a2 2 0 0 1 0 4h-2"/><path d="M8 6.5c0-1 1-1.2 1-2.2M11 6.5c0-1 1-1.2 1-2.2"/>`,
  graduation: `<path d="M2.5 9 12 5.2 21.5 9 12 12.8z"/><path d="M6.5 11v4c0 1.2 2.5 2.4 5.5 2.4s5.5-1.2 5.5-2.4v-4"/><line x1="21.5" y1="9" x2="21.5" y2="13"/>`,
  baby: `<circle cx="12" cy="8" r="3.2"/><path d="M6.5 20c0-3.3 2.5-5.5 5.5-5.5s5.5 2.2 5.5 5.5"/><path d="M12 4.8c1-1 2.6-.4 2 1.1"/><circle cx="10.8" cy="8" r=".5" fill="currentColor" stroke="none"/><circle cx="13.2" cy="8" r=".5" fill="currentColor" stroke="none"/>`,
  rings: `<circle cx="9.5" cy="14" r="3.8"/><circle cx="14.5" cy="14" r="3.8"/><path d="M8 9.5 9.8 7l2 2.4M12.2 9.4 14.2 7 16 9.5M9.8 7h4.4"/>`,
  house: `<path d="M4 11 12 4.5 20 11"/><path d="M6 10v9h12v-9"/><rect x="10" y="14" width="4" height="5"/>`,
  briefcase: `<rect x="3.5" y="8" width="17" height="11" rx="1.5"/><path d="M9 8V6.5C9 5.7 9.7 5 10.5 5h3c.8 0 1.5.7 1.5 1.5V8"/><line x1="3.5" y1="13" x2="20.5" y2="13"/>`,

  // --- アバター（人物） ---
  person: `<circle cx="12" cy="8" r="3.4"/><path d="M5 20c0-3.9 3.1-6.5 7-6.5s7 2.6 7 6.5"/>`,
  woman: `<circle cx="12" cy="8.6" r="3.1"/><path d="M8.9 8.6C8.1 6 9.6 4.3 12 4.3s3.9 1.7 3.1 4.3"/><path d="M6 20c0-3.6 2.7-6 6-6s6 2.4 6 6"/>`,
  man: `<circle cx="12" cy="8.6" r="3.1"/><path d="M9 6.3h6"/><path d="M6 20c0-3.6 2.7-6 6-6s6 2.4 6 6"/>`,
  elder_woman: `<circle cx="12" cy="8.6" r="3.1"/><path d="M8.9 8.6C8.1 6 9.6 4.3 12 4.3s3.9 1.7 3.1 4.3"/><circle cx="10.4" cy="8.7" r="1"/><circle cx="13.6" cy="8.7" r="1"/><path d="M11.4 8.7h1.2"/><path d="M6 20c0-3.6 2.7-6 6-6s6 2.4 6 6"/>`,
  elder_man: `<circle cx="12" cy="8.6" r="3.1"/><path d="M9 6.3h6"/><circle cx="10.4" cy="8.7" r="1"/><circle cx="13.6" cy="8.7" r="1"/><path d="M11.4 8.7h1.2"/><path d="M6 20c0-3.6 2.7-6 6-6s6 2.4 6 6"/>`,
  girl: `<circle cx="12" cy="9" r="2.9"/><circle cx="7.7" cy="9.3" r="1.4"/><circle cx="16.3" cy="9.3" r="1.4"/><path d="M7 20c0-3.2 2.3-5.4 5-5.4s5 2.2 5 5.4"/>`,
  boy: `<circle cx="12" cy="9" r="2.9"/><path d="M9.3 7 12 5.3 14.7 7"/><path d="M7 20c0-3.2 2.3-5.4 5-5.4s5 2.2 5 5.4"/>`,
  couple: `<circle cx="8.3" cy="9.5" r="2.5"/><circle cx="15.7" cy="9.5" r="2.5"/><path d="M3.8 20c0-2.9 2-4.8 4.5-4.8s4.5 1.9 4.5 4.8M11.2 20c0-2.9 2-4.8 4.5-4.8s4.5 1.9 4.5 4.8"/><path d="M12 4c.8-1 2.2-.3 1.8.8-.2.6-1.8 1.5-1.8 1.5s-1.6-.9-1.8-1.5C9.8 3.7 11.2 3 12 4z" fill="currentColor" stroke="none"/>`,
  music: `<path d="M9 18V6l9-2v12"/><circle cx="7" cy="18" r="2"/><circle cx="16" cy="16" r="2"/>`,
  book: `<path d="M12 6.5C10.5 5 8 4.5 4.5 5v13C8 17.5 10.5 18 12 19.5"/><path d="M12 6.5C13.5 5 16 4.5 19.5 5v13C16 17.5 13.5 18 12 19.5"/><line x1="12" y1="6.5" x2="12" y2="19.5"/>`,
  cake: `<line x1="3.5" y1="20.5" x2="20.5" y2="20.5"/><path d="M5.5 20.5v-7c0-1 .8-1.8 1.8-1.8h9.4c1 0 1.8.8 1.8 1.8v7"/><path d="M5.5 15c1.3 1.3 2.8 1.3 4 0s2.8-1.3 4 0 2.8 1.3 4 0"/><line x1="12" y1="7" x2="12" y2="11"/>`,
  cat: `<path d="M5 9 6 4.5l3.4 2.4a7 7 0 0 1 5.2 0L18 4.5 19 9"/><path d="M5 9.5v2a7 7 0 0 0 14 0v-2"/><circle cx="9.6" cy="12" r=".6" fill="currentColor" stroke="none"/><circle cx="14.4" cy="12" r=".6" fill="currentColor" stroke="none"/><path d="M11 14.5h2M12 14.5v1.2"/>`,
  star: `<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 17.9 6.8 19.6l1-5.8L3.5 9.7l5.9-.9z"/>`,
};

// 行事ラベル → アイコンキー
const OCCASION_ICON = {
  "誕生日":"birthday", "記念日":"heart", "母の日":"flower", "父の日":"tie",
  "敬老の日":"tea", "バレンタイン":"heart", "ホワイトデー":"candy", "クリスマス":"christmas",
  "お中元":"gift", "お歳暮":"gift", "振袖の予約":"kimono", "成人（二十歳のつどい）":"graduation",
  "幼稚園入園":"graduation", "幼稚園卒園":"graduation", "小学校入学":"graduation", "小学校卒業":"graduation",
  "中学校入学":"graduation", "中学校卒業":"graduation", "高校入学":"graduation", "高校卒業":"graduation",
  "出産祝い":"baby", "結婚祝い":"rings", "新築・引っ越し祝い":"house", "就職祝い":"briefcase",
  "入学祝い":"graduation", "卒業祝い":"graduation", "還暦祝い":"gift", "開店・開業祝い":"gift",
};

// アバター選択肢（人の登録で選ぶ）
const AVATARS = ["woman","man","elder_woman","elder_man","person","girl","boy","couple",
  "music","book","tea","flower","cake","cat","star","gift"];

function icon(key, size = 24){
  const body = SVG_ICON_PATHS[key] || SVG_ICON_PATHS.gift;
  return `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" `
    + `stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" style="display:block">${body}</svg>`;
}
