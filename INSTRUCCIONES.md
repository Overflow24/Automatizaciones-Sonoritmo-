# Cómo probar OrderFlow en tu computadora

Esta carpeta tiene 3 archivos:
- `database.py` — define la base de datos
- `app.py` — el backend (las 7 puertas que construimos)
- `OrderFlow.html` — tu app, ya conectada al backend

## Requisito previo: tener Python instalado

Si no sabes si ya lo tienes, abre una terminal (en Windows: busca "cmd" o
"PowerShell"; en Mac: busca "Terminal") y escribe:

```
python3 --version
```

Si te marca un número de versión (por ejemplo "Python 3.11.2"), ya lo tienes.
Si te marca error, descárgalo de https://www.python.org/downloads/ — durante
la instalación en Windows, asegúrate de marcar la casilla "Add Python to PATH".

## Paso 1 — Instalar Flask

Flask es la única pieza extra que necesitas instalar. En la terminal:

```
pip install flask
```

Si eso da error, prueba con:

```
pip3 install flask
```

## Paso 2 — Prender el backend

1. Abre la terminal
2. Navega a la carpeta donde guardaste estos 3 archivos. Por ejemplo, si los
   guardaste en Descargas/orderflow-proyecto, escribe:
   ```
   cd Descargas/orderflow-proyecto
   ```
3. Arranca el backend:
   ```
   python3 app.py
   ```
4. Deberías ver un mensaje que dice algo como:
   ```
   Base de datos lista en: .../orderflow.db
   * Running on http://127.0.0.1:5000
   ```
5. Deja esa ventana de terminal abierta — si la cierras, el backend se apaga.

## Paso 3 — Abrir la app

Con el backend prendido (la terminal del paso anterior sigue abierta),
ve a la carpeta y haz doble clic en `OrderFlow.html`. Se va a abrir en tu
navegador y ahora sí va a estar conectado de verdad a una base de datos
que vive en tu computadora — los datos ya no se pierden al cerrar la
pestaña.

## Cómo saber si algo no está conectando

Si abres OrderFlow.html y ves un mensaje de advertencia que dice
"No se pudo conectar con el servidor", significa que el backend (Paso 2)
no está corriendo o se cerró. Vuelve a hacer el Paso 2 y refresca la
página del navegador.

## Para apagar todo

En la terminal donde corre el backend, presiona Ctrl + C.

## Próximo paso

Este archivo `orderflow.db` que se generó es tu base de datos real, viviendo
en tu computadora. El siguiente paso para que tu equipo (no solo tú) pueda
usarlo es el despliegue: mover estas mismas piezas a un servidor en internet
prendido todo el tiempo, para que cada persona entre desde su propia
computadora con un link, sin necesitar tener Python instalado ni nada de esto.
