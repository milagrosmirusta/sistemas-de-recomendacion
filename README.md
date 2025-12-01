# 🎌 Sistema de Recomendación de Anime

Sistema de recomendación de anime basado en datos scrapeados de MyAnimeList (MAL), implementando múltiples estrategias desde filtrado colaborativo item-based hasta redes neuronales Two-Tower, con un sistema híbrido adaptativo que evoluciona según la experiencia del usuario.

## 🎯 Características Principales

- **Estrategias de Recomendación**: Desde popularidad hasta deep learning
- **Sistema Híbrido Adaptativo**: Evoluciona según el número de valoraciones del usuario
- **Recomendaciones Contextuales**: "Quienes vieron X también vieron..." (content-based)
- **Two-Tower Neural Network**: Modelo de embeddings para power users (200+ ratings)
- **Interfaz Intuitiva**: Sistema de valoración 1-10 con filtrado por género
- **Análisis de Perfil**: Estadísticas detalladas de gustos y preferencias
- **Sistema de Reset**: Restauración a estado original

---

## 📊 Datos del Proyecto

### Fuentes de Datos (Scrapeadas de MAL)

- **Animes**: 8,763 animes (emitidos desde 1980-2025)
- **Usuarios**: 20,965 usuarios (desde reviews del top 100)
- **Interacciones**: 1,058,897 ratings
- **Tabla `top_animes`**: Ordenada por cantidad de rankings y score
- **Tabla `item_similitudes`**: 150,499 pares de animes similares

---

## 🏗️ Arquitectura del Sistema

### Estrategias de Recomendación Implementadas

#### 1. **Popularidad (Top-N)**
```python
RECOMENDADOR_ACTIVO = "top_n"
```

- **Método**: Ordena por score y members de MAL
- **Cuándo se usa**: Usuario nuevo (0 valoraciones) o en híbrido (<10 ratings)
- **Tabla**: `top_animes` (pre-calculada en `init()`)
- **Implementación**: `recomendador_top_n()`

**Ventajas**:
- Siempre funciona (no requiere datos del usuario)
- Recomendaciones de alta calidad (animes populares)
- Extremadamente rápido (tabla pre-ordenada)

**Desventajas**:
- Cero personalización
- Mismas recomendaciones para todos

---

#### 2. **Filtrado Colaborativo Item-Based** ⭐
```python
RECOMENDADOR_ACTIVO = "item_based"
```

- **Método**: "Si te gustó A y B, te gustará C porque otros usuarios que vieron A y B también vieron C"
- **Similitud**: Co-ocurrencia (count de usuarios que vieron ambos con score >= 7)
- **Tabla**: `item_similitudes` (150,499 pares pre-calculados)
- **Implementación**: `recomendador_item_based()`

**Algoritmo de pre-cálculo**:

```python
def calcular_similitud_items():
    """
    Crea tabla con pares de animes similares.
    Similitud = cantidad de usuarios que valoraron AMBOS con score >= 7
    """
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
        HAVING COUNT(*) >= 100  -- Threshold: mínimo 100 usuarios en común
        ORDER BY similitud DESC;
    """)
```

**Ventajas**:
- Muy preciso con suficientes datos (+10 ratings)
- Escalable (pre-cálculo offline)
- Rápido en runtime (~10-50ms)

**Desventajas**:
- Requiere tabla pre-calculada (150K pares)
- No funciona bien con cold start (<10 ratings)

---

#### 3. **Content-Based (Basado en Contenido)**
```python
RECOMENDADOR_ACTIVO = "content_based"
```

- **Método**: Recomienda animes con géneros similares
- **Features**: Géneros (top 3 más frecuentes del usuario)
- **Implementación**: `recomendador_content_based()`

**Algoritmo**:

```python
def recomendador_content_based(username, animes_relevantes, animes_desconocidos, N=9):
    """
    1. Obtiene animes que le gustaron al usuario (score >= 7)
    2. Cuenta frecuencia de géneros en esos animes
    3. Identifica top 3 géneros favoritos
    4. Busca animes con esos géneros (LIKE query)
    5. Ordena por score MAL y members
    """
    # Contar géneros favoritos
    genre_counts = {}
    for row in user_liked_animes:
        for genre in row['genres'].split(','):
            genre_counts[genre] = genre_counts.get(genre, 0) + 1
    
    # Top 3 géneros
    top_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    
    # Buscar animes similares
    query = """
        SELECT DISTINCT a.anime_id, a.score, a.members
        FROM animes a
        WHERE (a.genres LIKE ? OR a.genres LIKE ? OR a.genres LIKE ?)
          AND a.anime_id NOT IN (?)
          AND a.anime_id IN (?)
        ORDER BY a.score DESC, a.members DESC
        LIMIT ?
    """
```

