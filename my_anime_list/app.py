from flask import Flask, request, render_template, make_response, redirect
import recomendar

app = Flask(__name__)
app.debug = True

try:
    recomendar.init()
except Exception as e:
    print(f"⚠️ init() falló: {e}")
    
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
    genero = request.args.get('genero', '').strip()

    generos = recomendar.obtener_generos_unicos()
    animes_vistos = set(map(int, recomendar.items_vistos(username)))
    animes_valorados = set(map(int, recomendar.items_valorados(username)))
    animes_totales = animes_vistos | animes_valorados
    if genero:
        anime_id = recomendar.buscar_ids_por_genero(genero, limit=200)
    else:
        anime_id = recomendar.recomendar(username)
    animes_no_vistos = [aid for aid in anime_id if int(aid) not in animes_totales]

    if not animes_no_vistos:
        print("⚠️ Todos los recomendados vistos. Buscando siguientes del top.")
        animes_no_vistos = recomendar.top_animes(limit=500)
        animes_no_vistos = [aid for aid in animes_no_vistos if int(aid) not in animes_totales]
   
    print(f"🎯 Total de animes recomendados por modelo: {len(anime_id)}")
    print(f"👀 Ejemplo de IDs recomendados: {anime_id[:15]}")
    print(f"🚫 IDs ya vistos/valorados ({len(animes_totales)}): {list(animes_totales)[:15]}")
    animes_finales_ids = animes_no_vistos[:9]
    animes_finales = recomendar.datos_animes(animes_finales_ids)

    for aid in animes_finales_ids:
        if aid not in animes_vistos:
            recomendar.insertar_interacciones(aid, username, 0)

    cant_valorados = len(recomendar.items_valorados(username))
    cant_vistos = len(recomendar.items_vistos(username))

    # --- Render ---
    return render_template(
        "recomendaciones.html",
        animes_recomendados=animes_finales,
        username=username,
        cant_valorados=cant_valorados,
        cant_vistos=cant_vistos,
        generos=generos,
        genero_seleccionado=genero
    )


@app.get('/recomendaciones/<int:anime_id>')
def get_recomendaciones_anime(anime_id):
    username = request.cookies.get('username')
    
    animes_vistos = set(map(int, recomendar.items_vistos(username)))
    animes_valorados = set(map(int, recomendar.items_valorados(username)))
    animes_totales = animes_vistos | animes_valorados
    anime_ids_recomendados = recomendar.recomendar_contexto(username, anime_id)
    animes_no_vistos = [aid for aid in anime_ids_recomendados if int(aid) not in animes_totales]

    if not animes_no_vistos:
        print(f"⚠️ Todos los similares a {anime_id} vistos. Mostrando otros del mismo género.")
        genero_principal = recomendar.genero_principal(anime_id)  
        animes_no_vistos = recomendar.buscar_ids_por_genero(genero_principal, limit=20)
        animes_no_vistos = [aid for aid in animes_no_vistos if int(aid) not in animes_totales]

    animes_finales_ids = animes_no_vistos[:3]
    animes_finales = recomendar.datos_animes(animes_finales_ids)

    for aid in animes_finales_ids:
        if aid not in animes_vistos:
            recomendar.insertar_interacciones(aid, username, 0)

    rec = recomendar.obtener_anime(anime_id)

    cant_valorados = len(recomendar.items_valorados(username))
    cant_vistos = len(recomendar.items_vistos(username))

    return render_template("recomendaciones_animes.html", rec=rec, animes_recomendados=animes_finales, username=username, cant_valorados=cant_valorados, cant_vistos=cant_vistos)


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


