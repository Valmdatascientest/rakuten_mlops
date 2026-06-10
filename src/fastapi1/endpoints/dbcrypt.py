import psycopg2
import os
from passlib.context import CryptContext

# Configurer le contexte de cryptage
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

# Fonction pour hacher un mot de passe
def hash_password(password: str):
    return pwd_context.hash(password)

# Configuration de la connexion à la base de données
def get_db_connection():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url)

    conn = psycopg2.connect(
        dbname=os.getenv("POSTGRES_DB", "rakuten_auth"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=os.getenv("POSTGRES_PORT", "5432"),
    )
    return conn

# Comptes de démonstration. Les mots de passe viennent exclusivement de l'environnement.
users = [
    {"username": "admin", "full_name": "Admin User", "email": "admin@example.com", "password": os.environ["ADMIN_USER_PASSWORD"], "role": "admin"},
    {"username": "dev", "full_name": "Dev User", "email": "dev@example.com", "password": os.environ["DEV_USER_PASSWORD"], "role": "dev"},
    {"username": "client", "full_name": "Client User", "email": "client@example.com", "password": os.environ["CLIENT_USER_PASSWORD"], "role": "client"},
]

# Fonction pour insérer les utilisateurs dans la base de données
def insert_users():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Créer la table si elle n'existe pas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username VARCHAR(50) PRIMARY KEY,
        full_name VARCHAR(100),
        email VARCHAR(100),
        hashed_password VARCHAR(255),
        disabled BOOLEAN,
        role VARCHAR(20)
    )
    """)

    # Insérer les utilisateurs
    for user in users:
        hashed_password = hash_password(user["password"])
        cursor.execute(
            """
            INSERT INTO users (username, full_name, email, hashed_password, disabled, role)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (username) DO UPDATE SET
                full_name = EXCLUDED.full_name,
                email = EXCLUDED.email,
                hashed_password = EXCLUDED.hashed_password,
                disabled = EXCLUDED.disabled,
                role = EXCLUDED.role
            """,
            (user["username"], user["full_name"], user["email"], hashed_password, False, user["role"])
        )

    # Valider les modifications
    conn.commit()
    conn.close()

if __name__ == "__main__":
    insert_users()