**Ventajas**:
- Funciona desde el primer rating
- Explicable (géneros favoritos)
- No requiere otros usuarios

**Desventajas**:
- Baja serendipity (solo recomienda lo similar)
- No captura patrones complejos

---

#### 4. **Content-Based Avanzado**
```python
RECOMENDADOR_ACTIVO = "content_based_avanzado"
```

- **Método**: Content-based con múltiples features
- **Features**: Géneros (peso 3) + Studios (peso 2) + Score range (peso 1)
- **Optimización**: Una query masiva + scoring en memoria
- **Implementación**: `recomendador_content_based_avanzado()`

**Algoritmo mejorado**:

```python
def recomendador_content_based_avanzado(username, animes_relevantes, animes_desconocidos, N=9):
    # 1. Analizar preferencias (géneros, studios, scores)
    # ...
    
    # 2. UNA query masiva para obtener TODOS los candidatos
    query = f"""
        SELECT anime_id, genres, studios, score
        FROM animes
        WHERE anime_id IN ({placeholders})
    """
    candidates = sql_select(query, animes_desconocidos)
    
    # 3. Calcular similarity en memoria (súper rápido)
    for anime in candidates:
        similarity = 0
        
        # Score por géneros (peso: 3)
        if anime['genres']:
            for genre in anime_genres:
                if genre in top_genres:
                    similarity += 3
        
        # Score por studios (peso: 2)
        if anime['studios']:
            for studio in anime_studios:
                if studio in top_studios:
                    similarity += 2
        
        # Score por rating similar (peso: 1)
        if abs(anime['score'] - avg_score) <= 1.5:
            similarity += 1
    
    # 4. Ordenar por similarity
    candidate_scores.sort(key=lambda x: x[1], reverse=True)
    return candidate_scores[:N]
```

**Optimización clave**:

```
❌ ANTES (N queries):
for anime_id in animes_desconocidos:  # 5000 animes
    query = "SELECT * FROM animes WHERE anime_id = ?"
    # → 5000 queries → ~2000ms

✅ AHORA (1 query + scoring en Python):
query = "SELECT * FROM animes WHERE anime_id IN (?, ?, ...)"
# → 1 query (~50ms) + scoring en memoria (~10ms) = 60ms
```

**Ventajas**:
- Más preciso que content-based simple
- Considera múltiples features
- Más rápido (optimización de queries)

---

#### 5. **Two-Tower Neural Network** 
```python
RECOMENDADOR_ACTIVO = "two_tower"
```

- **Método**: Embeddings de usuarios y animes con red neuronal
- **Arquitectura**: Dos torres (user + anime) + dot product
- **Cuándo se usa**: Solo en híbrido avanzado para power users (200+ ratings)
- **Implementación**: `recomendador_two_tower()` + modelo TensorFlow

**Arquitectura del modelo**:

```
User Tower:
  user_id → Embedding(embedding_dim)
  genre_prefs → Dense layer
  avg_rating → Normalizado
  num_ratings → Normalizado
  → Concatenate → Dense → user_embedding

Anime Tower:
  anime_id → Embedding(embedding_dim)
  genres_encoded → Dense layer
  studios_encoded → Dense layer
  score → Normalizado
  → Concatenate → Dense → anime_embedding

Score Prediction:
  dot_product(user_embedding, anime_embedding) → score
```

**Features utilizadas**:

```python
# User features
user_feats = {
    'user_id': int,              # Índice en vocabulario
    'genre_prefs': [float],      # Vector de preferencias de género
    'avg_rating': float,         # Rating promedio del usuario
    'num_ratings': int           # Cantidad de ratings
}

# Anime features
anime_feats = {
    'anime_id': int,             # Índice en vocabulario
    'genres': [float],           # One-hot de géneros
    'studios': [float],          # One-hot de studios
    'score': float,              # Score MAL normalizado
    'year': float,               # Año normalizado
    'episodes': float            # Episodios normalizado
}
```

**Recomendación en runtime**:

