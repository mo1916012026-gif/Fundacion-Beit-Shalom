/* =====================================================================
   Usuario de la aplicación con PERMISOS MÍNIMOS.
   La aplicación nunca debe conectarse como "sa".
   1) Cambia la contraseña por una real y larga.
   2) Ejecuta este script con un usuario administrador.
   3) Pon ese usuario y contraseña en el archivo .env
   ===================================================================== */
USE master;
GO
CREATE LOGIN beitshalom_app WITH PASSWORD = 'CAMBIAR_POR_UNA_CONTRASEÑA_LARGA_Y_SEGURA_1!',
    CHECK_POLICY = ON;
GO
USE BeitShalomDB;
GO
CREATE USER beitshalom_app FOR LOGIN beitshalom_app;
GO
-- Formulario público: leer áreas y registrar solicitudes
GRANT SELECT ON AreasColaboracion TO beitshalom_app;
GRANT SELECT, INSERT ON Colaboradores TO beitshalom_app;
GRANT SELECT, INSERT ON ColaboradorAreas TO beitshalom_app;
-- Panel administrativo (CRUD completo de colaboradores): editar y eliminar
GRANT UPDATE, DELETE ON Colaboradores TO beitshalom_app;
GRANT DELETE ON ColaboradorAreas TO beitshalom_app;
-- Inicio de sesión: leer administradores y actualizar el control de intentos
GRANT SELECT ON Administradores TO beitshalom_app;
GRANT UPDATE (intentos_fallidos, bloqueado_hasta, ultimo_acceso) ON Administradores TO beitshalom_app;
-- Sin acceso a otras bases ni permisos de esquema: aunque la app fuera atacada,
-- el daño posible queda limitado a las tablas de este proyecto.
GO
