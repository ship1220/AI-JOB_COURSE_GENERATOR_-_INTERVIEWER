from database import SessionLocal
from models import User, InterviewAttempt, SkillProgress

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from dotenv import load_dotenv
import google.genai as genai
import os
import requests
import random


# ---------------- DB ----------------
def get_db():
    return SessionLocal()


# ---------------- ENV ----------------
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")  # you have llama3:latest


# ---------------- APP ----------------
app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------------- DEFAULT QUESTIONS (Final Fallback) ----------------
DEFAULT_QUESTIONS = {
    "intern": [
        "Tell me about yourself.",
        "What is the difference between a process and a thread?",
        "What is normalization in DBMS?",
        "Explain OOP concepts in simple words.",
        "What is an API and why do we use it?"
    ],
    "junior": [
        "Tell me about a project you built and what challenges you faced.",
        "Explain SQL JOINs with an example.",
        "What is deadlock and how can it be prevented?",
        "Explain polymorphism and give a real-world example.",
        "What is HTTP and how is it different from HTTPS?"
    ],
    "mid": [
        "Explain indexing in databases and when it helps.",
        "How do you handle concurrency in an application?",
        "Explain SOLID principles briefly.",
        "What happens when you type a URL in a browser?",
        "How do you optimize a slow SQL query?"
    ],
    "senior": [
        "How would you design a scalable interview preparation platform?",
        "Explain CAP theorem and real-world tradeoffs.",
        "How do you approach performance optimization end-to-end?",
        "How do you handle system failures and retries in production?",
        "Explain database sharding and when you would use it."
    ]
}


# ---------------- INTERVIEW SESSION STORE (in-memory) ----------------
interview_sessions = {}


# ---------------- FALLBACK FUNCTIONS ----------------
def generate_question_with_fallback(role: str, level: str, difficulty: str = "easy") -> str:
    prompt = f"""
You are a mock interviewer.
Role: {role}
Level: {level}
Difficulty: {difficulty}

Ask ONE realistic interview question.
Rules:
- Keep it short and practical.
- Don't mention "difficulty" or "category".
Return ONLY the question text.
""".strip()

    # 1) OLLAMA (Primary)
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False
        }
        r = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=20)
        if r.status_code == 200:
            data = r.json()
            text = data.get("response", "").strip()
            if text:
                return text
    except Exception as e:
        print("Ollama question failed:", str(e))

    # 2) GEMINI (Secondary)
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        text = response.text.strip() if hasattr(response, "text") else ""
        if text:
            return text
    except Exception as e:
        print("Gemini question failed:", str(e))

    # 3) DEFAULT (Final)
    level_key = level.lower().strip()
    if level_key not in DEFAULT_QUESTIONS:
        level_key = "intern"
    return random.choice(DEFAULT_QUESTIONS[level_key])


def generate_feedback_with_fallback(role: str, level: str, answer: str) -> str:
    prompt = f"""
You are an interviewer for {role} ({level}).
Give short constructive feedback for this answer:
"{answer}"

Also give a correct/improved answer in 3-5 lines.
Keep it beginner-friendly.
""".strip()

    # 1) OLLAMA
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False
        }
        r = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=25)
        if r.status_code == 200:
            data = r.json()
            text = data.get("response", "").strip()
            if text:
                return text
    except Exception as e:
        print("Ollama feedback failed:", str(e))

    # 2) GEMINI
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        text = response.text.strip() if hasattr(response, "text") else ""
        if text:
            return text
    except Exception as e:
        print("Gemini feedback failed:", str(e))

    # 3) DEFAULT
    return "Feedback unavailable right now. Improve clarity, add an example, and explain step-by-step."


# ---------------- ROUTES ----------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


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


@app.get("/index", response_class=HTMLResponse)
def interview_page(request: Request):
    username = request.cookies.get("user")
    if not username:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "username": username}
    )


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("user")
    return response


# ---------------- NEW INTERVIEW FLOW ----------------

@app.post("/start_interview/")
async def start_interview(request: Request, role: str = Form(...), level: str = Form(...)):
    username = request.cookies.get("user")
    if not username:
        return {"error": "Not logged in"}

    interview_sessions[username] = {
        "role": role,
        "level": level,
        "round": 1,
        "difficulty": "easy",
        "history": []
    }

    question_text = generate_question_with_fallback(role, level, "easy")
    interview_sessions[username]["history"].append({"question": question_text, "answer": ""})

    return {"question": question_text}


@app.post("/submit_answer/")
async def submit_answer(request: Request, answer: str = Form(...)):
    username = request.cookies.get("user")
    if not username:
        return {"error": "Not logged in"}

    if username not in interview_sessions:
        return {"error": "Interview not started. Please start again."}

    session = interview_sessions[username]
    role = session["role"]
    level = session["level"]
    difficulty = session["difficulty"]

    # Save answer
    session["history"][-1]["answer"] = answer

    # Feedback
    feedback_text = generate_feedback_with_fallback(role, level, answer)

    # Difficulty adaptation (simple)
    low = feedback_text.lower()
    if "incorrect" in low or "wrong" in low or "not correct" in low:
        session["difficulty"] = "easy"
    else:
        if difficulty == "easy":
            session["difficulty"] = "medium"
        elif difficulty == "medium":
            session["difficulty"] = "hard"

    # Next question
    next_question = generate_question_with_fallback(role, level, session["difficulty"])

    session["history"].append({"question": next_question, "answer": ""})
    session["round"] += 1

    # Save attempt in DB
    db = get_db()
    user = db.query(User).filter(User.username == username).first()

    attempt = InterviewAttempt(
        user_id=user.id,
        role=role,
        topic="auto",
        difficulty=session["difficulty"],
        answer=answer,
        feedback=feedback_text
    )
    db.add(attempt)

    # Optional: update skill progress under "auto"
    skill = db.query(SkillProgress).filter(
        SkillProgress.user_id == user.id,
        SkillProgress.skill == "auto"
    ).first()

    if not skill:
        skill = SkillProgress(
            user_id=user.id,
            skill="auto",
            attempts=1,
            weak=False
        )
        db.add(skill)
    else:
        skill.attempts += 1

    if "incorrect" in low or "wrong" in low or "not correct" in low:
        skill.weak = True

    db.commit()

    return {"feedback": feedback_text, "next_question": next_question}


@app.get("/progress", response_class=HTMLResponse)
def progress_page(request: Request):
    db = get_db()
    username = request.cookies.get("user")

    user = db.query(User).filter(User.username == username).first()
    skills = db.query(SkillProgress).filter(SkillProgress.user_id == user.id).all()

    return templates.TemplateResponse(
        "progress.html",
        {"request": request, "username": username, "skills": skills}
    )
