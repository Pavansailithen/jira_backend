import os
import shutil
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Form, File, UploadFile
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models import User
from app.auth.auth_utils import (
    hash_password,
    verify_password,
    create_access_token,
    validate_password,
    validate_lowercase_email
)
from app.auth.dependencies import get_current_user
from app.schemas.user_schema import UserResponse
from app.schemas.auth_schema import LoginRequest, SignupRequest
from app.constants import ErrorMessages
from app.constants import ADMIN, DEVELOPER, MASTER_ADMIN, TESTER
from app.exceptions import raise_bad_request, raise_unauthorized, raise_forbidden
from app.utils.logger import get_logger

logger = get_logger(__name__)

from app.config.settings import settings

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/signup")
def signup(
    request: SignupRequest,
    db: Session = Depends(get_db)
):
    """
    Registers a new user with the specified role.
    Checks if email already exists and enforces validation.
    """
    # Use localized list for signup restrictions if needed, or general constant
    allowed_signup_roles = [DEVELOPER, TESTER]
    
    if request.role not in allowed_signup_roles:
        if request.role == ADMIN:
            raise_forbidden("ADMIN role cannot be chosen during signup")
        request.role = DEVELOPER
    
    if db.query(User).filter(User.email == request.email).first():
        raise_bad_request(ErrorMessages.EMAIL_EXISTS)
    
    validate_password(request.password)
    validate_lowercase_email(request.email)
    
    user = User(
        username=request.username,
        email=request.email,
        hashed_password=hash_password(request.password),
        role=request.role
    )
    
    db.add(user)
    
    db.flush() # Ensure ID is generated
    db.refresh(user)
    
    return {"message": "User registered successfully"}

@router.get("/users", response_model=List[UserResponse])
def get_all_users(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Retrieve all users to populate assignee lists"""
    # Filtering out the hardcoded admin email if it exists in settings/logic
    # Keeping logic as is but note duplication of concept
    return db.query(User).filter(User.email != "admin@jira.local").all()

def perform_login(email: str, password: str, db: Session):
    """
    Validates credentials and generates an access token.
    Handles view mode logic for promoted admins.
    """
    logger.info(f"Attempting login for email: {email}")
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            logger.warning(f"Login failed: User not found for email {email}")
            raise_unauthorized(ErrorMessages.INVALID_CREDENTIALS)
        
        logger.info(f"User found: {user.username} (ID: {user.id}). Verifying password...")
        if not verify_password(password, user.hashed_password):
            logger.warning(f"Login failed: Invalid password for email {email}")
            raise_unauthorized(ErrorMessages.INVALID_CREDENTIALS)
        
        # Default view_mode based on role on fresh login
        if not user.is_master_admin:
            # If user is an ADMIN (promoted), default to ADMIN mode. Otherwise DEVELOPER.
            user.view_mode = ADMIN if user.role == ADMIN else DEVELOPER
            db.flush()
            logger.info(f"View mode set to {user.view_mode} for user {user.username}")
        
        logger.info("Generating access token...")
        token = create_access_token({
            "user_id": user.id,
            "role": user.role
        })
        
        logger.info(f"Login successful for user: {user.username}")
        return {
            "access_token": token,
            "token_type": "bearer",
            "user_id": user.id,
            "role": user.role,
            "view_mode": user.view_mode,
            "is_master_admin": user.is_master_admin
        }
    except Exception as e:
        logger.error(f"Error during perform_login for {email}: {str(e)}")
        raise

@router.post("/login")
def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticates a user and returns a JWT token.
    """
    return perform_login(request.email, request.password, db)

@router.post("/token")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """OAuth2 compatible token login, for Swagger UI"""
    return perform_login(form_data.username, form_data.password, db)

@router.get("/me", response_model=UserResponse)
def my_profile(user: User = Depends(get_current_user)):
    """
    Retrieves the current authenticated user's profile.
    """
    return user

@router.post("/switch-mode")
def switch_mode(
    mode: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Switches the current user's view mode (Admin/Developer).
    Master Admin cannot switch modes.
    """
    if user.is_master_admin:
        raise_bad_request("Master Admin cannot switch modes")
    
    if mode not in [ADMIN, DEVELOPER]:
        raise_bad_request(ErrorMessages.INVALID_MODE)
        
    user.view_mode = mode
    
    return {"message": f"Switched to {mode} mode", "view_mode": user.view_mode}

@router.post("/verify-password")
def verify_current_password(
    password: str = Form(...),
    user: User = Depends(get_current_user)
):
    """
    Verifies the current user's password (e.g., before sensitive actions).
    """
    if not verify_password(password, user.hashed_password):
        raise_unauthorized(ErrorMessages.INVALID_PASSWORD)
    return {"valid": True}

@router.put("/me", response_model=UserResponse)
def update_profile(
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    current_password: Optional[str] = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Updates the calling user's profile (Username, Password).
    Requires current password to change password.
    """
    if username:
        user.username = username
    
    if password:
        if not current_password:
            raise_bad_request("Current password is required to set a new password")
        if not verify_password(current_password, user.hashed_password):
            raise_unauthorized(ErrorMessages.INVALID_CURRENT_PASSWORD)
            
        validate_password(password)
        user.hashed_password = hash_password(password)
    
  
    db.flush() # Apply changes to generate updated timestamps if any
    db.refresh(user)
    return user

@router.post("/me/avatar")
def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Uploads a profile picture for the current user.
    """
    UPLOAD_DIR = os.path.join(settings.UPLOAD_DIR, "avatars")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    file_ext = file.filename.split(".")[-1]
    filename = f"user_{user.id}_{int(datetime.utcnow().timestamp())}.{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    user.profile_pic = f"/uploads/avatars/{filename}"
    
    return {"profile_pic": user.profile_pic}

@router.delete("/me/profile-pic")
def delete_profile_pic(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Removes the current user's profile picture.
    """
    user.profile_pic = None
    
    return {"message": "Profile picture removed"}

@router.post("/logout")
def logout():
    return {"message": "Logout successful"}