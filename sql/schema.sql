-- Esquema de la tabla `publicaciones` usado por database.py
-- Ejecutar en el SQL Editor de Supabase para recrear la DB desde cero.

create table if not exists publicaciones (
    id uuid primary key default gen_random_uuid(),
    url_original text not null,
    archivo_local text not null,
    cuenta text not null,
    hora_programada timestamptz not null,
    estado text not null default 'pendiente'
        check (estado in ('pendiente', 'publicado', 'error', 'cancelado')),
    ig_media_id text,
    published_at timestamptz,
    error_msg text,
    created_at timestamptz not null default now()
);

-- Acelera la consulta del scheduler (obtener_pendientes_listos):
-- WHERE estado = 'pendiente' AND hora_programada <= now() ORDER BY hora_programada
create index if not exists idx_publicaciones_pendientes
    on publicaciones (estado, hora_programada);
