import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// ⚠️ Estos valores los cargás como secrets en Supabase Dashboard
const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const MP_ACCESS_TOKEN = Deno.env.get("MP_ACCESS_TOKEN")!; // Tu token de MP

// Crear cliente de Supabase
const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);

serve(async (req) => {
  // Solo aceptamos POST
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  try {
    const body = await req.json();
    console.log("Webhook recibido:", JSON.stringify(body));

    // MP manda varios tipos de notificaciones, solo nos importa "payment"
    if (body.type !== "payment") {
      return new Response("OK - ignorado", { status: 200 });
    }

    const paymentId = body.data?.id;
    if (!paymentId) {
      return new Response("Sin payment ID", { status: 400 });
    }

    // Consultamos el pago real a la API de MP para verificarlo
    const mpRes = await fetch(
      `https://api.mercadopago.com/v1/payments/${paymentId}`,
      { headers: { Authorization: `Bearer ${MP_ACCESS_TOKEN}` } }
    );
    const pago = await mpRes.json();
    console.log("Pago de MP:", JSON.stringify(pago));

    // Solo procesamos pagos aprobados
    if (pago.status !== "approved") {
      return new Response("Pago no aprobado, ignorado", { status: 200 });
    }

    const email = pago.payer?.email;
    const externalReference = pago.external_reference; // Formato: "usuarioId_planId"
    
    if (!email || !externalReference) {
      return new Response("Faltan datos del pago", { status: 400 });
    }

    // Parsear external_reference: "usuarioId_planId"
    const parts = externalReference.split("_");
    if (parts.length < 2) {
      return new Response("Formato de external_reference inválido", { status: 400 });
    }

    const clientId = parts[0]; // usuarioId
    const planId = parts[1]; // planId (mensual, semestral, anual)

    // Calcular fecha_fin según el plan
    const now = new Date();
    let fechaFin: Date;
    
    switch (planId) {
      case "mensual":
        fechaFin = new Date(now.setMonth(now.getMonth() + 1));
        break;
      case "semestral":
        fechaFin = new Date(now.setMonth(now.getMonth() + 6));
        break;
      case "anual":
        fechaFin = new Date(now.setFullYear(now.getFullYear() + 1));
        break;
      default:
        return new Response("Plan inválido", { status: 400 });
    }

    // Guardamos/actualizamos la licencia en Supabase
    const { error } = await supabase
      .from("licencias")
      .upsert(
        {
          client_id: clientId,
          email: email,
          plan_tipo: planId,
          estado: "activa",
          fecha_inicio: new Date().toISOString(),
          fecha_fin: fechaFin.toISOString(),
          mp_payment_id: String(paymentId),
          actualizado_at: new Date().toISOString(),
        },
        { onConflict: "client_id" } // Si ya existe ese client_id, actualiza
      );

    if (error) {
      console.error("Error Supabase:", error);
      return new Response("Error interno", { status: 500 });
    }

    console.log(`✅ Licencia activada: ${email} → ${planId}`);
    return new Response("OK", { status: 200 });
    
  } catch (error) {
    console.error("Error procesando webhook:", error);
    return new Response("Error interno", { status: 500 });
  }
});
