from flask import Flask, request, render_template, make_response, redirect
import recomendar

app = Flask(__name__)
app.debug = True

@app.get('/')
def get_index():
    return render_template('login.html')

@app.post('/')
def post_index():
    id_lector = request.form.get('id_lector', None)

    if id_lector: # si me mandaron el id_lector
        recomendar.crear_usuario(id_lector)

        # mando al usuario a la página de recomendaciones
        res = make_response(redirect("/recomendaciones"))

        # pongo el id_lector en una cookie para recordarlo
        res.set_cookie('id_lector', id_lector)
        return res

    # sino, le muestro el formulario de login
    return render_template('login.html')

@app.get('/recomendaciones')
def get_recomendaciones():
    id_lector = request.cookies.get('id_lector')

    id_libros = recomendar.recomendar(id_lector)

    # pongo libros vistos con rating = 0
    for id_libro in id_libros:
        recomendar.insertar_interacciones(id_libro, id_lector, 0)

    libros_recomendados = recomendar.datos_libros(id_libros)
    cant_valorados = len(recomendar.items_valorados(id_lector))
    cant_vistos = len(recomendar.items_vistos(id_lector))

    return render_template("recomendaciones.html", libros_recomendados=libros_recomendados, id_lector=id_lector, cant_valorados=cant_valorados, cant_vistos=cant_vistos)

@app.get('/recomendaciones/<string:id_libro>')
def get_recomendaciones_libro(id_libro):
    id_lector = request.cookies.get('id_lector')

    id_libros = recomendar.recomendar_contexto(id_lector, id_libro)

    # pongo libros vistos con rating = 0
    for id_libro in id_libros:
        recomendar.insertar_interacciones(id_libro, id_lector, 0)

    libros_recomendados = recomendar.datos_libros(id_libros)
    cant_valorados = len(recomendar.items_valorados(id_lector))
    cant_vistos = len(recomendar.items_vistos(id_lector))

    libro = recomendar.obtener_libro(id_libro)

    return render_template("recomendaciones_libro.html", libro=libro, libros_recomendados=libros_recomendados, id_lector=id_lector, cant_valorados=cant_valorados, cant_vistos=cant_vistos)


@app.post('/recomendaciones')
def post_recomendaciones():
    id_lector = request.cookies.get('id_lector')

    # inserto los ratings enviados como interacciones
    for id_libro in request.form.keys():
        rating = int(request.form[id_libro])
        if rating > 0: # 0 es que no puntuó
            recomendar.insertar_interacciones(id_libro, id_lector, rating)

    return make_response(redirect("/recomendaciones"))

@app.get('/reset')
def get_reset():
    id_lector = request.cookies.get('id_lector')
    recomendar.reset_usuario(id_lector)

    return make_response(redirect("/recomendaciones"))

if __name__ == '__main__':
    app.run()


