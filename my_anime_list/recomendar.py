## version: 1.4 -- recomendaciones item based

from mimetypes import init
import sqlite3
import os
import random
from flask import g

import metricas

#DATABASE_FILE = os.path.dirname(os.path.abspath("__file__")) + "/datos/qll.db"
DATABASE_FILE = os.path.dirname(__file__) + "/datos/mal.db"

### --- RECOMENDADOR USADO --- ###
RECOMENDADOR_ACTIVO = "item_based"  # opciones: "azar", "top_n", "item_based", "user_based"

## Conexión global
# Flag para saber si estamos en Flask o testing directo
_testing_db = None  # Conexión para testing

## Conexión global
def get_db():
    """
    Crea una conexión única por request (persistente en g) cuando está en Flask.
    Si está en testing directo, usa una conexión global.
    """
    # Si estamos en testing directo (sin Flask)
    if _testing_db is not None:
        return _testing_db
    
    # Si estamos en Flask
    try:
        if 'db' not in g:
            g.db = sqlite3.connect(DATABASE_FILE)
            g.db.row_factory = sqlite3.Row
        return g.db
    except RuntimeError:
        # Si g no existe, crear conexión temporal
        db = sqlite3.connect(DATABASE_FILE)
        db.row_factory = sqlite3.Row
        return db


def close_db(e=None):
    """Cierra la conexión si existe al final del request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_testing_db():
    """Inicializa la base de datos para testing (sin Flask)."""
    global _testing_db
    _testing_db = sqlite3.connect(DATABASE_FILE)
    _testing_db.row_factory = sqlite3.Row
    return _testing_db


def close_testing_db():
    """Cierra la conexión de testing."""
    global _testing_db
    if _testing_db is not None:
        _testing_db.close()
        _testing_db = None
# def sql_execute(query, params=None):
#     con = sqlite3.connect(DATABASE_FILE)
#     cur = con.cursor()
#     if params:
#         res = cur.execute(query, params)
#     else:
#         res = cur.execute(query)

#     con.commit()
#     con.close()
#     return res
def sql_execute(query, params=None):
    db = get_db()
    cur = db.cursor()
    if params:
        cur.execute(query, params)
    else:
        cur.execute(query)
    db.commit()
    return cur


def sql_select(query, params=None):
    db = get_db()
    cur = db.cursor()
    if params:
        cur.execute(query, params)
    else:
        cur.execute(query)
    return cur.fetchall()

# def sql_select(query, params=None):
#     con = sqlite3.connect(DATABASE_FILE)
#     con.row_factory = sqlite3.Row # esto es para que devuelva registros en el fetchall
#     cur = con.cursor()
#     if params:
#         res = cur.execute(query, params)
#     else:
#         res = cur.execute(query)

#     ret = res.fetchall()
#     con.close()
#     return ret

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
    query = """
        SELECT a.anime_id
        FROM animes a
        LEFT JOIN interacciones i 
          ON a.anime_id = i.anime_id AND i.username = ?
        WHERE i.anime_id IS NULL;
    """
    rows = sql_select(query, [username])
    return [i["anime_id"] for i in rows]


def datos_animes(anime_id):
    query = f"SELECT DISTINCT * FROM animes WHERE anime_id IN ({','.join(['?']*len(anime_id))})"
    animes = sql_select(query, anime_id)
    return animes

def filtrar_por_genero(anime_principal_id, lista_ids):
    """Filtra los animes que compartan al menos un género con el anime principal."""
    # Obtener géneros del anime principal
    anime_principal = sql_select("SELECT genres FROM animes WHERE anime_id = ?;", [anime_principal_id])
    if not anime_principal:
        return lista_ids  # si no hay géneros, no filtro
    generos_principal = [g.strip() for g in anime_principal[0]["genres"].split(",")]

    if not lista_ids:
        return []

    # Busco todos los candidatos y filtro por género
    placeholders = ",".join(["?"] * len(lista_ids))
    candidatos = sql_select(f"SELECT anime_id, genres FROM animes WHERE anime_id IN ({placeholders})", lista_ids)

    filtrados = []
    for a in candidatos:
        generos = [g.strip() for g in a["genres"].split(",")]
        if any(g in generos for g in generos_principal) and a["anime_id"] != anime_principal_id:
            filtrados.append(a["anime_id"])

    # Si hay pocos, los devuelvo todos, si no, muestro los primeros 3 al azar
    return random.sample(filtrados, k=min(3, len(filtrados)))

def calcular_similitud_items():
    """
    Crea una tabla de items similares basada en co-ocurrencia.
    Solo la crea si está vacía o no existe.
    """
    print("⏳ Verificando tabla item_similitudes...")
    
    # Verificar si la tabla existe
    result = sql_select("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='item_similitudes';
    """)
    
    if result:  # La tabla existe
        # Verificar si tiene datos
        count = sql_select("SELECT COUNT(*) as cnt FROM item_similitudes;")
        if count[0]["cnt"] > 0:
            print("✅ item_similitudes ya existe con datos, omitiendo creación")
            return
    
    print("🔄 Creando tabla item_similitudes...")
    sql_execute("DROP TABLE IF EXISTS item_similitudes;")
    sql_execute("""
        CREATE TABLE item_similitudes (
            anime_id_1 BIGINT,
            anime_id_2 BIGINT,
            similitud FLOAT,
            PRIMARY KEY (anime_id_1, anime_id_2)
        );
    """)
    
    print("📊 Calculando similitudes (esto puede tardar varios minutos)...")
    sql_execute("""
        INSERT INTO item_similitudes (anime_id_1, anime_id_2, similitud)
        SELECT 
            i1.anime_id AS anime_id_1,
            i2.anime_id AS anime_id_2,
            COUNT(*) AS similitud
        FROM interacciones i1
        JOIN interacciones i2 
            ON i1.username = i2.username 
            AND i1.anime_id < i2.anime_id  
        WHERE i1.score >= 7 AND i2.score >= 7
        GROUP BY i1.anime_id, i2.anime_id
        HAVING COUNT(*) >= 100  
        ORDER BY similitud DESC;
    """)
    
    count = sql_select("SELECT COUNT(*) as cnt FROM item_similitudes;")
    print(f"✅ item_similitudes creada con {count[0]['cnt']} pares de similitudes")
    

