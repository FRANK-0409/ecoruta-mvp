# EcoRuta

EcoRuta ayuda a los estudiantes de Tecsup a planificar su salida al campus y coordinar viajes compartidos por distrito. El planificador recomienda a qué hora salir, estima la llegada y muestra el margen antes de clase.

## Usar EcoRuta en línea

El [planificador publicado en GitHub Pages](https://frank-0409.github.io/ecoruta-mvp/) tiene acceso público. El módulo de viajes compartidos requiere el servidor de EcoRuta.

Para estimar el tiempo de viaje, elige tu sede y pulsa **Ver ruta a Tecsup en Google Maps** junto al campo de duración. Elige tu punto de partida y medio de transporte en Maps. Luego ingresa en EcoRuta los minutos que indique la ruta.

## Ejecutar en tu computadora

Con Git y Python 3 instalados, ejecuta estos comandos:

```bash
git clone https://github.com/FRANK-0409/ecoruta-mvp.git
cd ecoruta-mvp
python3 server.py
```

Si ya tienes el repositorio clonado, entra en su carpeta y ejecuta solo el comando de Python. Abre [EcoRuta en tu navegador](http://127.0.0.1:8000/). Para detener el servidor, pulsa `Ctrl + C` en la terminal. Si el puerto ya está ocupado, puedes usar `PORT=8001 python3 server.py` y abrir el puerto 8001.

## Ejemplo de uso

1. Ingresa `08:00` como hora de inicio de clase.
2. Ingresa `40` como duración habitual del viaje en minutos.
3. Ingresa `07:15` como la hora más temprana a la que puedes salir. Este campo es opcional.
4. Pulsa **Calcular mi traslado**.

EcoRuta recomienda salir a las **07:10** para tener 10 minutos de margen. Si sales a las **07:15**, estima que llegarás a las **07:55** y muestra un **margen reducido de 5 minutos**.

El último plan calculado se recupera al volver a abrir EcoRuta en el mismo navegador. Para eliminarlo, pulsa **Borrar plan**.

## Probar viajes compartidos

1. Abre **Viajes compartidos**, filtra por **Arequipa** y escribe **Paucarpata**. Pulsa **Buscar**.
2. Con el seudónimo **Jorge**, publica una búsqueda de compañía para mañana y fija la llegada a las **08:00**. Usa un punto de partida ficticio.
3. En otro perfil del navegador, abre la misma URL y busca el grupo. Únete con el seudónimo **Ana**.
4. En un tercer perfil, ofrece **2 asientos** al grupo con el seudónimo **Luis**, recojo a las **07:15**, llegada a las **07:55** y un aporte de **S/ 4** por persona.
5. Desde los perfiles de Jorge y Ana, pulsa **Buscar** para ver la oferta y solicitar un asiento. En el perfil de Luis, vuelve a pulsar **Buscar** y confirma ambas solicitudes. El viaje quedará lleno.

Para ofrecer asientos a cualquier estudiante del distrito, usa **Ofrecer asientos** en la parte superior. Unirse a un grupo indica interés. Para reservar en una oferta del grupo, solicita un asiento y espera la confirmación del conductor. El aporte se muestra en la publicación.

Las publicaciones y reservas se guardan en una base SQLite en `datos/viajes.sqlite3`. Usa el mismo navegador y perfil para administrar tus publicaciones. Para la evaluación, usa seudónimos y puntos de encuentro ficticios.

## Publicación del módulo de viajes

El servidor incluido es para pruebas. Para ofrecer la función en línea, el alojamiento debe servir la aplicación y la API bajo el mismo dominio HTTPS y conservar la base en un disco persistente. La ruta del archivo SQLite se puede indicar con `ECORUTA_DB`. GitHub Pages sirve el planificador estático.
