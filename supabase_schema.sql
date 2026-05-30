-- ==========================================
-- ESQUEMA PARA NUEVO PROYECTO SUPABASE
-- GA ERP - Suscripciones Dinámicas
-- ==========================================

-- 1. Tabla de Planes (Precios Dinámicos)
CREATE TABLE IF NOT EXISTS public.planes_suscripcion (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    precio NUMERIC(10, 2) NOT NULL,
    dias INTEGER NOT NULL,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insertar planes por defecto (Podés modificarlos después desde el Dashboard de Supabase)
INSERT INTO public.planes_suscripcion (id, nombre, descripcion, precio, dias, activo) VALUES
('1_mes', 'Mensual', 'Acceso completo por 1 mes', 35000, 30, TRUE),
('6_meses', 'Semestral', 'Acceso completo por 6 meses (15% descuento)', 180000, 180, TRUE),
('1_anio', 'Anual', 'Acceso completo por 1 año (30% descuento)', 300000, 365, TRUE)
ON CONFLICT (id) DO NOTHING;

-- 2. Tabla de Suscripciones (Control de pagos)
CREATE TABLE IF NOT EXISTS public.suscripciones (
    id BIGSERIAL PRIMARY KEY,
    client_id TEXT NOT NULL,
    plan_id TEXT REFERENCES public.planes_suscripcion(id),
    fecha_inicio TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    fecha_expiracion TIMESTAMP WITH TIME ZONE,
    estado TEXT DEFAULT 'pendiente', -- 'activa', 'vencida', 'pendiente', 'cancelada'
    mercadopago_payment_id TEXT,
    mercadopago_preference_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Tabla de Códigos de Descuento (Opcional)
CREATE TABLE IF NOT EXISTS public.codigos_descuento (
    id BIGSERIAL PRIMARY KEY,
    codigo TEXT UNIQUE NOT NULL,
    porcentaje_descuento NUMERIC(5, 2) DEFAULT 0,
    activo BOOLEAN DEFAULT TRUE,
    usos_maximos INTEGER DEFAULT 1,
    usos_actuales INTEGER DEFAULT 0,
    fecha_expiracion TIMESTAMP WITH TIME ZONE
);

-- ==========================================
-- CONFIGURACIÓN DE SEGURIDAD (RLS)
-- ==========================================

-- Habilitar Row Level Security (Opcional para este caso, pero buena práctica)
ALTER TABLE public.planes_suscripcion ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.suscripciones ENABLE ROW LEVEL SECURITY;

-- Política para que el backend (Service Role Key) pueda leer/escribir todo
-- (Vercel usa la Service Role Key, así que necesita acceso total)
CREATE POLICY "Allow all operations for service role" ON public.planes_suscripcion FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all operations for service role" ON public.suscripciones FOR ALL USING (true) WITH CHECK (true);

-- ==========================================
-- NOTA PARA VOS:
-- 1. Andá a tu NUEVO proyecto de Supabase.
-- 2. Andá a "SQL Editor" en el menú izquierdo.
-- 3. Pegá este contenido y dasle a "Run".
-- 4. Luego andá a "Project Settings" > "API" y copiá la URL y el Service Role Key para tu backend/.env y Vercel.
-- ==========================================