```python
def recomendador_two_tower(username, animes_relevantes, animes_desconocidos, N=9):
    """
    1. Cargar modelo TensorFlow pre-entrenado
    2. Obtener embedding del usuario (una vez)
    3. Para cada anime candidato:
       - Obtener embedding del anime
       - Calcular dot product con user embedding
    4. Retornar top N por score
    """
    # Cargar modelo
    model = tf.keras.models.load_model('two_tower_model.keras')
    
    # Obtener embedding del usuario
    user_embedding = model.get_user_embedding(user_inputs)
    
    # Calcular scores para candidatos (en batches)
    scores = []
    for batch_animes in batches(candidate_animes, 512):
        anime_embeddings = model.get_anime_embeddings(anime_inputs_batch)
        batch_scores = np.dot(anime_embeddings, user_embedding)
        scores.extend(batch_scores)
    
    # Top N
    return top_n_by_score(candidate_animes, scores, N)
```

**Ventajas**:
- Captura patrones complejos no lineales
- Aprende de toda la comunidad
- Muy preciso para power users

**Desventajas**:
- Requiere entrenamiento (modelo separado)
- Lento en runtime (~200ms por request)
- Solo funciona para usuarios/animes en vocabulario (que suelen ser los power users)

---

### Sistema Híbrido Adaptativo ⭐

El sistema por defecto que evoluciona con el usuario:

```python
RECOMENDADOR_ACTIVO = "hibrido"  # ← Recomendado
```

#### Estrategia Progresiva

```python
def recomendador_hibrido(username, animes_relevantes, animes_desconocidos, N=9):
    """
    Estrategia óptima para producción:
    - Cold start (<10):         100% Top-N
    - Establecidos (10-50):     80% Item-Based + 20% Content-Avanzado
    - Otakus (50+):            100% Item-based
    """
    num_ratings = len(animes_relevantes)
    
    if num_ratings < 10:
        return recomendador_top_n(username, animes_relevantes, animes_desconocidos, N)
    
    elif num_ratings < 50:
        n_item = int(N * 0.8)
        n_content = N - n_item
        
        item_recs = recomendador_item_based(username, animes_relevantes, animes_desconocidos, n_item)
        content_recs = recomendador_content_based_avanzado(username, animes_relevantes, animes_desconocidos, n_content * 2)
        
        return mezclar_recomendaciones(item_recs, content_recs, N)
    
    else:  # 50+
        return recomendador_item_based(username, animes_relevantes, animes_desconocidos, N)
```

**Función de mezcla**:

```python
def mezclar_recomendaciones(lista1, lista2, N):
    """
    Intercala dos listas sin duplicados.
    Prioriza lista1 (item-based) sobre lista2 (content).
    
    Ejemplo:
    lista1 = [A, B, C, D]
    lista2 = [X, B, Y, Z]
    resultado = [A, X, B, Y, C, Z, D]  (B solo aparece una vez)
    """
    resultado = []
    i, j = 0, 0
    
    while len(resultado) < N and (i < len(lista1) or j < len(lista2)):
        if i < len(lista1) and lista1[i] not in resultado:
            resultado.append(lista1[i])
        i += 1
        
        if len(resultado) < N and j < len(lista2) and lista2[j] not in resultado:
            resultado.append(lista2[j])
        j += 1
    
    return resultado[:N]
```

#### ¿Por qué esta progresión?

| Ratings | Estrategia | Razón |
|---------|-----------|-------|
| 0-9 | Top N (100%) | Sin datos → popularidad global funciona mejor |
| 10-49 | Item 80% + Content 20% | Suficientes datos para colaborativo, pero aún agregar diversidad |
| 50+ | Item Based (100%) | Datos suficientes para colaborativo puro (mejor precisión) |

---

### Sistema Híbrido con Two-Tower (Avanzado)

```python
RECOMENDADOR_ACTIVO = "hibrido_con_tt"
```

**Estrategia para power users**:

```python
def recomendador_hibrido_con_tt(username, animes_relevantes, animes_desconocidos, N=9):
    """
    - Cold start (<10):         100% Top-N
    - Usuarios medios (10-200): 80% Item-Based + 20% Content
    - Power users (200+):       50% Two-Tower + 30% Item-Based + 20% Content
    """
    num_ratings = len(animes_relevantes)
    
    if num_ratings < 10:
        return recomendador_top_n(...)
    
    elif num_ratings < 200:
        return mezcla_item_content(...)
    
    else:  # 200+
        n_dl = int(N * 0.5)
        n_item = int(N * 0.3)
        n_content = N - n_dl - n_item
        
        dl_recs = recomendador_two_tower(username, ..., n_dl * 2)
        item_recs = recomendador_item_based(username, ..., n_item * 2)
        content_recs = recomendador_content_based_avanzado(username, ..., n_content * 2)
        
        return mezclar_tres_fuentes(dl_recs, item_recs, content_recs, N)
```

