## version: 1.0 -- recomendaciones al azar

import sqlite3
import os
import random

import metricas

DATABASE_FILE = os.path.dirname(__file__) + "/datos/qll.db"

###

def sql_execute(query, params=None):
    con = sqlite3.connect(DATABASE_FILE)
    cur = con.cursor()
    if params:
        res = cur.execute(query, params)
    else:
        res = cur.execute(query)

    con.commit()
    con.close()
    return res

def sql_select(query, params=None):
    con = sqlite3.connect(DATABASE_FILE)
    con.row_factory = sqlite3.Row # esto es para que devuelva registros en el fetchall
    cur = con.cursor()
    if params:
        res = cur.execute(query, params)
    else:
        res = cur.execute(query)

    ret = res.fetchall()
    con.close()
    return ret

###

def crear_usuario(id_lector):
    query = "INSERT INTO lectores(id_lector) VALUES (?) ON CONFLICT DO NOTHING;" # si el id_lector existe, se produce un conflicto y le digo que no haga nada
    sql_execute(query, [id_lector])
    return

def insertar_interacciones(id_libro, id_lector, rating):
    # si el rating existia, lo actualizo
    query = f"INSERT INTO interacciones(id_libro, id_lector, rating) VALUES (?, ?, ?) ON CONFLICT (id_libro, id_lector) DO UPDATE SET rating=?;"
    sql_execute(query, [id_libro, id_lector, rating, rating])
    return

def reset_usuario(id_lector):
    query = f"DELETE FROM interacciones WHERE id_lector = ?;"
    sql_execute(query, [id_lector])
    return

def obtener_libro(id_libro):
    query = "SELECT * FROM libros WHERE id_libro = ?;"
    libro = sql_select(query, [id_libro])[0]
    return libro

def items_valorados(id_lector):
    query = f"SELECT id_libro FROM interacciones WHERE id_lector = ? AND rating > 0"
    rows = sql_select(query, [id_lector])
    return [i["id_libro"] for i in rows]

def items_vistos(id_lector):
    query = f"SELECT id_libro FROM interacciones WHERE id_lector = ? AND rating = 0"
    rows = sql_select(query, [id_lector])
    return [i["id_libro"] for i in rows]

def items_desconocidos(id_lector):
    query = f"SELECT id_libro FROM libros WHERE id_libro NOT IN (SELECT id_libro FROM interacciones WHERE id_lector = ? AND rating IS NOT NULL)"
    rows = sql_select(query, [id_lector])
    return [i["id_libro"] for i in rows]

def datos_libros(id_libros):
    query = f"SELECT DISTINCT * FROM libros WHERE id_libro IN ({','.join(['?']*len(id_libros))})"
    libros = sql_select(query, id_libros)
    return libros

def rating_libros(id_libros):
    res = sql_select(f"SELECT id_libro, rating FROM interacciones WHERE id_lector = ? AND id_libro IN ({",".join("?"*len(id_libros))});", [id_lector] + id_libros)

    ratings = { i["id_libro"]:i["rating"] for i in res }
    return [ratings.get(i, 0) for i in id_libros]

###

def init():
    print("init: top_libros")
    sql_execute("DROP TABLE IF EXISTS top_libros;")
    sql_execute("CREATE TABLE top_libros AS SELECT id_libro, count(*) AS cant FROM interacciones WHERE rating > 0 GROUP BY 1;")
    # TODO: usar avg(rating) o avg(rating)+count(*)

    # print("init: pares_de_libros")
    # sql_execute("DROP TABLE IF EXISTS pares_de_libros;")
    # sql_execute("""CREATE TABLE pares_de_libros AS
    #             SELECT i1.id_libro AS id_libro_1, i2.id_libro AS id_libro_2, count(*) AS count
    #               FROM interacciones AS i1, interacciones AS i2
    #              WHERE i1.id_lector = i2.id_lector AND i1.id_libro != i2.id_libro AND i1.rating > 3 -- hiperparámetro
    #              GROUP BY 1, 2
    #              HAVING count(*) > 5  -- hiperparámetro
    #             """)
    # sql_execute("CREATE INDEX idx_pares_de_libros ON pares_de_libros (id_libro_1);")
    # TODO: usar avg(rating) para los pares
    # TODO: optimizar hiperparámetros
    return

###

def recomendador_azar(id_lector, libros_relevantes, libros_desconocidos, N=9):
    id_libros = random.sample(libros_desconocidos, N)
    return id_libros

def recomendador_top_n(id_lector, libros_relevantes, libros_desconocidos, N=9):
    # TODO: si tiene rating bajo, lo tomo?
    # TODO: en vez de cantidad de interacciones, promedio de rating

    res = sql_select(f"SELECT id_libro FROM top_libros WHERE id_libro NOT IN ({",".join("?"*len(libros_relevantes))}) ORDER BY cant DESC LIMIT ?;", libros_relevantes + [N])
    id_libros = [i["id_libro"] for i in res]

    return id_libros

def recomendador_pares(id_lector, libros_relevantes, libros_desconocidos, N=9):
    # TODO:
    res = sql_select(f"""
                     SELECT DISTINCT id_libro_2 AS id_libro
                       FROM pares_de_libros
                      WHERE id_libro_1 IN ({",".join("?"*len(libros_relevantes))})
                        AND id_libro_2 IN ({",".join("?"*len(libros_desconocidos))})
                      ORDER BY count DESC
                      LIMIT ?;"""
                     , libros_relevantes+libros_desconocidos+[N])

    id_libros = [i["id_libro"] for i in res]

    return id_libros[:N]

