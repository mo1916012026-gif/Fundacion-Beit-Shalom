/* Solo para quien YA ejecutó una versión anterior de 02_usuario_aplicacion.sql con el
   usuario beitshalom_app: agrega los permisos de editar y eliminar colaboradores.
   Si la aplicación se conecta con Windows (DB_TRUSTED=1) no hace falta ejecutarlo. */
USE BeitShalomDB;
GO
GRANT UPDATE, DELETE ON Colaboradores TO beitshalom_app;
GRANT DELETE ON ColaboradorAreas TO beitshalom_app;
GO
