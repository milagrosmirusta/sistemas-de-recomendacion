import numpy as np
import tensorflow as tf
from tensorflow import keras
import os
from datetime import datetime

from .features import FeatureProcessor
from .dos_torres import create_model


def prepare_batch_data(user_ids, anime_ids, labels, user_features_cache, anime_features_cache, num_genres):
    """
    Prepara un batch de datos usando features pre-cacheadas.

    Args:
        user_ids: array de índices de usuarios
        anime_ids: array de índices de animes
        labels: array de labels (0 o 1)
        user_features_cache: dict con features pre-computadas de usuarios
        anime_features_cache: dict con features pre-computadas de animes
        num_genres: número de géneros

    Returns:
        (inputs_dict, labels_array)
    """
    # Arrays para user features
    genre_prefs_batch = []
    avg_rating_batch = []
    num_ratings_batch = []

    # Arrays para anime features
    genres_batch = []
    score_batch = []
    members_batch = []
    episodes_batch = []
    year_batch = []
    studio_id_batch = []

    # Default values
    default_genre_prefs = np.zeros(num_genres, dtype=np.float32)

    # Procesar cada sample usando cache
    for user_idx, anime_idx in zip(user_ids, anime_ids):
        # User features desde cache
        user_feats = user_features_cache.get(user_idx)
        if user_feats:
            genre_prefs_batch.append(user_feats['genre_prefs'])
            avg_rating_batch.append(user_feats['avg_rating'])
            num_ratings_batch.append(user_feats['num_ratings'])
        else:
            genre_prefs_batch.append(default_genre_prefs)
            avg_rating_batch.append(0.0)
            num_ratings_batch.append(0.0)

        # Anime features desde cache
        anime_feats = anime_features_cache.get(anime_idx)
        if anime_feats:
            genres_batch.append(anime_feats['genres'])
            score_batch.append(anime_feats['score'])
            members_batch.append(anime_feats['members'])
            episodes_batch.append(anime_feats['episodes'])
            year_batch.append(anime_feats['year'])
            studio_id_batch.append(anime_feats['studio_id'])
        else:
            genres_batch.append(default_genre_prefs)
            score_batch.append(0.5)
            members_batch.append(0.0)
            episodes_batch.append(0.0)
            year_batch.append(0.5)
            studio_id_batch.append(0)

    # Crear el diccionario de inputs
    inputs = {
        'user_id': np.array(user_ids, dtype=np.int32),
        'genre_prefs': np.array(genre_prefs_batch, dtype=np.float32),
        'avg_rating': np.array(avg_rating_batch, dtype=np.float32),
        'num_ratings': np.array(num_ratings_batch, dtype=np.float32),
        'anime_id': np.array(anime_ids, dtype=np.int32),
        'genres': np.array(genres_batch, dtype=np.float32),
        'score': np.array(score_batch, dtype=np.float32),
        'members': np.array(members_batch, dtype=np.float32),
        'episodes': np.array(episodes_batch, dtype=np.float32),
        'year': np.array(year_batch, dtype=np.float32),
        'studio_id': np.array(studio_id_batch, dtype=np.int32)
    }

    return inputs, labels


class DataGenerator(keras.utils.Sequence):
    """
    Generador de datos para entrenamiento eficiente con features pre-cacheadas.
    """

    def __init__(self, user_ids, anime_ids, labels, user_features_cache, anime_features_cache, num_genres, batch_size=256, shuffle=True):
        self.user_ids = user_ids
        self.anime_ids = anime_ids
        self.labels = labels
        self.user_features_cache = user_features_cache
        self.anime_features_cache = anime_features_cache
        self.num_genres = num_genres
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.indices = np.arange(len(self.labels))

        if self.shuffle:
            np.random.shuffle(self.indices)

    def __len__(self):
        """Número de batches por época."""
        return int(np.ceil(len(self.labels) / self.batch_size))

    def __getitem__(self, index):
        """Genera un batch de datos."""
        # Índices del batch
        start_idx = index * self.batch_size
        end_idx = min((index + 1) * self.batch_size, len(self.labels))
        batch_indices = self.indices[start_idx:end_idx]

        # Datos del batch
        batch_user_ids = self.user_ids[batch_indices]
        batch_anime_ids = self.anime_ids[batch_indices]
        batch_labels = self.labels[batch_indices]

        # Preparar features usando cache
        inputs, labels = prepare_batch_data(
            batch_user_ids,
            batch_anime_ids,
            batch_labels,
            self.user_features_cache,
            self.anime_features_cache,
            self.num_genres
        )

        return inputs, labels

    def on_epoch_end(self):
        """Mezcla los datos al final de cada época."""
        if self.shuffle:
            np.random.shuffle(self.indices)


