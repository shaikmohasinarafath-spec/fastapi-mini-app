from pathlib import Path

import fitz
import pytesseract
from pdf2image import convert_from_path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import (
    create_access_token,
    hash_password,
    verify_password,
    verify_token,
)
from database import Base, engine, get_db
from models import Material, User


# --------------------------------------------------
# TESSERACT OCR CONFIGURATION
# --------------------------------------------------

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


# --------------------------------------------------
# APP SETUP
# --------------------------------------------------

app = FastAPI(title="FastAPI Mini App")

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

Base.metadata.create_all(bind=engine)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login"
)


# --------------------------------------------------
# REQUEST MODELS
# --------------------------------------------------

class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


# --------------------------------------------------
# AUTHENTICATION
# --------------------------------------------------

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    payload = verify_token(token)

    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )

    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )

    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    return user


# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "message": "FastAPI Mini App is running"
    }


# --------------------------------------------------
# CREATE USER
# --------------------------------------------------

@app.post("/users")
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(
        (User.username == user_data.username)
        | (User.email == user_data.email)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Username or email already exists"
        )

    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hash_password(
            user_data.password
        )
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "message": "User created successfully",
        "user_id": user.id,
        "username": user.username,
        "email": user.email
    }


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@app.post("/auth/login")
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.username == login_data.username
    ).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    if not verify_password(
        login_data.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    access_token = create_access_token(
        {"sub": str(user.id)}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


# --------------------------------------------------
# PDF UPLOAD
# --------------------------------------------------

@app.post("/materials/upload")
async def upload_material(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required"
        )

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed"
        )

    safe_filename = Path(file.filename).name

    # Add user ID to avoid filename conflicts
    file_path = (
        UPLOAD_DIR
        / f"{current_user.id}_{safe_filename}"
    )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty"
        )

    file_path.write_bytes(content)

    material = Material(
        filename=safe_filename,
        filepath=str(file_path),
        owner_id=current_user.id
    )

    db.add(material)
    db.commit()
    db.refresh(material)

    return {
        "message": "PDF uploaded successfully",
        "material_id": material.id,
        "filename": material.filename
    }


# --------------------------------------------------
# PDF TEXT EXTRACTION + OCR
# --------------------------------------------------

def extract_pdf_text(pdf_path: str) -> str:
    text_parts = []

    try:
        # --------------------------------------------------
        # STEP 1: NORMAL PDF TEXT EXTRACTION
        # --------------------------------------------------

        document = fitz.open(pdf_path)

        for page in document:
            page_text = page.get_text()

            if page_text:
                text_parts.append(page_text)

        document.close()

        extracted_text = "\n".join(
            text_parts
        ).strip()

        # If normal text exists, return it
        if extracted_text:
            return extracted_text

        # --------------------------------------------------
        # STEP 2: OCR FALLBACK
        # For scanned/image-based PDFs
        # --------------------------------------------------

        images = convert_from_path(
            pdf_path,
            dpi=200
        )

        for image in images:
            ocr_text = pytesseract.image_to_string(
                image
            )

            if ocr_text.strip():
                text_parts.append(ocr_text)

        return "\n".join(text_parts).strip()

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not read PDF: {str(e)}"
        )


# --------------------------------------------------
# SUMMARY
# --------------------------------------------------

@app.post("/materials/{material_id}/summary")
def create_summary(
    material_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    material = db.query(Material).filter(
        Material.id == material_id,
        Material.owner_id == current_user.id
    ).first()

    if not material:
        raise HTTPException(
            status_code=404,
            detail="Material not found"
        )

    text = extract_pdf_text(
        material.filepath
    )

    if not text:
        raise HTTPException(
            status_code=400,
            detail="No text found in PDF"
        )

    material.extracted_text = text

    # Simple local summary
    clean_text = " ".join(
        text.split()
    )

    sentences = [
        sentence.strip()
        for sentence in clean_text.split(".")
        if sentence.strip()
    ]

    summary = ". ".join(
        sentences[:5]
    )

    if summary:
        summary += "."

    material.summary = summary

    db.commit()
    db.refresh(material)

    return {
        "material_id": material.id,
        "summary": summary
    }


# --------------------------------------------------
# QUIZ GENERATION
# --------------------------------------------------

@app.post("/materials/{material_id}/quiz")
def create_quiz(
    material_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    material = db.query(Material).filter(
        Material.id == material_id,
        Material.owner_id == current_user.id
    ).first()

    if not material:
        raise HTTPException(
            status_code=404,
            detail="Material not found"
        )

    text = material.extracted_text

    if not text:
        text = extract_pdf_text(
            material.filepath
        )

    if not text:
        raise HTTPException(
            status_code=400,
            detail="No text available for quiz generation"
        )

    words = [
        word.strip(
            ".,!?;:()[]{}"
        )
        for word in text.split()
        if len(
            word.strip(
                ".,!?;:()[]{}"
            )
        ) > 5
    ]

    questions = []

    for word in words[:5]:
        questions.append({
            "question": (
                f"What is the significance of "
                f"'{word}' in the material?"
            ),
            "answer": word
        })

    return {
        "material_id": material.id,
        "quiz": questions
    }