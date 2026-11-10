-- 在 Supabase 後台 → SQL Editor 貼上並執行一次即可
create table if not exists clothing (
  id bigint generated always as identity primary key,
  name text, category text, color text,
  styles text, seasons text, notes text,
  favorite boolean default false,
  wear_count integer default 0,
  last_worn date,
  image_path text, thumb_path text,
  created_at timestamptz default now()
);
create table if not exists outfits (
  id bigint generated always as identity primary key,
  name text, item_ids text, note text,
  created_at timestamptz default now()
);
create table if not exists wear_log (
  id bigint generated always as identity primary key,
  worn_on date, item_ids text
);

-- 圖片儲存桶（私有）
insert into storage.buckets (id, name, public)
values ('wardrobe', 'wardrobe', false)
on conflict (id) do nothing;
