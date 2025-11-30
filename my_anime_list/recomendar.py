from mimetypes import init
import sqlite3
import os
import random
from flask import g
import time

import metricas

DATABASE_FILE = os.path.dirname(__file__) + "/datos/mal.db"

### --- RECOMENDADOR USADO --- ###
RECOMENDADOR_ACTIVO = "hibrido"  # opciones: "azar", "top_n", "item_based", "two_tower", "content_based", "content_based_avanzado", "hibrido", "hibrido_con_tt"


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


# def close_db(e=None):
#     """Cierra la conexión si existe al final del request."""
#     db = g.pop('db', None)
#     if db is not None:
#         db.close()


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
    if score == 0:
        # Si score es 0 (marcar como visto), solo insertar si NO existe
        query = "INSERT INTO interacciones(anime_id, username, score) VALUES (?, ?, ?) ON CONFLICT (anime_id, username) DO NOTHING;"
        sql_execute(query, [anime_id, username, score])
    else:
        # Si score > 0 (valoración real), insertar o actualizar siempre
        query = "INSERT INTO interacciones(anime_id, username, score) VALUES (?, ?, ?) ON CONFLICT (anime_id, username) DO UPDATE SET score=?;"
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
    query = f"SELECT anime_id FROM interacciones WHERE username = ?"
    rows = sql_select(query, [username])
    return [i["anime_id"] for i in rows]


def items_desconocidos(username):
    query = """
        SELECT a.anime_id
        FROM animes a
        WHERE a.anime_id NOT IN (
            SELECT anime_id FROM interacciones WHERE username = ?
        );
    """
    rows = sql_select(query, [username])
    return [i["anime_id"] for i in rows]


def datos_animes(anime_id):
    query = f"SELECT DISTINCT * FROM animes WHERE anime_id IN ({','.join(['?']*len(anime_id))})"
    animes = sql_select(query, anime_id)
    return animes

def filtrar_por_genero(anime_principal_id, lista_ids, N=3):
    """Filtra los animes que compartan al menos un género con el anime principal."""
    # Obtener géneros del anime principal
    anime_principal = sql_select("SELECT genres FROM animes WHERE anime_id = ?;", [anime_principal_id])

    if not anime_principal or not anime_principal[0]["genres"]:
        # Si no existe el anime o no tiene géneros, devolver los primeros N de la lista
        return lista_ids[:N] if lista_ids else []

    generos_principal = [g.strip() for g in anime_principal[0]["genres"].split(",")]

    if not lista_ids:
        return []

    # Busco todos los candidatos y filtro por género
    placeholders = ",".join(["?"] * len(lista_ids))
    candidatos = sql_select(f"SELECT anime_id, genres FROM animes WHERE anime_id IN ({placeholders})", lista_ids)

    filtrados = []
    for a in candidatos:
        # Manejo casos donde genres puede ser None
        if not a["genres"]:
            continue
        generos = [g.strip() for g in a["genres"].split(",")]
        if any(g in generos for g in generos_principal) and a["anime_id"] != anime_principal_id:
            filtrados.append(a["anime_id"])

    # Si no hay filtrados, devolver lista vacía para que se complete después
    if not filtrados:
        return []

    # Devolver hasta N animes al azar
    return random.sample(filtrados, k=min(N, len(filtrados)))

