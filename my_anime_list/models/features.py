import numpy as np
import sqlite3
from collections import Counter, defaultdict
import os

DATABASE_FILE = os.path.dirname(os.path.dirname(__file__)) + "/datos/mal.db"


class FeatureProcessor:
    """Procesa y normaliza features de usuarios y animes."""

    def __init__(self, db_path=None):
        self.db_path = db_path or DATABASE_FILE
        self.genre_to_idx = {}
        self.studio_to_idx = {}
        self.user_to_idx = {}
        self.anime_to_idx = {}
        self.num_genres = 0
        self.num_studios = 0
        self.num_users = 0
        self.num_animes = 0

        # Estadísticas para normalización
        self.max_score = 10.0
        self.max_members = 1.0
        self.max_episodes = 1.0
        self.max_year = 2024
        self.min_year = 1960

    def _get_connection(self):
        """Crea conexión a la base de datos."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def build_vocabularies(self):
        """Construye vocabularios de géneros, studios, usuarios y animes."""
        conn = self._get_connection()
        cur = conn.cursor()

        # Géneros únicos
        genres_set = set()
        cur.execute("SELECT genres FROM animes WHERE genres IS NOT NULL")
        for row in cur.fetchall():
            if row['genres']:
                for genre in row['genres'].split(','):
                    genres_set.add(genre.strip())

        self.genre_to_idx = {g: i for i, g in enumerate(sorted(genres_set))}
        self.num_genres = len(self.genre_to_idx)

        # Studios únicos
        studios_set = set()
        cur.execute("SELECT studios FROM animes WHERE studios IS NOT NULL")
        for row in cur.fetchall():
            if row['studios']:
                for studio in row['studios'].split(','):
                    studios_set.add(studio.strip())

        self.studio_to_idx = {s: i for i, s in enumerate(sorted(studios_set))}
        self.num_studios = len(self.studio_to_idx)

        # Usuarios
        cur.execute("SELECT DISTINCT username FROM usuarios ORDER BY username")
        users = [row['username'] for row in cur.fetchall()]
        self.user_to_idx = {u: i for i, u in enumerate(users)}
        self.num_users = len(self.user_to_idx)

        # Animes
        cur.execute("SELECT DISTINCT anime_id FROM animes ORDER BY anime_id")
        animes = [row['anime_id'] for row in cur.fetchall()]
        self.anime_to_idx = {a: i for i, a in enumerate(animes)}
        self.num_animes = len(self.anime_to_idx)

        # Estadísticas para normalización
        cur.execute("SELECT MAX(members) as max_m, MAX(episodes) as max_e FROM animes")
        row = cur.fetchone()
        self.max_members = float(row['max_m']) if row['max_m'] else 1.0
        self.max_episodes = float(row['max_e']) if row['max_e'] else 1.0

        conn.close()

        print(f"✅ Vocabularios construidos:")
        print(f"   - Géneros: {self.num_genres}")
        print(f"   - Studios: {self.num_studios}")
        print(f"   - Usuarios: {self.num_users}")
        print(f"   - Animes: {self.num_animes}")

    def get_user_features(self, username):
        """
        Extrae features de un usuario.

        Returns:
            dict con:
            - user_id: índice del usuario
            - genre_prefs: array de preferencias de género (normalizado)
            - avg_rating: rating promedio
            - num_ratings: número de ratings
        """
        conn = self._get_connection()
        cur = conn.cursor()

        if username not in self.user_to_idx:
            return None

        user_id = self.user_to_idx[username]

        # Obtener interacciones del usuario
        cur.execute("""
            SELECT i.score, a.genres
            FROM interacciones i
            JOIN animes a ON i.anime_id = a.anime_id
            WHERE i.username = ? AND i.score > 0
        """, (username,))

        interactions = cur.fetchall()

        if not interactions:
            # Usuario sin ratings
            return {
                'user_id': user_id,
                'genre_prefs': np.zeros(self.num_genres, dtype=np.float32),
                'avg_rating': 0.0,
                'num_ratings': 0.0
            }

        # Calcular preferencias de género (ponderadas por rating)
        genre_scores = defaultdict(list)
        ratings = []

        for row in interactions:
            score = row['score']
            ratings.append(score)

            if row['genres']:
                for genre in row['genres'].split(','):
                    genre = genre.strip()
                    if genre in self.genre_to_idx:
                        genre_scores[genre].append(score)

        # Vector de preferencias de género
        genre_prefs = np.zeros(self.num_genres, dtype=np.float32)
        for genre, scores in genre_scores.items():
            idx = self.genre_to_idx[genre]
            genre_prefs[idx] = np.mean(scores) / self.max_score  # Normalizar

        avg_rating = np.mean(ratings) / self.max_score
        num_ratings = len(ratings) / 100.0  # Normalizar (aprox.)

        conn.close()

        return {
            'user_id': user_id,
            'genre_prefs': genre_prefs,
            'avg_rating': np.float32(avg_rating),
            'num_ratings': np.float32(min(num_ratings, 1.0))
        }

    def get_anime_features(self, anime_id):
        """
        Extrae features de un anime.

        Returns:
            dict con:
            - anime_id: índice del anime
            - genres: multi-hot encoding de géneros
            - score: score normalizado
            - members: members normalizado
            - episodes: episodios normalizado
            - year: año normalizado
            - studio: índice del studio principal
        """
        conn = self._get_connection()
        cur = conn.cursor()

        if anime_id not in self.anime_to_idx:
            return None

        anime_idx = self.anime_to_idx[anime_id]

        cur.execute("""
            SELECT genres, score, members, episodes, year, studios
            FROM animes
            WHERE anime_id = ?
        """, (anime_id,))

        row = cur.fetchone()
        conn.close()

        if not row:
            return None

        # Multi-hot encoding de géneros
        genres_vector = np.zeros(self.num_genres, dtype=np.float32)
        if row['genres']:
            for genre in row['genres'].split(','):
                genre = genre.strip()
                if genre in self.genre_to_idx:
                    genres_vector[self.genre_to_idx[genre]] = 1.0

        # Score normalizado
        score = float(row['score']) / self.max_score if row['score'] else 0.5

        # Members normalizado (log scale)
        members = float(row['members']) if row['members'] else 0
        members_norm = np.log1p(members) / np.log1p(self.max_members)

        # Episodes normalizado
        episodes = float(row['episodes']) if row['episodes'] else 0
        episodes_norm = min(episodes / self.max_episodes, 1.0)

        # Year normalizado
        year = 0.5  # default
        if row['year']:
            try:
                year_val = int(row['year'])
                year = (year_val - self.min_year) / (self.max_year - self.min_year)
            except:
                pass

        # Studio (solo el primero)
        studio_idx = 0
        if row['studios']:
            studio = row['studios'].split(',')[0].strip()
            studio_idx = self.studio_to_idx.get(studio, 0)

        return {
            'anime_id': anime_idx,
            'genres': genres_vector,
            'score': np.float32(score),
            'members': np.float32(members_norm),
            'episodes': np.float32(episodes_norm),
            'year': np.float32(year),
            'studio_id': studio_idx
        }

    def prepare_training_data(self, min_interactions=20, negative_ratio=1):
        """
        Prepara datos de entrenamiento con samples positivos y negativos.

        Args:
            min_interactions: mínimo de interacciones para incluir un usuario
            negative_ratio: ratio de negativos por cada positivo

        Returns:
            (user_ids, anime_ids, labels)
        """
        conn = self._get_connection()
        cur = conn.cursor()

        print("📊 Preparando datos de entrenamiento...")

        # Obtener usuarios con suficientes interacciones
        cur.execute("""
            SELECT username, COUNT(*) as cnt
            FROM interacciones
            WHERE score > 0
            GROUP BY username
            HAVING cnt >= ?
        """, (min_interactions,))

        active_users = [row['username'] for row in cur.fetchall()]
        print(f"   - Usuarios activos: {len(active_users)}")

        user_ids = []
        anime_ids = []
        labels = []

        for username in active_users:
            user_idx = self.user_to_idx[username]
            
            # Samples positivos (score >= 7)
            cur.execute("""
                SELECT anime_id
                FROM interacciones
                WHERE username = ? AND score >= 7
            """, (username,))

            positive_animes = [row['anime_id'] for row in cur.fetchall()]

            # Samples negativos REALES (score < 5)
            cur.execute("""
                SELECT anime_id
                FROM interacciones
                WHERE username = ? AND score > 0 AND score < 5
                ORDER BY RANDOM()
                LIMIT ?
            """, (username, len(positive_animes) * negative_ratio))

            negative_animes = [row['anime_id'] for row in cur.fetchall()]

            # Si no hay suficientes negativos reales, completar con algunos random
            if len(negative_animes) < len(positive_animes) * negative_ratio:
                needed = len(positive_animes) * negative_ratio - len(negative_animes)
                
                # Obtener animes que NO vio (como fallback)
                cur.execute("""
                    SELECT a.anime_id
                    FROM animes a
                    LEFT JOIN interacciones i ON a.anime_id = i.anime_id AND i.username = ?
                    WHERE i.anime_id IS NULL
                    ORDER BY RANDOM()
                    LIMIT ?
                """, (username, needed))
                
                negative_animes.extend([row['anime_id'] for row in cur.fetchall()])

            # Agregar samples positivos
            for anime_id in positive_animes:
                if anime_id in self.anime_to_idx:
                    user_ids.append(user_idx)
                    anime_ids.append(self.anime_to_idx[anime_id])
                    labels.append(1)

            # Agregar samples negativos
            for anime_id in negative_animes:
                if anime_id in self.anime_to_idx:
                    user_ids.append(user_idx)
                    anime_ids.append(self.anime_to_idx[anime_id])
                    labels.append(0)

        conn.close()

        print(f"   - Samples totales: {len(labels)}")
        print(f"   - Positivos: {sum(labels)}")
        print(f"   - Negativos: {len(labels) - sum(labels)}")

        return (
            np.array(user_ids, dtype=np.int32),
            np.array(anime_ids, dtype=np.int32),
            np.array(labels, dtype=np.float32)
        )