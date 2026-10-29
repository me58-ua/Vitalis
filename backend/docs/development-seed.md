# Cuentas de desarrollo

El seeder `app/scripts/seed_users.py` crea tres cuentas sintéticas para desarrollo local:

| Rol | Usuario | Correo | Contraseña de desarrollo |
| --- | --- | --- | --- |
| Administrador | `admin` | `admin@vitalis.local` | `Admin123!` |
| Profesional | `professional_one` | `professional1@vitalis.local` | `Professional123!` |
| Paciente | `patient_one` | `patient1@vitalis.local` | `Patient123!` |

Las tres cuentas están activas. El profesional tiene un perfil aprobado y revisado por el administrador del seed, con especialidad, colegiación sintética, consulta y opciones de teleconsulta. Este estado es exclusivo de las cuentas de desarrollo; no cambia el flujo de aprobación del registro público.

El paciente tiene su cuenta y un `PatientProfile` con fecha de nacimiento, sexo al nacer, altura de 165 cm, peso de 62 kg, dirección sintética, grupo sanguíneo y zona horaria `Europe/Madrid`. El onboarding está sin completar, los consentimientos de IA y de compartir datos están desactivados y no hay antecedentes revisados. No se crean alergias, enfermedades, medicación, hábitos, documentos, citas, mensajes, resultados de riesgo ni ninguna otra fila clínica o relación profesional-paciente.

## Ejecutar

Desde `backend/`, con la API y la base de desarrollo en ejecución y las migraciones aplicadas:

```powershell
docker compose exec api python -m app.scripts.seed_users
```


## Probar el acceso

Abrir el frontend en `http://localhost:3000`, pulsar «Iniciar sesión» y utilizar una de las cuentas anteriores. Se puede entrar por correo o por nombre de usuario. Paciente y profesional navegan a sus paneles provisionales; administrador vuelve a la portada. `GET /patients/me/profile`, autenticado como paciente, devuelve el perfil del seed.

Las credenciales son públicas y sintéticas; este seeder no está destinado a producción.
