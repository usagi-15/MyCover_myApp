-- 『My Cover』Supabase のテーブル・RLS・関数・ストレージ
-- Supabase ダッシュボードの「SQL Editor」に全文を貼り付けて Run する。何度実行しても壊れないように書いている。
--
-- 方針（実装指示書 10章）
--   - 展示PC：service_role（secret）キーで書き込む。service_role は RLS の対象外
--   - スマホ用ページ：anon（publishable）キーを埋め込む。下の権限と RLS で許可した操作しかできない
--   - 研究用の詳細データ（作り直し回数・各回の入力など）はここに置かず、展示PCのローカル SQLite に残す

-- ---------------------------------------------------------------- テーブル
create table if not exists public.covers (
  jacket_no    integer     primary key,
  token        text        not null unique,          -- Get It Now 用 URL の ?t=
  image_url    text        not null,                 -- Storage の公開URL
  prompt       text        not null,                 -- 確定版の入力文
  confirmed_at timestamptz not null default now(),
  hidden       boolean     not null default false    -- ギャラリーから非表示
);

create table if not exists public.cards (
  card_no    integer     primary key,
  card_token text        not null unique,            -- カード URL の ?c=（事前に一括発行）
  jacket_no  integer     references public.covers (jacket_no),  -- ひも付け前は null
  linked_at  timestamptz
);

create table if not exists public.page_views (
  id         bigint      generated always as identity primary key,
  kind       text        not null check (kind in ('get_it_now', 'card')),
  token      text        check (char_length(token) <= 64),
  card_token text        check (char_length(card_token) <= 64),
  viewed_at  timestamptz not null default now(),
  check (
    (kind = 'get_it_now' and token is not null and card_token is null) or
    (kind = 'card' and card_token is not null and token is null)
  )
);
-- IP アドレスなど個人を特定する情報は記録しない

-- ---------------------------------------------------------------- 権限と RLS
alter table public.covers     enable row level security;
alter table public.cards      enable row level security;
alter table public.page_views enable row level security;

revoke all on public.covers, public.cards, public.page_views from anon, authenticated;

-- covers：anon は hidden=false の行の公開用カラムだけ読める
grant select (jacket_no, image_url, prompt, confirmed_at) on public.covers to anon;
drop policy if exists covers_public_read on public.covers;
create policy covers_public_read on public.covers
  for select to anon using (hidden = false);

-- cards：anon にはテーブルを直接読ませない（一覧取得の防止）。下の関数 get_card だけを使う

-- page_views：anon は書き込み（insert）のみ。読み取りは不可
grant insert (kind, token, card_token) on public.page_views to anon;
drop policy if exists page_views_insert on public.page_views;
create policy page_views_insert on public.page_views
  for insert to anon with check (true);

-- ---------------------------------------------------------------- スマホ用ページが呼ぶ関数（RPC）
-- ?t=<token> → ジャケット1件（見つからない・非表示なら0件）
create or replace function public.get_cover_by_token(p_token text)
returns table (jacket_no integer, image_url text, prompt text, confirmed_at timestamptz)
language sql stable security definer set search_path = public
as $$
  select c.jacket_no, c.image_url, c.prompt, c.confirmed_at
  from public.covers c
  where c.token = p_token and c.hidden = false;
$$;

-- ?c=<card_token> → カード1件。ひも付け前なら linked=false でジャケット情報は null
create or replace function public.get_card(p_card_token text)
returns table (card_no integer, linked boolean, jacket_no integer, image_url text, prompt text, confirmed_at timestamptz)
language sql stable security definer set search_path = public
as $$
  select k.card_no, (c.jacket_no is not null), c.jacket_no, c.image_url, c.prompt, c.confirmed_at
  from public.cards k
  left join public.covers c on c.jacket_no = k.jacket_no and c.hidden = false
  where k.card_token = p_card_token;
$$;

revoke all on function public.get_cover_by_token(text) from public;
revoke all on function public.get_card(text) from public;
grant execute on function public.get_cover_by_token(text) to anon;
grant execute on function public.get_card(text) to anon;

-- ---------------------------------------------------------------- ストレージ
-- バケット covers：公開読み取り（<img> でそのまま表示するため）。書き込みは service_role のみ
-- （anon 向けの書き込みポリシーは作らない）
insert into storage.buckets (id, name, public)
values ('covers', 'covers', true)
on conflict (id) do update set public = true;
