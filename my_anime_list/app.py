from flask import Flask, request, render_template, make_response, redirect
import recomendar

app = Flask(__name__)
app.debug = True

@app.get('/')
def get_index():
    return render_template('login.html')

@app.post('/')
def post_index():
    username = request.form.get('username', None)

    if username: # si me mandaron el username
        recomendar.crear_usuario(username)

        # mando al usuario a la página de recomendaciones
        res = make_response(redirect("/recomendaciones"))

        # pongo el username en una cookie para recordarlo
        res.set_cookie('username', username)
        return res

    # sino, le muestro el formulario de login
    return render_template('login.html')

@app.get('/recomendaciones')
def get_recomendaciones():
    username = request.cookies.get('username')

    anime_id = recomendar.recomendar(username)

    # pongo animes vistos con rating = 0
    for anime in anime_id:
        recomendar.insertar_interacciones(anime, username, 0)

    animes_recomendados = recomendar.datos_animes(anime_id)
    cant_valorados = len(recomendar.items_valorados(username))
    cant_vistos = len(recomendar.items_vistos(username))

    return render_template("recomendaciones.html", animes_recomendados=animes_recomendados, username=username, cant_valorados=cant_valorados, cant_vistos=cant_vistos)

@app.get('/recomendaciones/<string:anime>')
def get_recomendaciones_libro(anime):
    username = request.cookies.get('username')

    anime_id = recomendar.recomendar_contexto(username, anime)

    # pongo animes vistos con rating = 0
    for anime in anime_id:
        recomendar.insertar_interacciones(anime, username, 0)

    animes_recomendados = recomendar.datos_animes(anime_id)
    cant_valorados = len(recomendar.items_valorados(username))
    cant_vistos = len(recomendar.items_vistos(username))

    animes = recomendar.obtener_anime(anime)

    return render_template("recomendaciones_animes.html", animes=animes, animes_recomendados=animes_recomendados, username=username, cant_valorados=cant_valorados, cant_vistos=cant_vistos)


@app.post('/recomendaciones')
def post_recomendaciones():
    username = request.cookies.get('username')

    # inserto los ratings enviados como interacciones
    for id in request.form.keys():
        rating = int(request.form[id])
        if rating > 0: # 0 es que no puntuó
            recomendar.insertar_interacciones(id, username, rating)

    return make_response(redirect("/recomendaciones"))

@app.get('/reset')
def get_reset():
    username = request.cookies.get('username')
    recomendar.reset_usuario(username)

    return make_response(redirect("/recomendaciones"))

if __name__ == '__main__':
    app.run()


