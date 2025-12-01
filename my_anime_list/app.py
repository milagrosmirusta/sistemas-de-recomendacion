from flask import Flask, request, render_template, make_response, redirect, g
import recomendar
import estadisticas

app = Flask(__name__)
app.debug = True

with app.app_context():
    recomendar.crear_backup_db()
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
    genero_filtro = request.args.get('genero', None)
    animes_id, sistema_usado = recomendar.recomendar(username)

    if genero_filtro and genero_filtro != "":
        animes_id = recomendar.buscar_ids_por_genero(genero_filtro, limit=9)
        sistema_usado = f"Filtrado por género: {genero_filtro}"
    else:
        # Sin filtro, usar recomendaciones personalizadas
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


@app.get('/admin/factory_reset')
def get_admin_reset():
    return render_template('admin_reset.html')

@app.post('/admin/factory_reset')
def admin_factory_reset():
    password = request.form.get('password', '')
    
    # Cambia esta contraseña por la que quieras
    if password != "123456":
        return render_template('admin_reset.html', error="❌ Contraseña incorrecta"), 403
    
    # Ejecutar reset de fábrica
    success = recomendar.factory_reset()
    
    if success:
        # Limpiar cookie del usuario actual
        res = make_response(redirect("/"))
        res.set_cookie('username', '', expires=0)
        return res
    else:
        return render_template('admin_reset.html', error="❌ Error durante el reset. Verifica que exista el backup."), 500
    
@app.get('/perfil')
def get_perfil():
    username = request.cookies.get('username')
    
    if not username:
        return redirect("/")
    
    # Obtener estadísticas
    stats = estadisticas.obtener_estadisticas_usuario(username)
    
    # Verificar si tiene valoraciones
    if stats['basicas']['total_valorados'] == 0:
        return render_template('perfil.html', username=username, sin_datos=True)
    
    # Opcional: Comparación global
    comparacion = estadisticas.obtener_comparacion_global(username)
    
    return render_template('perfil.html', 
                          username=username, 
                          stats=stats, 
                          comparacion=comparacion)

@app.get('/recomendaciones/<int:anime_id>')
def get_recomendaciones_anime(anime_id):
    username = request.cookies.get('username')
    anime_principal_id = anime_id
    animes_id, sistema_usado = recomendar.recomendar_contexto(username, anime_principal_id)

    for rec_anime_id in animes_id:
        recomendar.insertar_interacciones(rec_anime_id, username, 0)

    animes_finales = recomendar.datos_animes(animes_id)
    cant_valorados = len(recomendar.items_valorados(username)) 
    cant_vistos = len(recomendar.items_vistos(username))
    rec = recomendar.obtener_anime(anime_principal_id)

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


