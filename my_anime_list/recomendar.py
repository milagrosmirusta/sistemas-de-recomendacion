## version: 1.0 -- recomendaciones al azar

from mimetypes import init
import sqlite3
import os
import random

import metricas

#DATABASE_FILE = os.path.dirname(os.path.abspath("__file__")) + "/datos/qll.db"
DATABASE_FILE = os.path.dirname(__file__) + "/datos/mal.db"

### --- RECOMENDADOR USADO --- ###
RECOMENDADOR_ACTIVO = "top_n"  # opciones: "azar", "top_n", "item_based", "user_based"

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

def crear_usuario(username):
    query = "INSERT INTO usuarios(username) VALUES (?) ON CONFLICT DO NOTHING;" # si el username existe, se produce un conflicto y le digo que no haga nada
    sql_execute(query, [username])
    return

def insertar_interacciones(anime_id, username, score):
    query = f"INSERT INTO interacciones(anime_id, username, score) VALUES (?, ?, ?) ON CONFLICT (anime_id, username) DO UPDATE SET score=?;" # si el rating existia lo actualizo
    sql_execute(query, [anime_id, username, score, score])
    return

def reset_usuario(username):
    query = f"DELETE FROM interacciones WHERE username = ?;"
    sql_execute(query, [username])
    return

def obtener_anime(id):
    query = "SELECT * FROM animes WHERE anime_id = ?;"
    anime = sql_select(query, [id])[0]
    return anime

def items_valorados(username):
    query = f"SELECT anime_id FROM interacciones WHERE username = ? AND score > 0"
    rows = sql_select(query, [username])
    return [i["anime_id"] for i in rows]

def items_vistos(username):
    query = f"SELECT anime_id FROM interacciones WHERE username = ? AND score = 0"
    rows = sql_select(query, [username])
    return [i["anime_id"] for i in rows]

def items_desconocidos(username):
    query = f"SELECT anime_id FROM animes WHERE anime_id NOT IN (SELECT anime_id FROM interacciones WHERE username = ? AND score IS NOT NULL)"
    rows = sql_select(query, [username])
    return [i["anime_id"] for i in rows]

def datos_animes(anime_id):
    query = f"SELECT DISTINCT * FROM animes WHERE anime_id IN ({','.join(['?']*len(anime_id))})"
    animes = sql_select(query, anime_id)
    return animes

###
def init():
    print("init: top_animes")
    sql_execute("DROP TABLE IF EXISTS top_animes;")
    sql_execute("""
        CREATE TABLE top_animes AS
        SELECT anime_id, members, score
        FROM animes
        ORDER BY score DESC, members DESC
    """)

def recomendar_azar(username, animes_relevantes, animes_desconocidos, N=9):
    anime_id = random.sample(animes_desconocidos, N)
    return anime_id

def recomendador_top_n(username, animes_relevantes, animes_desconocidos, N=9):
    res = sql_select(f"""
        SELECT anime_id 
        FROM top_animes 
        WHERE anime_id NOT IN ({",".join("?"*len(animes_relevantes))})
        ORDER BY score DESC 
        LIMIT ?;
    """, animes_relevantes + [N])

    id_animes = [i["anime_id"] for i in res]
    return id_animes

def recomendar(username, animes_relevantes=None, animes_desconocidos=None, N=9):
    if not animes_relevantes:
        animes_relevantes = items_valorados(username)

    if not animes_desconocidos:
        animes_desconocidos = items_desconocidos(username)

    if RECOMENDADOR_ACTIVO == "azar":
        return recomendar_azar(username, animes_relevantes, animes_desconocidos, N)
    elif RECOMENDADOR_ACTIVO == "top_n":
        return recomendador_top_n(username, animes_relevantes, animes_desconocidos, N)
    else:
        raise ValueError(f"Recomendador '{RECOMENDADOR_ACTIVO}' no reconocido")

def recomendar_contexto(username, anime_id, animes_relevantes=None, animes_desconocidos=None, N=3):
    if not animes_relevantes:
        animes_relevantes = items_valorados(username)

    if not animes_desconocidos:
        animes_desconocidos = items_desconocidos(username)

    if RECOMENDADOR_ACTIVO == "azar":
        return recomendar_azar(username, animes_relevantes, animes_desconocidos, N)
    elif RECOMENDADOR_ACTIVO == "top_n":
        return recomendador_top_n(username, animes_relevantes, animes_desconocidos, N)
    else:
        raise ValueError(f"Recomendador '{RECOMENDADOR_ACTIVO}' no reconocido")        

###

def test(username):
    animes_relevantes = items_valorados(username)
    animes_desconocidos = items_vistos(username) + items_desconocidos(username)

    random.shuffle(animes_relevantes)

    corte = int(len(animes_relevantes)*0.8)
    animes_relevantes_training = animes_relevantes[:corte]
    animes_relevantes_testing = animes_relevantes[corte:] + animes_desconocidos

    recomendacion = recomendar(username, animes_relevantes_training, animes_relevantes_testing, 20)

    relevance_scores = []
    for id in recomendacion:
        res = sql_select("SELECT score FROM interacciones WHERE username = ? AND anime_id = ?;", [username, id])
        if res is not None and len(res) > 0:
            rating = res[0][0]
        else:
            rating = 0


        relevance_scores.append(rating)
    score = metricas.normalized_discounted_cumulative_gain(relevance_scores)
    return score

if __name__ == '__main__':
    user_animes = sql_select("""
        SELECT username 
        FROM usuarios 
        WHERE (SELECT count(*) FROM interacciones WHERE username = usuarios.username) >= 100 
        LIMIT 50;
    """)
    user_animes = [i["username"] for i in user_animes]

    scores = []
    for user in user_animes:
        score = test(user)
        scores.append(score)
        print(f"{user} >> {score:.6f}")

    ndcg_mean = sum(scores)/len(scores)
    print(f"\nNDCG: {ndcg_mean:.6f} --> {RECOMENDADOR_ACTIVO}")

    # 💾 Guardar resultado
    from datetime import datetime
    with open("resultados.txt", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {RECOMENDADOR_ACTIVO} - NDCG: {ndcg_mean:.6f}\n")

    print("✅ Resultados guardados en resultados.txt")


   
