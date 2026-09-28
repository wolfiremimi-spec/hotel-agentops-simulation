-- Hotel AgentOps: database setup. Paste into Supabase → SQL Editor → New query → Run. Safe to run more than once.
-- Row Level Security is ON with no policies, so the public (anon/publishable) key can read or write nothing.
-- Only the app's server, holding the secret key in Streamlit secrets, can reach these tables.

create extension if not exists pgcrypto;

create table if not exists public.hotels (
    id           uuid primary key default gen_random_uuid(),
    name         text not null,
    access_hash  text not null unique,
    profile      jsonb not null default '{}'::jsonb,
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);

create table if not exists public.service_days (
    id            uuid primary key default gen_random_uuid(),
    hotel_id      uuid not null references public.hotels(id) on delete cascade,
    service_date  date not null,
    status        text not null default 'draft',
    inputs        jsonb,
    run           jsonb,
    closeout      jsonb,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now(),
    unique (hotel_id, service_date)
);

create table if not exists public.audit_events (
    id        bigint generated always as identity primary key,
    hotel_id  uuid not null references public.hotels(id) on delete cascade,
    at        timestamptz not null default now(),
    actor     text not null,
    action    text not null,
    detail    jsonb not null default '{}'::jsonb
);

create index if not exists service_days_hotel_date on public.service_days (hotel_id, service_date desc);
create index if not exists audit_events_hotel_at on public.audit_events (hotel_id, at desc);

alter table public.hotels       enable row level security;
alter table public.service_days enable row level security;
alter table public.audit_events enable row level security;

-- The audit log is append-only: no edits, and no deletes except when a whole hotel workspace is removed.
create or replace function public.audit_events_append_only() returns trigger language plpgsql as $$
begin
    if tg_op = 'DELETE' and pg_trigger_depth() > 1 then
        return old;                      -- cascaded from deleting the hotel
    end if;
    raise exception 'audit_events is append-only';
end $$;
drop trigger if exists audit_events_no_change on public.audit_events;
create trigger audit_events_no_change before update or delete on public.audit_events
    for each row execute function public.audit_events_append_only();

-- Explicit privileges, so this works whether or not "Automatically expose new tables" was ticked.
-- The public roles get nothing; only the server's secret key (service_role) can use these tables.
revoke all on public.hotels, public.service_days, public.audit_events from anon, authenticated;
grant usage on schema public to service_role;
grant select, insert, update, delete on public.hotels, public.service_days to service_role;
grant select, insert on public.audit_events to service_role;