**¿Por qué 200+ para Two-Tower?**

Two-Tower aprende patrones complejos que solo se manifiestan con MUCHOS datos:

```
100 ratings:  Usuario ve muchos géneros → patrones ambiguos
200+ ratings: Usuario tiene preferencias claras → Two-Tower destaca
```

---

## 📁 Estructura del Proyecto

```
my_anime_list/
├── app.py                      # Flask app principal
├── recomendar.py               # Lógica de recomendación 
├── estadisticas.py             # Análisis de perfil de usuario
├── metricas.py                 # NDCG para evaluación
├── templates/                  # Templates HTML
│   ├── login.html             
│   ├── recomendaciones.html   
│   ├── recomendaciones_animes.html  # Recomendaciones contextuales
│   ├── perfil.html            
│   └── admin_reset.html       
├── static/                     
│   └── img/
│       └── background-login.jpg
├── datos/                      
│   ├── mal.db                 # Base de datos SQLite (1.06M interacciones)
│   ├── mal_original.db        # Backup automático
│   └── embeddings/            # Modelo Two-Tower (opcional)
│       ├── two_tower_model.keras
│       └── feature_processor.pkl
├── models/                     # Entrenamiento Two-Tower (opcional)
│   ├── training.py
│   ├── features.py
│   └── dos_torres.py
└── train.py
└── resultados.txt              # Log de evaluaciones NDCG
```

---

## Instalación

### 1. Requisitos

```bash
pip install -r requirements.txt
```

### 2. Inicializar Base de Datos

```bash
python recomendar.py
```

Al ejecutar por primera vez, se crean automáticamente:
- Tabla `top_animes` (si no existe)
- Tabla `item_similitudes` (si no existe - tarda ~5 minutos)

### 3. Ejecutar Aplicación

```bash
python app.py
```

Aplicación disponible en: `http://localhost:5000`

---

## Uso del Sistema

### Interfaz Web

#### 1. Login
- Ingresa tu username
- Se crea automáticamente si no existe

#### 2. Recomendaciones Principales
- **Visualización**: Grid de 9 animes
- **Filtrado por género**: Dropdown opcional
- **Valoración**: 1-10 por anime
- **Indicador de sistema**: Muestra qué estrategia se usa

#### 3. Recomendaciones Contextuales

Click en un anime → "Quienes vieron X también vieron..."

**Método**: 100% content-based avanzado + filtrado por género compartido

```python
def recomendar_contexto(username, anime_id, N=3):
    """
    1. Usa content_based_avanzado para generar candidatos
    2. Filtra por géneros compartidos con anime_id
    3. Excluye el anime principal
    """
    base_recs = recomendador_content_based_avanzado(username, ..., N * 10)
    filtrados = filtrar_por_genero(anime_id, base_recs)
    return filtrados[:N]
```

#### 4. Perfil de Usuario

- **Estadísticas básicas**: Total valorados, promedio, max, min
- **Comparación global**: Tu promedio vs. todos
- **Distribución de scores**: Histograma
- **Top géneros**: Favoritos y menos gustados
- **Top estudios**: Estudios favoritos
- **Top años**: Años de producción favoritos
- **Top 10 mejores/peores**: Animes mejor y peor valorados

#### 5. Reset de Usuario

Elimina todas tus valoraciones (vuelve a 0).

#### 6. Admin Reset (Factory Reset)

- **Acceso**: `/admin/factory_reset`
- **Contraseña**: `123456`
- **Acción**: Restaura TODA la BD al estado original

---

## 🧪 Testing y Evaluación

### Ejecutar Evaluación

```bash
python recomendar.py
```

### Configuración

```python
# En recomendar.py (línea 13)
RECOMENDADOR_ACTIVO = "hibrido"  # Estrategia a evaluar

# En main (líneas 980-981)
number = 500         # Número de usuarios
interacciones = 5    # Mínimo de interacciones
```

### Metodología

1. **Train/Test Split**: 80% training, 20% testing
2. **Random shuffle**: Evitar sesgo temporal
3. **Métrica**: NDCG@20
4. **Categorización**: Cold start, new user, regular, power user

### Output de Ejemplo

```bash
================================================================================
🧪 EVALUACIÓN DE RECOMENDADOR: hibrido
================================================================================

📊 Configuración: 500 usuarios con mínimo 5 interacciones
🎯 Recomendador activo: hibrido

--------------------------------------------------------------------------------
[user_1234] 45 ratings, 8500 desconocidos | [Híbrido→Item80%+Content20%] | Recs: 20 | Relevantes: 7/20 (avg: 7.8) | Tiempo: 34.5ms | NDCG: 0.3122
[user_5678] 12 ratings, 8600 desconocidos | [Híbrido→Item80%+Content20%] | Recs: 20 | Relevantes: 4/20 (avg: 7.2) | Tiempo: 28.3ms | NDCG: 0.2145
...
--------------------------------------------------------------------------------

```

