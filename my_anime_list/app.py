from flask import Flask, request, render_template, make_response, redirect, g
import recomendar

app = Flask(__name__)
app.debug = True

with app.app_context():
    recomendar.init()
    recomendar.calcular_similitud_items()  # Esto se ejecuta UNA sola vez

def is_first_visit(username):
    """Verifica si es la primera visita del usuario"""
    conn = recomendar.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM interacciones WHERE username = ?", [username])
    count = cursor.fetchone()['count']
    #conn.close()
    return count == 0

#@app.teardown_appcontext
#def teardown_db(exception):
#    recomendar.close_db(exception)
@app.teardown_appcontext
def teardown_db(exception):
    """Flask llama esto automáticamente AL FINAL del request"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

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
    #Verifico primera visita
    first_visit = is_first_visit(username)

    animes_id, sistema_usado = recomendar.recomendar(username)

    for anime_id in animes_id:
        recomendar.insertar_interacciones(anime_id, username, 0)

    animes_recomendados = recomendar.datos_animes(animes_id)   
    cant_valorados = len(recomendar.items_valorados(username)) 
    cant_vistos = len(recomendar.items_vistos(username)) 
    generos = recomendar.obtener_generos_unicos()
    genero = request.args.get('genero', None)

    #Obtener ratings existentes del usuario para animes recomendados
    conn = recomendar.get_db()
    cursor = conn.cursor()
    user_ratings = {}
    if animes_id:
        placeholders=','.join(['?'] * len(animes_id))
        cursor.execute(f"""SELECT anime_id, score
                        FROM interacciones
                        WHERE username = ? AND anime_id IN ({placeholders})
                        """, [username] + animes_id)
        for row in cursor.fetchall(): 
            score_value=row['score']
            if score_value is not None:
                user_ratings[row['anime_id']] = int(float(score_value))
            else:
                user_ratings[row['anime_id']] = 0
    #conn.close()            
    # --- Render ---
    return render_template(
        "recomendaciones.html",
        animes_recomendados=animes_recomendados,
        user_rating=user_ratings,
        username=username,
        cant_valorados=cant_valorados,
        cant_vistos=cant_vistos,
        first_visit=first_visit,
        generos=generos,
        genero_seleccionado=genero,
        sistema_usado=sistema_usado
    )


@app.get('/recomendaciones/<int:anime_id>')
def get_recomendaciones_anime(anime_id):
    username = request.cookies.get('username')
    animes_id, sistema_usado = recomendar.recomendar_contexto(username, anime_id)

    for anime_id in animes_id:
        recomendar.insertar_interacciones(anime_id, username, 0)

    animes_finales = recomendar.datos_animes(animes_id)
    cant_valorados = len(recomendar.items_valorados(username)) 
    cant_vistos = len(recomendar.items_vistos(username))
    rec = recomendar.obtener_anime(anime_id)

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


