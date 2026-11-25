// スマホ用ページの設定。ここに書く値はすべて公開してよいもの（秘密キーは絶対に書かない）
window.MYCOVER = {
  supabaseUrl: "https://hasykewktdnsqgrnzgij.supabase.co",
  publishableKey: "sb_publishable_tV56DfmPw7fX5CfcCKNEyA_1yI9Dxwm", // 公開キー（RLS で保護）
  track: {
    title: "B7F",
    artist: "Usagi Ikeda",
    mp3: "B7F.mp3", // TODO: 楽曲MP3をこのページと同じ場所に B7F.mp3 という名前で置く
  },
  jacketDigits: 4,
  cardDigits: 4,
  // 特設エリア（M3）。公開日を過ぎると自動で切り替わる。展示PCの config/config.json の release と同じ日付にする
  release: {
    officialJacketAt: null, // TODO: 公式ジャケット公開日時（例 "2026-12-20T00:00:00+09:00"）。null のあいだは「近日公開」
    mvAt: null, // TODO: MV 公開日時
    officialJacketImage: "official.jpg", // 公式ジャケット画像（このページと同じ場所に置く）
    mvUrl: "", // TODO: MV の YouTube の URL
  },
  authorUrl: "", // TODO: 『My Cover』・作者HP の URL（空のあいだはリンクを出さない）
  exhibition: [
    "デザイン情報学科３年ゼミ展",
    "2026.12.3-12.5 / 9:00~18:00（最終日 ~16:30）",
    "武蔵野美術大学 鷹の台キャンパス９号館地下",
    "『My Cover』池田うさぎ（大石ゼミ）",
  ],
};