def train_model(epochs=10, batch_size=256, validation_split=0.2, embedding_dim=64, save_path=None):
    """
    Entrena el modelo Two-Tower desde cero.

    Args:
        epochs: número de épocas
        batch_size: tamaño del batch
        validation_split: porcentaje para validación
        embedding_dim: dimensión de embeddings
        save_path: ruta para guardar el modelo (default: data/embeddings/)

    Returns:
        (model, history, feature_processor)
    """
    print("=" * 60)
    print("🚀 ENTRENAMIENTO TWO-TOWER MODEL")
    print("=" * 60)

    # Ruta de guardado
    if save_path is None:
        base_dir = os.path.dirname(os.path.dirname(__file__))
        save_path = os.path.join(base_dir, 'datos', 'embeddings')

    os.makedirs(save_path, exist_ok=True)

    # 1. Feature processor
    print("\n1️⃣ Inicializando Feature Processor...")
    feature_processor = FeatureProcessor()
    feature_processor.build_vocabularies()

    # 2. Preparar datos de entrenamiento
    print("\n2️⃣ Preparando datos de entrenamiento...")
    user_ids, anime_ids, labels = feature_processor.prepare_training_data(
        min_interactions=20,
        negative_ratio=1
    )

    # Train/validation split
    n_samples = len(labels)
    n_val = int(n_samples * validation_split)
    indices = np.random.permutation(n_samples)

    val_indices = indices[:n_val]
    train_indices = indices[n_val:]

    train_user_ids = user_ids[train_indices]
    train_anime_ids = anime_ids[train_indices]
    train_labels = labels[train_indices]

    val_user_ids = user_ids[val_indices]
    val_anime_ids = anime_ids[val_indices]
    val_labels = labels[val_indices]

    print(f"   - Train samples: {len(train_labels)}")
    print(f"   - Validation samples: {len(val_labels)}")

    # 3. Pre-cachear features (OPTIMIZACIÓN)
    print("\n3️⃣ Pre-cacheando features...")
    print("   ⚡ Esto acelerará DRAMÁTICAMENTE el entrenamiento")

    # Obtener usuarios y animes únicos
    unique_user_ids = np.unique(user_ids)
    unique_anime_ids = np.unique(anime_ids)

    print(f"   - Usuarios únicos: {len(unique_user_ids)}")
    print(f"   - Animes únicos: {len(unique_anime_ids)}")

    # Mapeos inversos
    idx_to_user = {idx: user for user, idx in feature_processor.user_to_idx.items()}
    idx_to_anime = {idx: anime for anime, idx in feature_processor.anime_to_idx.items()}

    # Cache de user features
    print("   - Cacheando features de usuarios...")
    user_features_cache = {}
    for user_idx in unique_user_ids:
        username = idx_to_user.get(user_idx)
        if username:
            user_feats = feature_processor.get_user_features(username)
            if user_feats:
                user_features_cache[user_idx] = user_feats

    # Cache de anime features
    print("   - Cacheando features de animes...")
    anime_features_cache = {}
    for anime_idx in unique_anime_ids:
        anime_id = idx_to_anime.get(anime_idx)
        if anime_id:
            anime_feats = feature_processor.get_anime_features(anime_id)
            if anime_feats:
                anime_features_cache[anime_idx] = anime_feats

    print(f"   ✅ Features cacheadas en memoria ({len(user_features_cache)} usuarios, {len(anime_features_cache)} animes)")

    # 4. Crear generadores de datos
    print("\n4️⃣ Creando generadores de datos...")
    train_generator = DataGenerator(
        train_user_ids, train_anime_ids, train_labels,
        user_features_cache, anime_features_cache, feature_processor.num_genres,
        batch_size=batch_size, shuffle=True
    )

    val_generator = DataGenerator(
        val_user_ids, val_anime_ids, val_labels,
        user_features_cache, anime_features_cache, feature_processor.num_genres,
        batch_size=batch_size, shuffle=False
    )

    # 5. Crear modelo
    print("\n5️⃣ Creando modelo...")
    model = create_model(
        num_users=feature_processor.num_users,
        num_animes=feature_processor.num_animes,
        num_genres=feature_processor.num_genres,
        num_studios=feature_processor.num_studios,
        embedding_dim=embedding_dim
    )

    print(f"   - Usuarios: {feature_processor.num_users}")
    print(f"   - Animes: {feature_processor.num_animes}")
    print(f"   - Géneros: {feature_processor.num_genres}")
    print(f"   - Studios: {feature_processor.num_studios}")
    print(f"   - Embedding dim: {embedding_dim}")

    # 6. Callbacks
    print("\n6️⃣ Configurando callbacks...")
    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor='val_loss',
            patience=3,
            restore_best_weights=True
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.5,
            patience=2,
            min_lr=1e-6
        ),
        keras.callbacks.ModelCheckpoint(
            filepath=os.path.join(save_path, 'best_model.keras'),
            monitor='val_auc',
            save_best_only=True,
            mode='max'
        )
    ]

    # 7. Entrenar
    print("\n7️⃣ Entrenando modelo...")
    print("-" * 60)

    history = model.fit(
        train_generator,
        validation_data=val_generator,
        epochs=epochs,
        callbacks=callbacks,
        verbose=1
    )

    # 8. Guardar modelo y feature processor
    print("\n8️⃣ Guardando modelo y configuración...")
    model.save(os.path.join(save_path, 'two_tower_model.keras'))

    # Guardar vocabularios del feature processor
    import pickle
    with open(os.path.join(save_path, 'feature_processor.pkl'), 'wb') as f:
        pickle.dump(feature_processor, f)

    print(f"   ✅ Modelo guardado en: {save_path}")

    # 9. Resumen final
    print("\n" + "=" * 60)
    print("✅ ENTRENAMIENTO COMPLETADO")
    print("=" * 60)

    best_epoch = np.argmax(history.history['val_auc']) + 1
    best_auc = max(history.history['val_auc'])
    best_acc = history.history['val_accuracy'][best_epoch - 1]

    print(f"Mejor época: {best_epoch}/{epochs}")
    print(f"Mejor AUC: {best_auc:.4f}")
    print(f"Accuracy: {best_acc:.4f}")

    return model, history, feature_processor


if __name__ == '__main__':
    # Entrenar modelo
    model, history, fp = train_model(
        epochs=20,
        batch_size=256,
        validation_split=0.2,
        embedding_dim=64
    )