### Métricas Calculadas

#### NDCG (Normalized Discounted Cumulative Gain)

**Intuición**: ¿Qué tan bien ordena el recomendador los items relevantes?

```python
def normalized_discounted_cumulative_gain(relevance_scores):
    """
    relevance_scores: [9, 2, 8, 0, 7]  # Ratings reales en orden de recomendación
    
    DCG = sum(relevance_i / log2(i + 2))
    IDCG = DCG del ordenamiento perfecto [9, 8, 7, 2, 0]
    NDCG = DCG / IDCG
    
    Rango: 0.0 (peor) a 1.0 (perfecto)
    """
    dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(relevance_scores))
    idcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(sorted(relevance_scores, reverse=True)))
    return dcg / idcg if idcg > 0 else 0.0
```

---

## ⚙️ Configuración Avanzada

### Cambiar Estrategia por Defecto

```python
# En recomendar.py (línea 13)
RECOMENDADOR_ACTIVO = "hibrido"

# Opciones disponibles:
"azar"                          # Baseline aleatorio
"top_n"                         # Popularidad
"item_based"                    # Colaborativo item-based
"content_based"                 # Content simple (géneros)
"content_based_avanzado"        # Content multi-feature
"hibrido"                       # Adaptativo (RECOMENDADO) ⭐
"hibrido_con_tt"                # Con Two-Tower para power users
"two_tower"                     # Solo deep learning
```

### Ajustar Umbrales del Híbrido

```python
def recomendador_hibrido(username, animes_relevantes, animes_desconocidos, N=9):
    num_ratings = len(animes_relevantes)
    
    # Puedes cambiar estos valores:
    if num_ratings < 10:        # ← Cambiar a 5 o 15
        return recomendador_top_n(...)
    
    elif num_ratings < 50:      # ← Cambiar a 30 o 70
        # 80% item + 20% content
        ...
    
    else:
        return recomendador_item_based(...)
```

### Threshold de Similitud Item-Based

```python
# En calcular_similitud_items() (línea 250)
HAVING COUNT(*) >= 100  # ← Cambiar threshold

# Valores recomendados:
50:  Más pares (más cobertura, menos precisión)
100: Balance (default)
200: Menos pares (menos cobertura, más precisión)
```

---

## 🔧 Detalles Técnicos


### Gestión de Conexiones

**Patrón Flask `g`**:

```python
def get_db():
    """Una conexión por request"""
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE_FILE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def teardown_db(exception):
    """Cierre automático"""
    db = g.pop('db', None)
    if db is not None:
        db.close()
```

**Ventajas**:
- Thread-safe (cada request tiene su conexión)
- Sin memory leaks (cierre automático)
- Eficiente (una conexión por request, no por query)

---

## 🌐 Deploy en PythonAnywhere

### Archivos a Subir

```
/home/tu_usuario/anime-recommender/
├── app.py
├── recomendar.py
├── estadisticas.py
├── metricas.py
├── templates/
├── static/
└── datos/
    ├── mal.db
    └── mal_original.db
```

---

## 📝 Licencia y Autoría

**Proyecto académico** - Universidad de Buenos Aires
- **Curso**: Sistemas de Recomendación
- **Año**: 2025
- **Alumna**: Milagros Irusta


### ¿El modelo Two-Tower es necesario?

**No**, es **opcional**. El sistema funciona perfectamente sin él:

```python
# Sin Two-Tower
RECOMENDADOR_ACTIVO = "hibrido"  # Usa: top_n + item_based + content_based

# Con Two-Tower (power users)
RECOMENDADOR_ACTIVO = "hibrido_con_tt"  # Añade deep learning para 200+
```

### ¿Cómo entreno el modelo Two-Tower?

Si quieres usar deep learning:

```bash
cd models/
python train.py
```

Esto genera:
- `datos/embeddings/two_tower_model.keras`
- `datos/embeddings/feature_processor.pkl`

**Advertencia**: Requiere TensorFlow y puede tardar horas en entrenar.

---

## Contribuciones

Este es un proyecto académico, pero sugerencias y feedback son bienvenidos:
- Abrir un **Issue** para bugs o preguntas
- Enviar **Pull Request** con mejoras
💚
