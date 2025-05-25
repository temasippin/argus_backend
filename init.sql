-- Таблица зон доступа
CREATE TABLE IF NOT EXISTS public.zone
(
    zone_id uuid NOT NULL DEFAULT gen_random_uuid(),
    name VARCHAR(64) NOT NULL UNIQUE,         -- Идентификатор зоны (A/B/C...)
    description TEXT,                         -- Описание зоны
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP,
    CONSTRAINT zone_pkey PRIMARY KEY (zone_id)
);

-- Таблица глобальных настроек системы
CREATE TABLE IF NOT EXISTS public.openvpn
(
    openvpn_id uuid NOT NULL DEFAULT gen_random_uuid(),
    vpn_enabled BOOLEAN DEFAULT FALSE,        -- Активен ли VPN
    vpn_config JSONB,                         -- {server: "vpn.example.com", port: 1194, ...}
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP,
    CONSTRAINT configuration_pkey PRIMARY KEY (openvpn_id)
);

-- Основная таблица пользователей
CREATE TABLE IF NOT EXISTS public.user
(
    user_id uuid NOT NULL DEFAULT gen_random_uuid(),
    login VARCHAR(320) NOT NULL UNIQUE,
    password VARCHAR(128) NOT NULL,
    full_name VARCHAR(128),
    phone VARCHAR(20),
    access_level INTEGER CHECK (access_level >= 0 AND access_level <= 4),
    employee_id VARCHAR(32),
    department VARCHAR(64),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP,
    CONSTRAINT user_pkey PRIMARY KEY (user_id)
);

-- Устройства контроля доступа (добавлена связь с зонами)
CREATE TABLE IF NOT EXISTS public.device
(
    device_id uuid NOT NULL DEFAULT gen_random_uuid(),
    name VARCHAR(128) NOT NULL,
    ip INET NOT NULL,
    port INTEGER CHECK (port > 0 AND port <= 65535),
    zone_id uuid NOT NULL,
    location_description VARCHAR(256),
    is_online BOOLEAN DEFAULT FALSE,
    last_heartbeat TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP,
    CONSTRAINT device_pkey PRIMARY KEY (device_id),
    CONSTRAINT fk_zone FOREIGN KEY (zone_id) 
        REFERENCES public.zone(zone_id) ON DELETE CASCADE
);

-- Биометрические данные (исправлены ссылки)
CREATE TABLE IF NOT EXISTS public.biometry
(
    biometry_id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    encrypted_embedding BYTEA NOT NULL,
    iv BYTEA NOT NULL,
    secure_hash BYTEA NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    CONSTRAINT biometry_pkey PRIMARY KEY (biometry_id),
    CONSTRAINT fk_user FOREIGN KEY (user_id) 
        REFERENCES public.user(user_id) ON DELETE CASCADE
);

-- Права доступа
CREATE TABLE IF NOT EXISTS public.permission
(
    permission_id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    target_type VARCHAR(8) NOT NULL CHECK (target_type IN ('DEVICE', 'ZONE')),
    target_id uuid NOT NULL,                  -- device_id ИЛИ zone_id
    assigned_by uuid,
    valid_from TIMESTAMP DEFAULT now(),
    valid_to TIMESTAMP,
    schedule JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP,
    CONSTRAINT permission_pkey PRIMARY KEY (permission_id),
    CONSTRAINT fk_user FOREIGN KEY (user_id) 
        REFERENCES public.user(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_assigner FOREIGN KEY (assigned_by) 
        REFERENCES public.user(user_id)
);

-- Журнал событий
CREATE TABLE IF NOT EXISTS public.access_log
(
    access_log_id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid,
    device_id uuid NOT NULL,
    biometry_id uuid,
    event_type VARCHAR(32) NOT NULL,
    confidence FLOAT,
    path_to_photo VARCHAR(128),
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    CONSTRAINT access_log_pkey PRIMARY KEY (access_log_id),
    CONSTRAINT fk_user FOREIGN KEY (user_id) 
        REFERENCES public.user(user_id) ON DELETE SET NULL,
    CONSTRAINT fk_device FOREIGN KEY (device_id) 
        REFERENCES public.device(device_id),
    CONSTRAINT fk_biometry FOREIGN KEY (biometry_id) 
        REFERENCES public.biometry(biometry_id)
);
ALTER TABLE public.access_log ADD COLUMN access_granted BOOLEAN DEFAULT FALSE;


-- Системный журнал
CREATE TABLE IF NOT EXISTS public.audit_log
(
    audit_log_id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    action VARCHAR(32) NOT NULL,
    entity_type VARCHAR(32) NOT NULL,
    entity_id uuid,
    action_data JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    CONSTRAINT audit_log_pkey PRIMARY KEY (audit_log_id),
    CONSTRAINT fk_user FOREIGN KEY (user_id) 
        REFERENCES public.user(user_id)
);

-- Индексы (оптимизированы)
CREATE INDEX idx_biometry_user ON public.biometry(user_id);
CREATE INDEX idx_device_zone ON public.device(zone_id);
CREATE INDEX idx_permission_target ON public.permission(target_type, target_id);
CREATE INDEX idx_access_log_device_time ON public.access_log(device_id, created_at);