import argparse
import sys
import os

# Agregar el directorio actual al path para imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.training import train_model


def main():
    parser = argparse.ArgumentParser(
        description='Entrena el modelo Two-Tower para recomendación de animes'
    )

    parser.add_argument(
        '--epochs',
        type=int,
        default=10,
        help='Número de épocas de entrenamiento (default: 10)'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=256,
        help='Tamaño del batch (default: 256)'
    )

    parser.add_argument(
        '--validation-split',
        type=float,
        default=0.2,
        help='Porcentaje de datos para validación (default: 0.2)'
    )

    parser.add_argument(
        '--embedding-dim',
        type=int,
        default=64,
        help='Dimensión de los embeddings (default: 64)'
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("🚀 ENTRENAMIENTO TWO-TOWER MODEL")
    print("=" * 60)
    print(f"\nParámetros:")
    print(f"  - Épocas: {args.epochs}")
    print(f"  - Batch size: {args.batch_size}")
    print(f"  - Validation split: {args.validation_split}")
    print(f"  - Embedding dimension: {args.embedding_dim}")
    print()

    try:
        model, history, feature_processor = train_model(
            epochs=args.epochs,
            batch_size=args.batch_size,
            validation_split=args.validation_split,
            embedding_dim=args.embedding_dim
        )

        print("\n" + "=" * 60)
        print(" ENTRENAMIENTO COMPLETADO EXITOSAMENTE")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\n Entrenamiento interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error durante el entrenamiento: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()