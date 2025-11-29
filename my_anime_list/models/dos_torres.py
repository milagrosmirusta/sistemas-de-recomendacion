import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import numpy as np
from tensorflow.keras.utils import register_keras_serializable



@register_keras_serializable(package="MyAnimeRecommender")
class TwoTowerModel(keras.Model):
    """
    Modelo Two-Tower para recomendación.

    Args:
        num_users: número total de usuarios
        num_animes: número total de animes
        num_genres: número de géneros únicos
        num_studios: número de studios únicos
        embedding_dim: dimensión de los embeddings (default: 64)
    """

    def __init__(self, num_users, num_animes, num_genres, num_studios, embedding_dim=64, **kwargs):
        super(TwoTowerModel, self).__init__(**kwargs)

        # 🔑 CRÍTICO: Guardar estos valores como atributos
        self.num_users = num_users
        self.num_animes = num_animes
        self.num_genres = num_genres
        self.num_studios = num_studios
        self.embedding_dim = embedding_dim

        # --- TORRE DE USUARIO --- #
        self.user_embedding = layers.Embedding(
            input_dim=num_users,
            output_dim=embedding_dim,
            embeddings_regularizer=keras.regularizers.l2(1e-6),
            name='user_embedding'
        )

        self.user_dense1 = layers.Dense(128, activation='relu', name='user_dense1')
        self.user_dropout1 = layers.Dropout(0.3)
        self.user_dense2 = layers.Dense(embedding_dim, activation='relu', name='user_dense2')
        self.user_dropout2 = layers.Dropout(0.2)
        self.user_normalization = layers.BatchNormalization(name='user_norm')

        # --- TORRE DE ANIME --- #
        self.anime_embedding = layers.Embedding(
            input_dim=num_animes,
            output_dim=embedding_dim,
            embeddings_regularizer=keras.regularizers.l2(1e-6),
            name='anime_embedding'
        )

        self.studio_embedding = layers.Embedding(
            input_dim=num_studios + 1,
            output_dim=16,
            name='studio_embedding'
        )

        self.anime_dense1 = layers.Dense(128, activation='relu', name='anime_dense1')
        self.anime_dropout1 = layers.Dropout(0.3)
        self.anime_dense2 = layers.Dense(embedding_dim, activation='relu', name='anime_dense2')
        self.anime_dropout2 = layers.Dropout(0.2)
        self.anime_normalization = layers.BatchNormalization(name='anime_norm')

        # --- CAPA FINAL --- #
        self.dot_product = layers.Dot(axes=1, normalize=True, name='similarity')
        # Transformar dot product normalizado [-1, 1] a probabilidad [0, 1]
        # Formula: (dot + 1) / 2
        self.to_probability = layers.Lambda(lambda x: (x + 1.0) / 2.0, name='to_probability')



    def get_config(self):
        """Configuración para serialización."""
        config = super().get_config()
        config.update({
            'num_users': self.num_users,
            'num_animes': self.num_animes,
            'num_genres': self.num_genres,
            'num_studios': self.num_studios,
            'embedding_dim': self.embedding_dim
        })
        return config

    @classmethod
    def from_config(cls, config):
        """Reconstrucción desde config."""
        return cls(**config)

    def call(self, inputs, training=None):
        # ... tu código existente SIN CAMBIOS ...
        user_emb = self.user_embedding(inputs['user_id'])
        user_features = tf.concat([
            user_emb,
            inputs['genre_prefs'],
            tf.expand_dims(inputs['avg_rating'], -1),
            tf.expand_dims(inputs['num_ratings'], -1)
        ], axis=-1)

        user_tower = self.user_dense1(user_features)
        user_tower = self.user_dropout1(user_tower, training=training)
        user_tower = self.user_dense2(user_tower)
        user_tower = self.user_dropout2(user_tower, training=training)
        user_tower = self.user_normalization(user_tower, training=training)

        anime_emb = self.anime_embedding(inputs['anime_id'])
        studio_emb = self.studio_embedding(inputs['studio_id'])

        anime_features = tf.concat([
            anime_emb,
            inputs['genres'],
            studio_emb,
            #tf.expand_dims(inputs['score'], -1),
            tf.expand_dims(inputs['members'], -1),
            tf.expand_dims(inputs['episodes'], -1),
            tf.expand_dims(inputs['year'], -1)
        ], axis=-1)

        anime_tower = self.anime_dense1(anime_features)
        anime_tower = self.anime_dropout1(anime_tower, training=training)
        anime_tower = self.anime_dense2(anime_tower)
        anime_tower = self.anime_dropout2(anime_tower, training=training)
        anime_tower = self.anime_normalization(anime_tower, training=training)

        similarity = self.dot_product([user_tower, anime_tower])
        probability = self.to_probability(similarity)
        return probability

    def get_user_embedding(self, inputs, training=False):
        # ... SIN CAMBIOS ...
        user_emb = self.user_embedding(inputs['user_id'])
        user_features = tf.concat([
            user_emb,
            inputs['genre_prefs'],
            tf.expand_dims(inputs['avg_rating'], -1),
            tf.expand_dims(inputs['num_ratings'], -1)
        ], axis=-1)

        user_tower = self.user_dense1(user_features)
        user_tower = self.user_dropout1(user_tower, training=training)
        user_tower = self.user_dense2(user_tower)
        user_tower = self.user_dropout2(user_tower, training=training)
        user_tower = self.user_normalization(user_tower, training=training)
        return user_tower

    def get_anime_embedding(self, inputs, training=False):
        # ... SIN CAMBIOS ...
        anime_emb = self.anime_embedding(inputs['anime_id'])
        studio_emb = self.studio_embedding(inputs['studio_id'])

        anime_features = tf.concat([
            anime_emb,
            inputs['genres'],
            studio_emb,
            #tf.expand_dims(inputs['score'], -1), se lo saco para evitar feature leaking
            tf.expand_dims(inputs['members'], -1),
            tf.expand_dims(inputs['episodes'], -1),
            tf.expand_dims(inputs['year'], -1)
        ], axis=-1)

        anime_tower = self.anime_dense1(anime_features)
        anime_tower = self.anime_dropout1(anime_tower, training=training)
        anime_tower = self.anime_dense2(anime_tower)
        anime_tower = self.anime_dropout2(anime_tower, training=training)
        anime_tower = self.anime_normalization(anime_tower, training=training)
        return anime_tower


def create_model(num_users, num_animes, num_genres, num_studios, embedding_dim=64):
    # ... SIN CAMBIOS ...
    model = TwoTowerModel(
        num_users=num_users,
        num_animes=num_animes,
        num_genres=num_genres,
        num_studios=num_studios,
        embedding_dim=embedding_dim
    )

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=0.001),
        loss=keras.losses.BinaryCrossentropy(from_logits=False),
        metrics=[
            keras.metrics.BinaryAccuracy(name='accuracy'),
            keras.metrics.AUC(name='auc')
        ]
    )

    return model