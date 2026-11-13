# EcoRuta

EcoRuta es un planificador de salida al campus para estudiantes de Tecsup. Recomienda a qué hora salir, estima la hora de llegada y muestra cuántos minutos quedarían antes de que empiece la primera clase.

## Usar EcoRuta en línea

Abre [EcoRuta en GitHub Pages](https://frank-0409.github.io/ecoruta-mvp/). El acceso es público y funciona sin iniciar sesión.

## Ejecutar en tu computadora

Con Git y Python 3 instalados, ejecuta estos comandos:

```bash
git clone https://github.com/FRANK-0409/ecoruta-mvp.git
cd ecoruta-mvp
python3 -m http.server 8000 --bind 127.0.0.1
```

Si ya tienes el repositorio clonado, entra en su carpeta y ejecuta solo el comando de Python. Abre [EcoRuta en tu navegador](http://127.0.0.1:8000/). Para detener el servidor, pulsa `Ctrl + C` en la terminal.

## Ejemplo de uso

1. Ingresa `08:00` como hora de inicio de clase.
2. Ingresa `40` como duración habitual del viaje en minutos.
3. Ingresa `07:15` como la hora más temprana a la que puedes salir. Este campo es opcional.
4. Pulsa **Continuar al cálculo**.

EcoRuta recomienda salir a las **07:10** para tener 10 minutos de margen. Si sales a las **07:15**, estima que llegarás a las **07:55** y muestra un **margen reducido de 5 minutos**.