def recomendador_perfiles(id_lector, libros_relevantes, libros_desconocidos, N=9):
    # TODO: optimizar hiperparámetros
    # TODO: usar avg(rating)
    # TODO: ponderar diferentes perfiles
    res = sql_select(f"""
               SELECT l.genero, count(*) AS cant
                 FROM interacciones AS i JOIN libros AS l ON i.id_libro = l.id_libro
                WHERE id_lector = ?
                  AND i.id_libro IN ({",".join("?"*len(libros_relevantes))})
                  AND i.rating > 3 -- hiperparámetro
                GROUP BY 1
               HAVING count(*) > 2 -- hiperparámetro
                ORDER BY 2 DESC;
        """, [id_lector]+libros_relevantes)

    total_genero = float(sum([i["cant"] for i in res]))
    perfil_genero = {i["genero"]:i["cant"]/total_genero for i in res}

    res = sql_select(f"""
               SELECT l.autor, count(*) AS cant
                 FROM interacciones AS i JOIN libros AS l ON i.id_libro = l.id_libro
                WHERE id_lector = ?
                  AND i.id_libro IN ({",".join("?"*len(libros_relevantes))})
                  AND i.rating > 3 -- hiperparámetro
                GROUP BY 1
               HAVING count(*) > 2 -- hiperparámetro
                ORDER BY 2 DESC;
        """, [id_lector]+libros_relevantes)

    total_autor = float(sum([i["cant"] for i in res]))
    perfil_autor = {i["autor"]:i["cant"]/total_autor for i in res}

    res = sql_select(f"""SELECT id_libro, genero, autor
                           FROM libros
                          WHERE id_libro IN ({",".join("?"*len(libros_desconocidos))})
                             AND (genero IN ({ ",".join("?"*len(perfil_genero.keys())) })
                             OR autor IN ({ ",".join("?"*len(perfil_autor.keys())) }))
                          ;""", libros_desconocidos+list(perfil_genero.keys()) + list(perfil_autor.keys()))

    libros_a_puntuar = [ (i["id_libro"], perfil_genero.get(i["genero"], 0) + perfil_autor.get(i["autor"], 0)) for i in res]
    libros_a_puntuar = sorted(libros_a_puntuar, key=lambda x: x[1], reverse=True)
    id_libros = [i[0] for i in libros_a_puntuar]

    return id_libros[:N]

###

def recomendar(id_lector, libros_relevantes=None, libros_desconocidos=None, N=9):
    if not libros_relevantes:
        libros_relevantes = items_valorados(id_lector)

    if not libros_desconocidos:
        libros_desconocidos = items_desconocidos(id_lector)

    # return recomendador_azar(id_lector, libros_relevantes, libros_desconocidos, N)

    if len(libros_relevantes) == 0: # TODO: cambiar este límite
        rec = recomendador_top_n(id_lector, libros_relevantes, libros_desconocidos, N)
    elif len(libros_relevantes) <= 5: # TODO: cambiar este límite
        rec = recomendador_pares(id_lector, libros_relevantes, libros_desconocidos, N)
    else:
        rec = recomendador_perfiles(id_lector, libros_relevantes, libros_desconocidos, N)

    return rec

def recomendar_contexto(id_lector, id_libro, libros_relevantes=None, libros_desconocidos=None, N=3):
    if not libros_relevantes:
        libros_relevantes = items_valorados(id_lector)

    if not libros_desconocidos:
        libros_desconocidos = items_desconocidos(id_lector)

    #return recomendador_azar(id_lector, libros_relevantes, libros_desconocidos, N)
    return recomendador_top_n(id_lector, libros_relevantes, libros_desconocidos, N)

###

if __name__ == '__main__':
    def test(id_lector):
        libros_relevantes = items_valorados(id_lector)
        libros_desconocidos = items_vistos(id_lector) + items_desconocidos(id_lector)

        random.shuffle(libros_relevantes)

        corte = int(len(libros_relevantes)*0.8)
        libros_relevantes_training = libros_relevantes[:corte]
        libros_relevantes_testing = libros_relevantes[corte:] + libros_desconocidos

        recomendacion = recomendar(id_lector, libros_relevantes_training, libros_relevantes_testing, 20)

        relevance_scores = rating_libros(recomendacion)

        score = metricas.normalized_discounted_cumulative_gain(relevance_scores)
        return score

    ###

    init()

    id_lectores = sql_select("SELECT id_lector FROM lectores WHERE (SELECT count(*) FROM interacciones WHERE id_lector = lectores.id_lector) >= 100 limit 100;")
    id_lectores = [i["id_lector"] for i in id_lectores]

    scores = []
    for id_lector in id_lectores:
        score = test(id_lector)
        scores.append(score)
        print(f"{id_lector=} >> {score=:.6f}")

    print(f"NDCG: {sum(scores)/len(scores):.6f}")

    # NDCG: 0.499473 --> recomendador_top_N

    id_lectores = sql_select("SELECT id_lector FROM lectores WHERE (SELECT count(*) FROM interacciones WHERE id_lector = lectores.id_lector) >= 100 limit 100;")
    id_lectores = [i["id_lector"] for i in id_lectores]

    scores = []
    for id_lector in id_lectores:
        score = test(id_lector)
        scores.append(score)
        print(f"{id_lector=} >> {score=:.6f}")

    print(f"NDCG: {sum(scores)/len(scores):.6f}")


