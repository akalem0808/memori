# Add these endpoints to memory_api.py

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login and get access token"""
    user = authenticate_user(users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "permissions": user.permissions},
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """Get current user information"""
    return current_user

# Add these permission dependencies to the secure endpoints:

# Example for read-only endpoint
@app.get("/memories", response_model=List[MemoryResponse], dependencies=[Depends(READ_PERMISSION)])

# Example for write endpoint
@app.post("/memories/text", response_model=MemoryResponse, status_code=201, dependencies=[Depends(WRITE_PERMISSION)])

# Example for admin endpoint
@app.delete("/memories/{memory_id}", dependencies=[Depends(ADMIN_PERMISSION)])
