import sqlite3
from flask import g
import os
from recomendar import get_db


def obtener_estadisticas_usuario(username):
    """
    Obtiene estadísticas completas del perfil del usuario.
    Retorna un diccionario con todas las métricas.
    """
    conn = get_db()
    cursor = conn.cursor()
    
    # === ESTADÍSTICAS BÁSICAS ===
    cursor.execute("""
        SELECT 
            COUNT(*) as total_valorados,
            AVG(score) as promedio,
            MAX(score) as max_score,
            MIN(score) as min_score
        FROM interacciones 
        WHERE username = ? AND score > 0
    """, [username])
    stats_basicas = cursor.fetchone()
    
    # === TOP 10 MEJORES VALORADOS ===
    cursor.execute("""
        SELECT a.*, i.score
        FROM animes a
        JOIN interacciones i ON a.anime_id = i.anime_id
        WHERE i.username = ? AND i.score > 0
        ORDER BY i.score DESC, a.score DESC
        LIMIT 10
    """, [username])
    top_10_mejores = cursor.fetchall()
    
    # === TOP 10 PEORES VALORADOS ===
    cursor.execute("""
        SELECT a.*, i.score
        FROM animes a
        JOIN interacciones i ON a.anime_id = i.anime_id
        WHERE i.username = ? AND i.score > 0
        ORDER BY i.score ASC, a.score ASC
        LIMIT 10
    """, [username])
    top_10_peores = cursor.fetchall()
    
    # === GÉNEROS FAVORITOS (con conteo y promedio) ===
    cursor.execute("""
        SELECT a.genres, i.score
        FROM animes a
        JOIN interacciones i ON a.anime_id = i.anime_id
        WHERE i.username = ? AND i.score > 0
    """, [username])
    
    genero_stats = {}
    for row in cursor.fetchall():
        if row['genres']:
            score = row['score']
            for genero in row['genres'].split(','):
                genero = genero.strip()
                if genero not in genero_stats:
                    genero_stats[genero] = {'count': 0, 'sum': 0, 'avg': 0}
                genero_stats[genero]['count'] += 1
                genero_stats[genero]['sum'] += score
    
    # Calcular promedios y ordenar
    for genero in genero_stats:
        genero_stats[genero]['avg'] = genero_stats[genero]['sum'] / genero_stats[genero]['count']
    
    # Top géneros (por promedio)
    generos_ordenados = sorted(
        genero_stats.items(), 
        key=lambda x: (x[1]['avg'], x[1]['count']), 
        reverse=True
    )
    
    top_generos = generos_ordenados[:10] if len(generos_ordenados) >= 10 else generos_ordenados
    peores_generos = generos_ordenados[-10:] if len(generos_ordenados) >= 10 else []
    peores_generos.reverse()  # Del peor al "menos peor"
    
    # === ESTUDIOS FAVORITOS ===
    cursor.execute("""
        SELECT a.studios, i.score
        FROM animes a
        JOIN interacciones i ON a.anime_id = i.anime_id
        WHERE i.username = ? AND i.score > 0 AND a.studios IS NOT NULL
    """, [username])
    
    studio_stats = {}
    for row in cursor.fetchall():
        if row['studios']:
            score = row['score']
            for studio in row['studios'].split(','):
                studio = studio.strip()
                if studio not in studio_stats:
                    studio_stats[studio] = {'count': 0, 'sum': 0, 'avg': 0}
                studio_stats[studio]['count'] += 1
                studio_stats[studio]['sum'] += score
    
    for studio in studio_stats:
        studio_stats[studio]['avg'] = studio_stats[studio]['sum'] / studio_stats[studio]['count']
    
    top_studios = sorted(
        studio_stats.items(),
        key=lambda x: (x[1]['avg'], x[1]['count']),
        reverse=True
    )[:5]
    
    # === DISTRIBUCIÓN DE SCORES ===
    cursor.execute("""
        SELECT score, COUNT(*) as count
        FROM interacciones
        WHERE username = ? AND score > 0
        GROUP BY score
        ORDER BY score DESC
    """, [username])
    distribucion_scores = cursor.fetchall()
    
    # === AÑOS FAVORITOS ===
    cursor.execute("""
        SELECT a.year, AVG(i.score) as avg_score, COUNT(*) as count
        FROM animes a
        JOIN interacciones i ON a.anime_id = i.anime_id
        WHERE i.username = ? AND i.score > 0 AND a.year IS NOT NULL
        GROUP BY a.year
        ORDER BY avg_score DESC, count DESC
        LIMIT 5
    """, [username])
    top_years = cursor.fetchall()
    
    # === TIPOS DE ANIME FAVORITOS (TV, Movie, OVA, etc.) ===
    cursor.execute("""
        SELECT a.type, AVG(i.score) as avg_score, COUNT(*) as count
        FROM animes a
        JOIN interacciones i ON a.anime_id = i.anime_id
        WHERE i.username = ? AND i.score > 0 AND a.type IS NOT NULL
        GROUP BY a.type
        ORDER BY avg_score DESC, count DESC
    """, [username])
    top_types = cursor.fetchall()
    
    # === PROMEDIO POR RANGO DE EPISODIOS ===
    cursor.execute("""
        SELECT 
            CASE 
                WHEN a.episodes = 1 THEN '1 episodio'
                WHEN a.episodes BETWEEN 2 AND 12 THEN '2-12 episodios'
                WHEN a.episodes BETWEEN 13 AND 26 THEN '13-26 episodios'
                WHEN a.episodes BETWEEN 27 AND 52 THEN '27-52 episodios'
                ELSE '50+ episodios'
            END as rango,
            AVG(i.score) as avg_score,
            COUNT(*) as count
        FROM animes a
        JOIN interacciones i ON a.anime_id = i.anime_id
        WHERE i.username = ? AND i.score > 0 AND a.episodes IS NOT NULL
        GROUP BY rango
        ORDER BY avg_score DESC
    """, [username])
    episodios_stats = cursor.fetchall()
    
    return {
        'basicas': stats_basicas,
        'top_10_mejores': top_10_mejores,
        'top_10_peores': top_10_peores,
        'top_generos': top_generos,
        'peores_generos': peores_generos,
        'top_studios': top_studios,
        'distribucion_scores': distribucion_scores,
        'top_years': top_years,
        'top_types': top_types,
        'episodios_stats': episodios_stats
    }