def calcular_similitud_items():
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
            print("item_similitudes ya existe con datos, omitiendo creación")
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
    
    print("Calculando similitudes (esto puede tardar varios minutos)...")
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
    print(f"item_similitudes creada con {count[0]['cnt']} pares de similitudes")
    

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
            print("init: top_animes ya existe con datos, omitiendo creación")
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
    print("init: top_animes creada exitosamente")



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
        WHERE anime_id IN ({",".join("?"*len(animes_desconocidos))})
        ORDER BY score DESC 
        LIMIT ?;
    """, animes_desconocidos + [N])

    id_animes = [i["anime_id"] for i in res]
    return id_animes

def recomendador_item_based(username, animes_relevantes, animes_desconocidos, N=9):

    if not animes_relevantes:
        # Si no tiene valoraciones, caer en top_n
        return recomendador_top_n(username, animes_relevantes, animes_desconocidos, N)

    if not animes_desconocidos:
        return []

    placeholders_relevantes = ",".join("?" * len(animes_relevantes))

    # Limitar animes_desconocidos si son demasiados (límite SQLite)
    if len(animes_desconocidos) > 800:
        animes_desconocidos = random.sample(animes_desconocidos, 800)

    placeholders_desconocidos = ",".join("?" * len(animes_desconocidos))

    # Buscar animes similares a los que le gustaron, pero solo entre los desconocidos
    query = f"""
        SELECT
            CASE
                WHEN s.anime_id_1 IN ({placeholders_relevantes}) THEN s.anime_id_2
                ELSE s.anime_id_1
            END AS anime_id,
            SUM(s.similitud) AS score_total
        FROM item_similitudes s
        WHERE (s.anime_id_1 IN ({placeholders_relevantes}) OR s.anime_id_2 IN ({placeholders_relevantes}))
          AND anime_id NOT IN ({placeholders_relevantes})  -- excluir los valorados
          AND anime_id IN ({placeholders_desconocidos})  -- solo recomendar desconocidos
        GROUP BY anime_id
        ORDER BY score_total DESC
        LIMIT ?;
    """

    params = animes_relevantes * 4 + animes_desconocidos + [N]
    res = sql_select(query, params)

    return [r["anime_id"] for r in res]

def recomendador_content_based(username, animes_relevantes, animes_desconocidos, N=9):
    """
    Recomienda basándose sólo en los géneros de los animes gustados
    """
    if not animes_relevantes:
        return recomendador_top_n(username, animes_relevantes, animes_desconocidos, N)
    
    # Obtener géneros de animes que le gustaron (score >= 7)
    query = f"""
        SELECT a.genres
        FROM animes a
        JOIN interacciones i ON a.anime_id = i.anime_id
        WHERE i.username = ? AND i.score >= 7
    """
    rows = sql_select(query, [username])
    
    # Contar géneros favoritos
    genre_counts = {}
    for row in rows:
        if row['genres']:
            for genre in row['genres'].split(','):
                genre = genre.strip()
                genre_counts[genre] = genre_counts.get(genre, 0) + 1
    
    # Ordenar géneros por frecuencia
    top_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    
    if not top_genres:
        return recomendador_top_n(username, animes_relevantes, animes_desconocidos, N)
    
    # Buscar animes con esos géneros
    genre_patterns = [f"%{g[0]}%" for g in top_genres]
    placeholders_relevant = ",".join("?" * len(animes_relevantes))
    
    # Query para encontrar animes similares
    query = f"""
        SELECT DISTINCT a.anime_id, a.score, a.members
        FROM animes a
        WHERE (a.genres LIKE ? OR a.genres LIKE ? OR a.genres LIKE ?)
          AND a.anime_id NOT IN ({placeholders_relevant})
          AND a.anime_id IN ({",".join("?" * len(animes_desconocidos))})
        ORDER BY a.score DESC, a.members DESC
        LIMIT ?
    """
    
    params = genre_patterns + animes_relevantes + animes_desconocidos + [N]
    results = sql_select(query, params)
    
    return [r['anime_id'] for r in results]

def recomendador_content_based_avanzado(username, animes_relevantes, animes_desconocidos, N=9):
    """
    Content-based con múltiples features: géneros, studios, score range.
    OPTIMIZADO: Una sola query masiva en lugar de miles.
    """
    if not animes_relevantes:
        return recomendador_top_n(username, animes_relevantes, animes_desconocidos, N)
    
    # 1. Analizar preferencias del usuario
    query = """
        SELECT a.genres, a.studios, a.score
        FROM animes a
        JOIN interacciones i ON a.anime_id = i.anime_id
        WHERE i.username = ? AND i.score >= 7
    """
    rows = sql_select(query, [username])
    
    # Extraer preferencias
    genre_counts = {}
    studio_counts = {}
    scores = []
    
    for row in rows:
        # Géneros
        if row['genres']:
            for genre in row['genres'].split(','):
                genre = genre.strip()
                genre_counts[genre] = genre_counts.get(genre, 0) + 1
        
        # Studios
        if row['studios']:
            for studio in row['studios'].split(','):
                studio = studio.strip()
                studio_counts[studio] = studio_counts.get(studio, 0) + 1
        
        # Scores
        if row['score']:
            scores.append(row['score'])
    
    if not genre_counts:
        return recomendador_top_n(username, animes_relevantes, animes_desconocidos, N)
    
    # Top géneros y studios
    top_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    top_studios = sorted(studio_counts.items(), key=lambda x: x[1], reverse=True)[:2]
    
    # Score range preferido
    avg_score = sum(scores) / len(scores) if scores else 7.0
    
    # ✅ OPTIMIZACIÓN: Limitar candidatos para evitar overflow de SQLite
    # SQLite tiene límite de ~999 parámetros en una query
    if len(animes_desconocidos) > 800:
        animes_desconocidos = random.sample(animes_desconocidos, 800)
    
    if not animes_desconocidos:
        return []
    
    # ✅ OPTIMIZACIÓN: UNA query masiva en lugar de miles
    placeholders = ",".join("?" * len(animes_desconocidos))
    query = f"""
        SELECT anime_id, genres, studios, score
        FROM animes
        WHERE anime_id IN ({placeholders})
    """
    candidates = sql_select(query, animes_desconocidos)
    
    # 2. Calcular similarity para cada candidato (en memoria, súper rápido)
    candidate_scores = []
    
    for anime in candidates:
        similarity = 0
        
        # Score por géneros (peso: 3)
        if anime['genres']:
            anime_genres = [g.strip() for g in anime['genres'].split(',')]
            for genre, _ in top_genres:
                if genre in anime_genres:
                    similarity += 3
        
        # Score por studios (peso: 2)
        if anime['studios']:
            anime_studios = [s.strip() for s in anime['studios'].split(',')]
            for studio, _ in top_studios:
                if studio in anime_studios:
                    similarity += 2
        
        # Score por rating similar (peso: 1)
        if anime['score'] and abs(anime['score'] - avg_score) <= 1.5:
            similarity += 1
        
        if similarity > 0:
            candidate_scores.append((anime['anime_id'], similarity))
    
    # Ordenar por similarity y tomar top N
    candidate_scores.sort(key=lambda x: x[1], reverse=True)
    return [anime_id for anime_id, _ in candidate_scores[:N]]
def mezclar_recomendaciones(lista1, lista2, N):
    """
    Mezcla dos listas de recomendaciones intercalando, sin duplicados.
    Prioriza lista1 (aparece primero en el intercalado).
    """
    resultado = []
    i, j = 0, 0
    
    while len(resultado) < N and (i < len(lista1) or j < len(lista2)):
        # Intentar agregar de lista1 primero
        if i < len(lista1) and lista1[i] not in resultado:
            resultado.append(lista1[i])
            i += 1
        
        # Luego de lista2
        if len(resultado) < N and j < len(lista2) and lista2[j] not in resultado:
            resultado.append(lista2[j])
            j += 1
        
        # Avanzar índices si ya están en resultado
        if i < len(lista1) and lista1[i] in resultado:
            i += 1
        if j < len(lista2) and lista2[j] in resultado:
            j += 1
    
    return resultado[:N]
def recomendador_hibrido(username, animes_relevantes, animes_desconocidos, N=9):
    """
    Estrategia óptima para producción:
    - Cold start (<10): Top-N
    - Establecidos (10-50): 80% Item-Based + 20% Content-Avanzado
    - Otakus (+50): 100% Item-based
    """
    num_ratings = len(animes_relevantes)
        
    if num_ratings < 10:
        print(f"[Híbrido→TopN]", end=" | ")  
        return recomendador_top_n(username, animes_relevantes, animes_desconocidos, N)
    elif num_ratings < 50:
        print(f"[Híbrido→Item80%+Content20%]", end=" | ") 
        n_item = int(N * 0.8)
        n_content = N - n_item 
        item_recs = recomendador_item_based(username, animes_relevantes, animes_desconocidos, n_item)
        content_recs = recomendador_content_based_avanzado(username, animes_relevantes, animes_desconocidos, n_content * 2)
        return mezclar_recomendaciones(item_recs, content_recs, N)
    else:
        print(f"[Híbrido→Item100%]", end=" | ") 
        return recomendador_item_based(username, animes_relevantes, animes_desconocidos, N)
    

def mezclar_tres_fuentes(lista1, lista2, lista3, N):
    """
    Mezcla tres listas intercalando, sin duplicados.
    Prioriza lista1 > lista2 > lista3.
    """
    resultado = []
    i, j, k = 0, 0, 0
    
    while len(resultado) < N:
        # Rotar entre las tres listas
        if i < len(lista1) and lista1[i] not in resultado:
            resultado.append(lista1[i])
        i += 1
        
        if len(resultado) < N and j < len(lista2) and lista2[j] not in resultado:
            resultado.append(lista2[j])
        j += 1
        
        if len(resultado) < N and k < len(lista3) and lista3[k] not in resultado:
            resultado.append(lista3[k])
        k += 1
        
        # Break si se acabaron todas las listas
        if i >= len(lista1) and j >= len(lista2) and k >= len(lista3):
            break
    
    return resultado[:N]

def recomendador_hibrido_con_tt(username, animes_relevantes, animes_desconocidos, N=9):
    """
    Estrategia híbrida que usa Two-Tower solo cuando realmente funciona mejor:
    
    - Cold start (<10):         100% Top-N
    - Usuarios medios (10-200): 80% Item-Based + 20% Content
    - Power users (200+):       50% Two-Tower + 30% Item-Based + 20% Content

    """
    num_ratings = len(animes_relevantes)
    
    if num_ratings < 10:
        print(f"[Híbrido→TopN]", end=" ")
        return recomendador_top_n(username, animes_relevantes, animes_desconocidos, N)
    
    elif num_ratings < 200:
        print(f"[Híbrido→Item80%+Content20%]", end=" ")
        n_item = int(N * 0.8)
        n_content = N - n_item
        
        item_recs = recomendador_item_based(username, animes_relevantes, animes_desconocidos, n_item * 2)
        content_recs = recomendador_content_based_avanzado(username, animes_relevantes, animes_desconocidos, n_content * 2)
        
        return mezclar_recomendaciones(item_recs, content_recs, N)
    
    else:
        print(f"[Híbrido→TwoTower50%+Item30%+Content20%]", end=" ")
        n_dl = int(N * 0.5)
        n_item = int(N * 0.3)
        n_content = N - n_dl - n_item
        
        try:
            dl_recs = recomendador_two_tower(username, animes_relevantes, animes_desconocidos, n_dl * 2)
        except:
            print(f"[TwoTower-FAIL→Item]", end=" ")
            dl_recs = []
        
        item_recs = recomendador_item_based(username, animes_relevantes, animes_desconocidos, n_item * 2)
        content_recs = recomendador_content_based_avanzado(username, animes_relevantes, animes_desconocidos, n_content * 2)
        
        return mezclar_tres_fuentes(dl_recs, item_recs, content_recs, N)
        

def recomendador_two_tower(username, animes_relevantes, animes_desconocidos, N=9):
    """
    Recomendador basado en Two-Tower Model. Usa embeddings de usuarios y animes para calcular similitud.
    """
    try:
        import tensorflow as tf
        import pickle
        import numpy as np
        from models.features import FeatureProcessor

        # Ruta del modelo guardado
        model_path = os.path.join(os.path.dirname(__file__), 'datos', 'embeddings')
        model_file = os.path.join(model_path, 'two_tower_model.keras')
        processor_file = os.path.join(model_path, 'feature_processor.pkl')

        # Verificar si el modelo existe
        if not os.path.exists(model_file):
            print(f"⚠️  Modelo Two-Tower no encontrado en {model_file}")
            print("   Usando item_based como fallback...")
            return recomendador_item_based(username, animes_relevantes, animes_desconocidos, N)

        # Cargar modelo y feature processor
        model = tf.keras.models.load_model(model_file)

        with open(processor_file, 'rb') as f:
            feature_processor = pickle.load(f)

        # Verificar si el usuario está en el vocabulario
        if username not in feature_processor.user_to_idx:
            print(f"⚠️  Usuario '{username}' no está en el vocabulario del modelo")
            print("   Usando item_based como fallback...")
            return recomendador_item_based(username, animes_relevantes, animes_desconocidos, N)

        # Obtener features del usuario
        user_feats = feature_processor.get_user_features(username)
        if user_feats is None:
            return recomendador_item_based(username, animes_relevantes, animes_desconocidos, N)

        # Preparar inputs del usuario (batch de 1)
        user_inputs = {
            'user_id': np.array([user_feats['user_id']], dtype=np.int32),
            'genre_prefs': np.expand_dims(user_feats['genre_prefs'], 0),
            'avg_rating': np.array([user_feats['avg_rating']], dtype=np.float32),
            'num_ratings': np.array([user_feats['num_ratings']], dtype=np.float32)
        }

        # Obtener embedding del usuario
        user_embedding = model.get_user_embedding(user_inputs, training=False)
        user_embedding = user_embedding.numpy()[0]  # [embedding_dim]

        # Filtrar animes desconocidos que estén en el vocabulario
        candidate_animes = []
        for anime_id in animes_desconocidos:
            if anime_id in feature_processor.anime_to_idx:
                candidate_animes.append(anime_id)

        if not candidate_animes:
            print("⚠️  No hay animes candidatos en el vocabulario")
            return recomendador_item_based(username, animes_relevantes, animes_desconocidos, N)

        # Calcular scores para todos los candidatos
        scores = []

        # Procesar en batches para eficiencia
        batch_size = 512
        for i in range(0, len(candidate_animes), batch_size):
            batch_animes = candidate_animes[i:i+batch_size]

            # Obtener features de animes
            anime_features_batch = []
            valid_animes = []

            for anime_id in batch_animes:
                anime_feats = feature_processor.get_anime_features(anime_id)
                if anime_feats is not None:
                    anime_features_batch.append(anime_feats)
                    valid_animes.append(anime_id)

            if not anime_features_batch:
                continue

            # Preparar inputs de animes
            anime_inputs = {
                'anime_id': np.array([f['anime_id'] for f in anime_features_batch], dtype=np.int32),
                'genres': np.array([f['genres'] for f in anime_features_batch], dtype=np.float32),
                'score': np.array([f['score'] for f in anime_features_batch], dtype=np.float32),
                'members': np.array([f['members'] for f in anime_features_batch], dtype=np.float32),
                'episodes': np.array([f['episodes'] for f in anime_features_batch], dtype=np.float32),
                'year': np.array([f['year'] for f in anime_features_batch], dtype=np.float32),
                'studio_id': np.array([f['studio_id'] for f in anime_features_batch], dtype=np.int32)
            }

            # Obtener embeddings de animes
            anime_embeddings = model.get_anime_embedding(anime_inputs, training=False)
            anime_embeddings = anime_embeddings.numpy()  # [batch, embedding_dim]

            # Calcular similitud (dot product)
            batch_scores = np.dot(anime_embeddings, user_embedding)

            # Guardar scores con anime_id
            for anime_id, score in zip(valid_animes, batch_scores):
                scores.append((anime_id, score))

        # Ordenar por score descendente y tomar top N
        scores.sort(key=lambda x: x[1], reverse=True)
        top_animes = [anime_id for anime_id, score in scores[:N]]
        # Agregar al final de recomendador_two_tower, antes del return:
        print(f"\n[DEBUG {username}] Sample scores: {[f'{s:.3f}' for _, s in scores[:5]]}")
        print(f"[DEBUG {username}] Score range: min={min(s for _, s in scores):.3f}, max={max(s for _, s in scores):.3f}")
        return top_animes

    except Exception as e:
        print(f"❌ Error en recomendador_two_tower: {e}")
        print("   Usando item_based como fallback...")
        return recomendador_item_based(username, animes_relevantes, animes_desconocidos, N)


def genero_principal(anime_id):

    query = "SELECT genres FROM animes WHERE anime_id = ?"
    row = sql_select(query, [anime_id])
    if not row:
        return None
    generos = row[0]["genres"].split(", ")
    return generos[0] if generos else None


def recomendar(username, animes_relevantes=None, animes_desconocidos=None, N=9):
    if not animes_relevantes:
        animes_relevantes = items_valorados(username)

    if not animes_desconocidos:
        animes_desconocidos = items_desconocidos(username)

    # ✅ Determinar qué sistema se usará
    num_ratings = len(animes_relevantes)
    
    if RECOMENDADOR_ACTIVO == "hibrido":
        
        if num_ratings < 10:
            sistema_nombre = "Popular (Top-N)"
        elif num_ratings < 50:
            sistema_nombre = "Híbrido (80% Colaborativo + 20% Contenido)"
        else:
            sistema_nombre = "Colaborativo (Item-Based)"
    elif RECOMENDADOR_ACTIVO == "hibrido_con_tt":
        if num_ratings < 10:
            sistema_nombre = "Popular (Top-N)"
        elif num_ratings < 200:
            sistema_nombre = "Híbrido (80% Colaborativo + 20% Contenido)"
        else:
            sistema_nombre = "Híbrido Avanzado (50% Two-Tower + 30% Colaborativo + 20% Contenido)"
    else:
        # Mapear nombres legibles para otros sistemas
        nombres_sistemas = {
            "azar": "Aleatorio",
            "top_n": "Popular (Top-N)",
            "item_based": "Colaborativo (Item-Based)",
            "two_tower": "Deep Learning (Two-Tower)",
            "content_based": "Basado en Contenido",
            "content_based_avanzado": "Basado en Contenido Avanzado"
        }
        sistema_nombre = nombres_sistemas.get(RECOMENDADOR_ACTIVO, RECOMENDADOR_ACTIVO)

    # Ejecutar la recomendación
    if RECOMENDADOR_ACTIVO == "azar":
        animes = recomendar_azar(username, animes_relevantes, animes_desconocidos, N)
    elif RECOMENDADOR_ACTIVO == "top_n":
        animes = recomendador_top_n(username, animes_relevantes, animes_desconocidos, N)
    elif RECOMENDADOR_ACTIVO == "item_based":
        animes = recomendador_item_based(username, animes_relevantes, animes_desconocidos, N)
    elif RECOMENDADOR_ACTIVO == "two_tower":
        animes = recomendador_two_tower(username, animes_relevantes, animes_desconocidos, N)
    elif RECOMENDADOR_ACTIVO == "content_based":
        animes = recomendador_content_based(username, animes_relevantes, animes_desconocidos, N)
    elif RECOMENDADOR_ACTIVO == "content_based_avanzado":
        animes = recomendador_content_based_avanzado(username, animes_relevantes, animes_desconocidos, N)
    elif RECOMENDADOR_ACTIVO == "hibrido":
        animes = recomendador_hibrido(username, animes_relevantes, animes_desconocidos, N)
    elif RECOMENDADOR_ACTIVO == "hibrido_con_tt":
        animes = recomendador_hibrido_con_tt(username, animes_relevantes, animes_desconocidos, N)
    else:
        raise ValueError(f"Recomendador '{RECOMENDADOR_ACTIVO}' no reconocido")

    return animes, sistema_nombre

def recomendar_contexto(username, anime_id, animes_relevantes=None, animes_desconocidos=None, N=3):

    if not animes_relevantes:
        animes_relevantes = items_valorados(username)

    if not animes_desconocidos:
        animes_desconocidos = items_desconocidos(username)

    # Siempre uso content-based para contexto
    sistema_nombre = "Basado en Contenido (Content-Based)"

    base_recs = recomendador_content_based_avanzado(username, animes_relevantes, animes_desconocidos, N * 10)
    filtrados = filtrar_por_genero(anime_id, base_recs)

    # Excluyo el anime anime principal
    filtrados = [x for x in filtrados if x != anime_id]
    if len(filtrados) < N:
        faltan = [x for x in base_recs if x not in filtrados and x != anime_id]
        random.shuffle(faltan)
        filtrados += faltan[:N - len(filtrados)]

    return filtrados[:N], sistema_nombre


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
    """
    Evalúa el recomendador para un usuario específico.
    Retorna (ndcg_score, tiempo_recomendacion, metadatos)
    """
    start_time = time.time()
    
    animes_relevantes = items_valorados(username)
    animes_desconocidos = items_vistos(username) + items_desconocidos(username)

    # 🔍 DEBUG: Ver información del usuario
    num_ratings = len(animes_relevantes)
    print(f"[{username}] {num_ratings} ratings, {len(animes_desconocidos)} desconocidos", end=" | ")

    random.shuffle(animes_relevantes)

    corte = int(len(animes_relevantes)*0.8)
    animes_relevantes_training = animes_relevantes[:corte]
    animes_relevantes_testing = animes_relevantes[corte:] + animes_desconocidos

    # ⏱️ TIMING: Medir tiempo de recomendación
    rec_start = time.time()
    recomendacion = recomendar(username, animes_relevantes_training, animes_relevantes_testing, 20)
    rec_time = time.time() - rec_start

    # 🔍 DEBUG: Ver cuántas recomendaciones se generaron
    print(f"Recs: {len(recomendacion)}", end=" | ")

    relevance_scores = []
    for id in recomendacion:
        res = sql_select("SELECT score FROM interacciones WHERE username = ? AND anime_id = ?;", [username, id])
        if res is not None and len(res) > 0:
            rating = res[0][0]
        else:
            rating = 0

        relevance_scores.append(rating)
    
    score = metricas.normalized_discounted_cumulative_gain(relevance_scores)
    
    # 🔍 DEBUG: Ver distribución de ratings en las recomendaciones
    num_relevant = sum(1 for r in relevance_scores if r > 0)
    avg_relevant_score = sum(r for r in relevance_scores if r > 0) / num_relevant if num_relevant > 0 else 0
    
    total_time = time.time() - start_time
    
    print(f"Relevantes: {num_relevant}/20 (avg: {avg_relevant_score:.1f}) | Tiempo: {rec_time*1000:.1f}ms | NDCG: {score:.4f}")
    
    # Retornar métricas completas
    return {
        'ndcg': score,
        'rec_time': rec_time,
        'total_time': total_time,
        'num_ratings': num_ratings,
        'num_relevant': num_relevant,
        'avg_relevant_score': avg_relevant_score
    }


if __name__ == '__main__':
    # 🔧 Modo testing: usar conexión directa sin Flask
    print("=" * 80)
    print(f"🧪 EVALUACIÓN DE RECOMENDADOR: {RECOMENDADOR_ACTIVO}")
    print("=" * 80)
    print()
    
    # Inicializar conexión para testing
    init_testing_db()
    
    # Inicializar tablas si es necesario
    init()
    calcular_similitud_items()
    
    # Parámetros de evaluación
    number = 100
    interacciones = 300
    
    print(f"📊 Configuración: {number} usuarios con mínimo {interacciones} interacciones")
    print(f"🎯 Recomendador activo: {RECOMENDADOR_ACTIVO}")
    print()
    
    # Ejecutar tests
    user_animes = sql_select(f"""
        SELECT username 
        FROM usuarios 
        WHERE (SELECT count(*) FROM interacciones WHERE username = usuarios.username) >= {interacciones} 
        LIMIT {number};
    """)
    user_animes = [i["username"] for i in user_animes]

    # Métricas agregadas
    results = []
    ndcg_scores = []
    rec_times = []
    
    # Categorías por número de interacciones
    categories = {
        'cold_start': {'range': (0, 10), 'ndcgs': [], 'times': []},
        'new_user': {'range': (10, 50), 'ndcgs': [], 'times': []},
        'regular': {'range': (50, 200), 'ndcgs': [], 'times': []},
        'power_user': {'range': (200, float('inf')), 'ndcgs': [], 'times': []}
    }
    
    print("-" * 80)
    eval_start = time.time()
    
    for i, user in enumerate(user_animes, 1):
        result = test(user)
        results.append(result)
        ndcg_scores.append(result['ndcg'])
        rec_times.append(result['rec_time'])
        
        # Categorizar usuario
        num_ratings = result['num_ratings']
        for cat_name, cat_data in categories.items():
            if cat_data['range'][0] <= num_ratings < cat_data['range'][1]:
                cat_data['ndcgs'].append(result['ndcg'])
                cat_data['times'].append(result['rec_time'])
                break
        
        # Progress indicator cada 10 usuarios
        if i % 10 == 0:
            print(f"   ... {i}/{number} usuarios evaluados")
    
    total_eval_time = time.time() - eval_start
    
    print("-" * 80)
    print()
    
    # 📊 RESUMEN DE RESULTADOS
    print("=" * 80)
    print("📊 RESULTADOS FINALES")
    print("=" * 80)
    print()
    
    # Métricas generales
    ndcg_mean = sum(ndcg_scores) / len(ndcg_scores)
    ndcg_std = (sum((x - ndcg_mean) ** 2 for x in ndcg_scores) / len(ndcg_scores)) ** 0.5
    
    avg_rec_time = sum(rec_times) / len(rec_times)
    max_rec_time = max(rec_times)
    min_rec_time = min(rec_times)
    
    print(f"🎯 NDCG Global:")
    print(f"   Media:  {ndcg_mean:.6f}")
    print(f"   Std:    {ndcg_std:.6f}")
    print(f"   Min:    {min(ndcg_scores):.6f}")
    print(f"   Max:    {max(ndcg_scores):.6f}")
    print()
    
    print(f"⏱️  Tiempos de Recomendación:")
    print(f"   Promedio:  {avg_rec_time*1000:.2f} ms")
    print(f"   Mínimo:    {min_rec_time*1000:.2f} ms")
    print(f"   Máximo:    {max_rec_time*1000:.2f} ms")
    print(f"   Total:     {total_eval_time:.2f} s")
    print()
    
    # Métricas por categoría
    print(f"📈 Resultados por Categoría de Usuario:")
    print()
    
    for cat_name, cat_data in categories.items():
        if cat_data['ndcgs']:
            cat_ndcg = sum(cat_data['ndcgs']) / len(cat_data['ndcgs'])
            cat_time = sum(cat_data['times']) / len(cat_data['times'])
            min_int, max_int = cat_data['range']
            max_display = f"{max_int}" if max_int != float('inf') else "∞"
            
            print(f"   {cat_name.replace('_', ' ').title():15} ({min_int:3}-{max_display:>3} ratings):")
            print(f"      Usuarios: {len(cat_data['ndcgs']):3}  |  NDCG: {cat_ndcg:.4f}  |  Tiempo: {cat_time*1000:6.2f} ms")
    
    print()
    print("=" * 80)
    
    # 💾 Guardar resultado detallado
    from datetime import datetime
    ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    READ_FILE = os.path.join(ROOT_DIR, "resultados.txt")
    
    with open(READ_FILE, "a", encoding="utf-8") as f:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"\n{timestamp} - {RECOMENDADOR_ACTIVO} - NDCG: {ndcg_mean:.6f} ± {ndcg_std:.6f} - Tiempo: {avg_rec_time*1000:.2f}ms - {number} users +{interacciones} interacciones")
        
        # Agregar desglose por categoría
        for cat_name, cat_data in categories.items():
            if cat_data['ndcgs']:
                cat_ndcg = sum(cat_data['ndcgs']) / len(cat_data['ndcgs'])
                cat_time = sum(cat_data['times']) / len(cat_data['times'])
                f.write(f"\n   - {cat_name}: NDCG {cat_ndcg:.4f}, Tiempo {cat_time*1000:.2f}ms, N={len(cat_data['ndcgs'])}")

    print(f"✅ Resultados guardados en resultados.txt")
    print()
    
    # Cerrar conexión de testing
    close_testing_db()