###
def init():
    """Crea la tabla top_animes solo si no existe o está vacía."""
    # Verificar si la tabla existe y tiene datos
    result = sql_select("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='top_animes';
    """)

    if result:  # La tabla existe
        # Verificar si tiene datos
        count = sql_select("SELECT COUNT(*) as cnt FROM top_animes;")
        if count[0]["cnt"] > 0:
            print("✅ init: top_animes ya existe con datos, omitiendo creación")
            return

    print("🔄 init: creando top_animes")
    sql_execute("DROP TABLE IF EXISTS top_animes;")
    sql_execute("""
        CREATE TABLE top_animes (
        anime_id BIGINT PRIMARY KEY,
        members BIGINT,
        score FLOAT);""")
    sql_execute("""INSERT INTO top_animes (anime_id, members, score)
    SELECT anime_id, members, score
    FROM animes
    ORDER BY score DESC, members DESC""")
    print("✅ init: top_animes creada exitosamente")



def top_animes(limit=500):
    """
    Devuelve los IDs del top general, ya generado por init().
    """
    query = "SELECT anime_id FROM top_animes LIMIT ?"
    rows = sql_select(query, [limit])
    return [r["anime_id"] for r in rows]    

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

def recomendador_item_based(username, animes_relevantes, animes_desconocidos, N=9):

    if not animes_relevantes:
        # Si no tiene valoraciones, caer en top_n
        return recomendador_top_n(username, animes_relevantes, animes_desconocidos, N)
    
    placeholders = ",".join("?" * len(animes_relevantes))
    
    # Buscar animes similares a los que le gustaron
    query = f"""
        SELECT 
            CASE 
                WHEN s.anime_id_1 IN ({placeholders}) THEN s.anime_id_2
                ELSE s.anime_id_1
            END AS anime_id,
            SUM(s.similitud) AS score_total
        FROM item_similitudes s
        WHERE (s.anime_id_1 IN ({placeholders}) OR s.anime_id_2 IN ({placeholders}))
          AND anime_id NOT IN ({placeholders})  -- excluir los que ya vio
        GROUP BY anime_id
        ORDER BY score_total DESC
        LIMIT ?;
    """
    
    params = animes_relevantes * 4 + [N]
    res = sql_select(query, params)
    
    return [r["anime_id"] for r in res]

def genero_principal(anime_id):

    query = "SELECT genres FROM animes WHERE anime_id = ?"
    row = sql_select(query, [anime_id])
    if not row:
        return None
    generos = row[0]["genres"].split(", ")
    return generos[0] if generos else None


def recomendar(username, animes_relevantes=None, animes_desconocidos=None, N=500):
    if not animes_relevantes:
        animes_relevantes = items_valorados(username)

    if not animes_desconocidos:
        animes_desconocidos = items_desconocidos(username)

    if RECOMENDADOR_ACTIVO == "azar":
        return recomendar_azar(username, animes_relevantes, animes_desconocidos, N)
    elif RECOMENDADOR_ACTIVO == "top_n":
        return recomendador_top_n(username, animes_relevantes, animes_desconocidos, N)
    elif RECOMENDADOR_ACTIVO == "item_based":
        return recomendador_item_based(username, animes_relevantes, animes_desconocidos, N)
    else:
        raise ValueError(f"Recomendador '{RECOMENDADOR_ACTIVO}' no reconocido")

def recomendar_contexto(username, anime_id, animes_relevantes=None, animes_desconocidos=None, N=500):
    if not animes_relevantes:
        animes_relevantes = items_valorados(username)

    if not animes_desconocidos:
        animes_desconocidos = items_desconocidos(username)

    # Primero obtenemos las recomendaciones base (según el modo activo)
    if RECOMENDADOR_ACTIVO == "azar":
        base_recs = recomendar_azar(username, animes_relevantes, animes_desconocidos, N * 3)
    elif RECOMENDADOR_ACTIVO == "top_n":
        base_recs = recomendador_top_n(username, animes_relevantes, animes_desconocidos, N * 3)
    elif RECOMENDADOR_ACTIVO == "item_based":
        base_recs = recomendador_item_based(username, animes_relevantes, animes_desconocidos, N * 3)
    else:
        raise ValueError(f"Recomendador '{RECOMENDADOR_ACTIVO}' no reconocido")

    # Luego filtramos por género del anime principal
    filtrados = filtrar_por_genero(anime_id, base_recs)

    # Si el filtro deja pocos resultados, completamos con el resto
    if len(filtrados) < N:
        faltan = [x for x in base_recs if x not in filtrados and x != anime_id]
        random.shuffle(faltan)
        filtrados += faltan[: N - len(filtrados)]

    return filtrados

def buscar_ids_por_genero(genero, limit=9):
    """Devuelve los IDs de animes que contengan el género dado."""
    pattern = f"%{genero}%"
    query = f"""
        SELECT anime_id 
        FROM animes
        WHERE genres LIKE ?
        ORDER BY score DESC, members DESC
        LIMIT ?
    """
    res = sql_select(query, [pattern, limit])
    return [r["anime_id"] for r in res]

def obtener_generos_unicos():
    """Devuelve una lista con todos los géneros únicos de la tabla animes."""
    res = sql_select("SELECT genres FROM animes;")
    generos = set()

    for r in res:
        if r["genres"]:
            for g in r["genres"].split(","):
                generos.add(g.strip())

    return sorted(list(generos))

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
    # 🔧 Modo testing: usar conexión directa sin Flask
    print("🧪 Modo testing activado\n")
    
    # Inicializar conexión para testing
    init_testing_db()
    
    # Inicializar tablas si es necesario
    init()
    calcular_similitud_items()
    
    # Ejecutar tests
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
    
    # Cerrar conexión de testing
    close_testing_db()

   
