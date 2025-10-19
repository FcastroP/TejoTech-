import os
import cv2
import numpy as np
from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename

# ✅ Crear solo una instancia de Flask
app = Flask(__name__)

# 📁 Configuración de uploads
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ⚙️ Escala y ranking
PIXELS_PER_CM = 10.0
ranking = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def detectar_color(frame, lower, upper):
    mask = cv2.inRange(frame, lower, upper)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        if area > 100:
            M = cv2.moments(largest)
            if M["m00"] > 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                return (cx, cy)
    return None

def procesar_imagen(path):
    img = cv2.imread(path)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Rangos HSV
    lower_red1, upper_red1 = np.array([0, 120, 70]), np.array([10, 255, 255])
    lower_red2, upper_red2 = np.array([170, 120, 70]), np.array([180, 255, 255])
    lower_blue, upper_blue = np.array([100, 150, 0]), np.array([140, 255, 255])
    lower_green, upper_green = np.array([40, 70, 70]), np.array([80, 255, 255])

    red_pos = detectar_color(hsv, lower_red1, upper_red1) or detectar_color(hsv, lower_red2, upper_red2)
    blue_pos = detectar_color(hsv, lower_blue, upper_blue)
    green_pos = detectar_color(hsv, lower_green, upper_green)

    if red_pos: cv2.circle(img, red_pos, 10, (0, 0, 255), -1)
    if blue_pos: cv2.circle(img, blue_pos, 10, (255, 0, 0), -1)
    if green_pos: cv2.circle(img, green_pos, 10, (0, 255, 0), -1)

    resultado = {"Rojo": red_pos, "Azul": blue_pos, "Meta": green_pos}
    ganador = None
    dist_red_cm = dist_blue_cm = None

    if red_pos and blue_pos and green_pos:
        dist_red = np.linalg.norm(np.array(red_pos) - np.array(green_pos))
        dist_blue = np.linalg.norm(np.array(blue_pos) - np.array(green_pos))
        dist_red_cm = dist_red / PIXELS_PER_CM
        dist_blue_cm = dist_blue / PIXELS_PER_CM
        ganador = "Rojo" if dist_red < dist_blue else "Azul"

    output_path = os.path.join(UPLOAD_FOLDER, "resultado.jpg")
    cv2.imwrite(output_path, img)
    return resultado, ganador, "uploads/resultado.jpg", dist_red_cm, dist_blue_cm


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        jugador = request.form["jugador"]
        apuesta = request.form["apuesta"]
        foto_jugador = request.files.get("file.player")
        jugador_filename = None

        if foto_jugador and allowed_file(foto_jugador.filename):
            jugador_filename = secure_filename(f"{jugador}_foto." + foto_jugador.filename.rsplit(".", 1)[1])
            jugador_path = os.path.join(app.config["UPLOAD_FOLDER"], jugador_filename)
            foto_jugador.save(jugador_path)

        if jugador not in ranking:
            ranking[jugador] = {"apuesta": apuesta, "ganadas": 0, "perdidas": 0, "foto": jugador_filename}
        else:
            ranking[jugador]["apuesta"] = apuesta
            if jugador_filename:
                ranking[jugador]["foto"] = jugador_filename

        file = request.files["file"]
        if file.filename == "" or not allowed_file(file.filename):
            return redirect(request.url)

        filename = secure_filename(file.filename)
        path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(path)

        return redirect(url_for("resultado", filename=filename, jugador=jugador))

    return render_template("index.html", ranking=ranking)


@app.route("/resultado/<filename>/<jugador>")
def resultado(filename, jugador):
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    resultado, ganador, imagen, dist_red, dist_blue = procesar_imagen(path)

    if ganador and jugador in ranking:
        if ranking[jugador]["apuesta"] == ganador:
            ranking[jugador]["ganadas"] += 1
        else:
            ranking[jugador]["perdidas"] += 1

    return render_template("result.html", resultado=resultado, ganador=ganador,
                           ranking=ranking, imagen=imagen, dist_red=dist_red, dist_blue=dist_blue)


# ✅ Render usa el puerto de entorno
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
