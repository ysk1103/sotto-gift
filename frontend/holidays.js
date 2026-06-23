// 日本の祝日（ルールベース・1980〜2099想定）。getHolidays(year) -> {"M-D": 祝日名}
// 春分/秋分は近似式、振替休日・国民の休日も対応。六曜は別途（旧暦が必要）。

const _holidayCache = {};

function _nthMonday(y, m, n){
  const d = new Date(y, m - 1, 1);
  const off = (8 - d.getDay()) % 7;          // 最初の月曜まで（日=0…月=1）
  return 1 + off + 7 * (n - 1);
}

function getHolidays(year){
  if (_holidayCache[year]) return _holidayCache[year];
  const base = [];
  const add = (m, d, name) => base.push([m, d, name]);

  add(1, 1, "元日");
  add(1, _nthMonday(year, 1, 2), "成人の日");
  add(2, 11, "建国記念の日");
  if (year >= 2020) add(2, 23, "天皇誕生日");
  add(3, Math.floor(20.8431 + 0.242194 * (year - 1980) - Math.floor((year - 1980) / 4)), "春分の日");
  add(4, 29, "昭和の日");
  add(5, 3, "憲法記念日");
  add(5, 4, "みどりの日");
  add(5, 5, "こどもの日");
  add(7, _nthMonday(year, 7, 3), "海の日");
  add(8, 11, "山の日");
  add(9, _nthMonday(year, 9, 3), "敬老の日");
  add(9, Math.floor(23.2488 + 0.242194 * (year - 1980) - Math.floor((year - 1980) / 4)), "秋分の日");
  add(10, _nthMonday(year, 10, 2), "スポーツの日");
  add(11, 3, "文化の日");
  add(11, 23, "勤労感謝の日");

  // 日付キー(ms)ベースに
  const byT = {};
  base.forEach(([m, d, name]) => { byT[new Date(year, m - 1, d).getTime()] = name; });

  // 振替休日：祝日が日曜なら、次の祝日でない日を休みに
  base.forEach(([m, d]) => {
    const dt = new Date(year, m - 1, d);
    if (dt.getDay() === 0){
      const n = new Date(dt);
      do { n.setDate(n.getDate() + 1); } while (byT[n.getTime()]);
      byT[n.getTime()] = "振替休日";
    }
  });

  // 国民の休日：祝日に挟まれた平日（日曜以外）
  for (let m = 0; m < 12; m++){
    const dim = new Date(year, m + 1, 0).getDate();
    for (let d = 1; d <= dim; d++){
      const t = new Date(year, m, d).getTime();
      if (byT[t]) continue;
      const wd = new Date(year, m, d).getDay();
      const prev = new Date(year, m, d - 1).getTime();
      const next = new Date(year, m, d + 1).getTime();
      if (wd !== 0 && byT[prev] && byT[next]) byT[t] = "国民の休日";
    }
  }

  const out = {};
  Object.keys(byT).forEach(t => {
    const dt = new Date(Number(t));
    out[`${dt.getMonth() + 1}-${dt.getDate()}`] = byT[t];
  });
  _holidayCache[year] = out;
  return out;
}
