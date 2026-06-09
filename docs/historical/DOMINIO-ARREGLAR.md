# Arreglar dominio bago.dev — Instrucciones urgentes

## Problema
El dominio `bago.dev` está asignado al proyecto Vercel `landing`, pero **no resuelve correctamente**.

- DNS actual: nameservers de GoDaddy (`ns07.domaincontrol.com`, `ns08.domaincontrol.com`)
- DNS necesario: nameservers de Vercel (`ns1.vercel-dns.com`, `ns2.vercel-dns.com`)
- O alternativa: registro A → `76.76.21.21`

## Por qué no puedo arreglarlo automáticamente
1. La API de Vercel no permite cambiar nameservers de dominios "externos" (registrados fuera de Vercel).
2. El dominio no aparece en tu cuenta de GoDaddy, así que no puedo acceder al panel DNS.
3. Vercel detecta el dominio como `serviceType: external`.

## Solución (debes hacerlo tú en 2 minutos)

### Opción A: Cambiar nameservers desde Vercel Dashboard (recomendada)
1. Ve a https://vercel.com/dashboard/domains
2. Busca `bago.dev` en la lista.
3. Haz clic en `bago.dev`.
4. Busca una sección llamada **"Nameservers"** o **"DNS"**.
5. Selecciona la opción **"Use Vercel Nameservers"** (o similar).
6. Guarda. La propagación tarda 5-30 minutos.

### Opción B: Añadir registro A en tu registrador real
Si Vercel no te da opción de cambiar nameservers, necesitas encontrar dónde está realmente registrado el dominio.
1. Busca en tu email bandeja de entrada (y spam) por:
   - "bago.dev"
   - "domain registration"
   - "GoDaddy order"
   - "Vercel domain"
2. El email de confirmación de compra te dirá el registrador real y el panel de control.
3. Accede a ese panel y añade un registro **A**:
   - Host: `@` (o `bago.dev`)
   - Valor: `76.76.21.21`
   - TTL: 60 (o lo más bajo posible)
4. Guarda. La propagación tarda 5-30 minutos.

### Opción C: Transferir el dominio a Vercel
1. En Vercel dashboard → Domains → `bago.dev`.
2. Busca **"Transfer to Vercel"**.
3. Necesitarás el "Auth Code" (EPP) del registrador actual. Solicítalo por email.
4. Completa la transferencia en Vercel. Después Vercel gestionará todo automáticamente.

## Verificación
Una vez hecho cualquiera de los pasos anteriores, verifica en CMD/PowerShell:
```cmd
nslookup bago.dev
```
Debe devolver algo como `76.76.21.21` (Vercel) en lugar de `15.197.148.33` (GoDaddy parking).

## Si nada funciona
Contacta a soporte de Vercel desde tu dashboard (Settings → Support) con este mensaje:
> "Mi dominio bago.dev está registrado externamente (nameservers ns07/ns08.domaincontrol.com) pero no tengo acceso al panel DNS del registrador. Necesito que me ayudéis a apuntarlo correctamente a Vercel (project landing)."

---
Documento generado por Copilot. Token Vercel usado para diagnóstico: vca_0iW86ZH...
