# Progress tracker
#user_progress = {}

from database import SessionLocal
from models import User, InterviewAttempt, SkillProgress
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import google.genai as genai
import os

def get_db():
    return SessionLocal()


# Load env
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# FastAPI setup
app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Temporary user store
#users = {}
#logged_in_users = set()

# Home page
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

# Sign Up page
@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@app.post("/signup", response_class=HTMLResponse)
def signup(request: Request, username: str = Form(...), password: str = Form(...)):
    db = get_db()

    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "message": "User already exists!"}
        )

    new_user = User(username=username, password=password)
    db.add(new_user)
    db.commit()

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "message": "Signup successful! Please login."}
    )
    

# Login page
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    db = get_db()

    user = db.query(User).filter(
        User.username == username,
        User.password == password
    ).first()

    if user:
        response = RedirectResponse(url="/index", status_code=303)
        response.set_cookie(key="user", value=username)
        return response

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "message": "Invalid credentials."}
    )


# Interview page
@app.get("/index", response_class=HTMLResponse)
def interview_page(request: Request):
    username = request.cookies.get("user")
    if not username:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "username": username}
    )

# Logout
@app.get("/logout")
def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("user")
    return response


# ========== GEMINI Q&A ==========
@app.post("/generate_question/")
async def generate_question(
    role: str = Form(...),
    type: str = Form(...),
    topic: str = Form(...),
    difficulty: str = Form(...)
):
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)

        prompt = (
            f"Generate one {difficulty} level {type} very basic 3rd year engineering student type interview question "
            f"focused on {topic} for a {role} role. "
            f"Keep it short, clear, and beginner-friendly — avoid overly complex,vast or theoretical questions."
            f"Don't mention the prompt in the question."
        )

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )

        question_text = response.text if hasattr(response, "text") else "Could not generate question."
        return {"question": question_text.strip()}

    except Exception as e:
        return {"question": f"Error: {str(e)}"}


@app.post("/analyse_answer/")
async def analyse_answer(
    request: Request,
    role: str = Form(...),
    topic: str = Form(...),
    difficulty: str = Form(...),
    answer: str = Form(...)
):
    try:
        db = get_db()
        username = request.cookies.get("user")

        user = db.query(User).filter(User.username == username).first()

        # --- AI FEEDBACK ---
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = (
            f"As an interviewer for a {role} position, "
            f"give short constructive feedback on this answer: '{answer}' "
            f"and also give the correct answer."
        )

        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )

        feedback_text = response.text if hasattr(response, "text") else "No feedback."

        # --- SAVE INTERVIEW ATTEMPT ---
        attempt = InterviewAttempt(
            user_id=user.id,
            role=role,
            topic=topic,
            difficulty=difficulty,
            answer=answer,
            feedback=feedback_text
        )

        db.add(attempt)

        # --- SKILL PROGRESS UPDATE ---
        skill = db.query(SkillProgress).filter(
            SkillProgress.user_id == user.id,
            SkillProgress.skill == topic
        ).first()

        if not skill:
            skill = SkillProgress(
                user_id=user.id,
                skill=topic,
                attempts=1,
                weak=False
            )
            db.add(skill)
        else:
            skill.attempts += 1

        # Simple adaptive rule (SAFE)
        if "incorrect" in feedback_text.lower() or "not correct" in feedback_text.lower():
            skill.weak = True

        db.commit()

        return {"feedback": feedback_text.strip()}

    except Exception as e:
        return {"error": str(e)}

        # Track progress
        username = request.cookies.get("user", "guest")
        if username not in user_progress:
            user_progress[username] = {"questions_answered": 0}
        user_progress[username]["questions_answered"] += 1

        # Return feedback
        return {"feedback": feedback_text.strip()}

    except Exception as e:
        return {"error": str(e)}


@app.get("/progress", response_class=HTMLResponse)
def progress_page(request: Request):
    db = get_db()
    username = request.cookies.get("user")

    user = db.query(User).filter(User.username == username).first()
    skills = db.query(SkillProgress).filter(SkillProgress.user_id == user.id).all()

    return templates.TemplateResponse(
        "progress.html",
        {
            "request": request,
            "username": username,
            "skills": skills
        }
    )