def obtener_comparacion_global(username):
    """
    Compara las estadísticas del usuario con los promedios globales.
    """
    conn = get_db()
    cursor = conn.cursor()
    
    # Promedio del usuario
    cursor.execute("""
        SELECT AVG(score) as user_avg
        FROM interacciones
        WHERE username = ? AND score > 0
    """, [username])
    user_avg = cursor.fetchone()['user_avg']
    
    # Promedio global
    cursor.execute("""
        SELECT AVG(score) as global_avg
        FROM interacciones
        WHERE score > 0
    """)
    global_avg = cursor.fetchone()['global_avg']
    
    # Diferencia
    diferencia = user_avg - global_avg if user_avg and global_avg else 0
    
    # Género del usuario más valorado vs género global más valorado
    cursor.execute("""
        SELECT a.genres, i.score
        FROM animes a
        JOIN interacciones i ON a.anime_id = i.anime_id
        WHERE i.username = ? AND i.score > 0
    """, [username])
    
    user_genres = {}
    for row in cursor.fetchall():
        if row['genres']:
            for g in row['genres'].split(','):
                g = g.strip()
                user_genres[g] = user_genres.get(g, 0) + 1
    
    top_user_genre = max(user_genres.items(), key=lambda x: x[1])[0] if user_genres else None
    
    return {
        'user_avg': user_avg,
        'global_avg': global_avg,
        'diferencia': diferencia,
        'top_user_genre': top_user_genre,
        'es_mas_critico': diferencia < -0.5,
        'es_mas_generoso': diferencia > 0.5
    }


def obtener_estadisticas_temporales(username):

    conn = get_db()
    cursor = conn.cursor()
    
    # Verificar si existe columna de timestamp
    cursor.execute("PRAGMA table_info(interacciones)")
    columns = [row['name'] for row in cursor.fetchall()]
    
    if 'timestamp' not in columns and 'created_at' not in columns:
        return None
    
    timestamp_col = 'timestamp' if 'timestamp' in columns else 'created_at'
    
    # Evolución temporal (últimos 30 días)
    cursor.execute(f"""
        SELECT 
            DATE({timestamp_col}) as fecha,
            AVG(score) as avg_score,
            COUNT(*) as count
        FROM interacciones
        WHERE username = ? AND score > 0
        GROUP BY fecha
        ORDER BY fecha DESC
        LIMIT 30
    """, [username])
    
    evolucion = cursor.fetchall()
    
    return {
        'evolucion': evolucion,
        'tiene_datos': len(evolucion) > 0
    }