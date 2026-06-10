from fastapi import FastAPI, Depends, HTTPException, status, APIRouter, Request, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
import psycopg2
import os
from psycopg2.extras import DictCursor
from passlib.context import CryptContext

app = FastAPI()
router = APIRouter()
templates = Jinja2Templates(directory="src/fastapi1/endpoints")

# Connexion à la base PostgreSQL
def get_db_connection():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url)

    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DB", "rakuten_auth"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=os.getenv("POSTGRES_PORT", "5432"),
    )

# Modèles Pydantic
class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    role: str

class UserInDB(User):
    hashed_password: str

# Sécurité
SECRET_KEY = os.environ["SECRET_KEY"]
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Fonctions sécurité
def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Token invalide")
        return get_user(username)
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")

# Récupération utilisateur depuis la base
def get_user(username: str):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return UserInDB(
            username=user["username"],
            full_name=user["full_name"],
            email=user["email"],
            hashed_password=user["hashed_password"],
            disabled=user["disabled"],
            role=user["role"]
        )
    return None

# Dépendances de sécurité

async def get_current_user(token: str = Depends(oauth2_scheme)):
    return decode_access_token(token)

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Utilisateur désactivé")
    return current_user



# Routes
@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user(form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Nom d'utilisateur ou mot de passe incorrect")

    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/test-login", response_class=HTMLResponse)
async def read_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.get("/users/me")
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

@router.get("/admin-only")
async def admin_only(current_user: User = Depends(get_current_active_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès réservé à l'admin")
    return {"message": "Bienvenue, admin."}

@router.get("/dev-only")
async def dev_only(current_user: User = Depends(get_current_active_user)):
    if current_user.role != "dev":
        raise HTTPException(status_code=403, detail="Accès réservé aux développeurs")
    return {"message": "Bienvenue, développeur."}

@router.get("/client-only")
async def client_only(current_user: User = Depends(get_current_active_user)):
    if current_user.role != "client":
        raise HTTPException(status_code=403, detail="Accès réservé aux clients")
    return {"message": "Bienvenue, client."}

@router.get("/test")
def hello():
    return {"message": "Hello, Rakuten World!"}


@router.get("/", include_in_schema=False)
async def root_redirect():
    print(">>> Redirection depuis / vers /test-login")
    return RedirectResponse(url="/test-login")

@app.middleware("http")
async def redirect_unauthorized_requests(request: Request, call_next):
    response = await call_next(request)
    print(f">>> Requête {request.url.path}, status: {response.status_code}")
    if response.status_code in (401, 403, 404):
        return RedirectResponse(url="/test-login")
    return response

app.include_router(router)
