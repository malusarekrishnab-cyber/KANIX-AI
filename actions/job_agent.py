import os
import json
import time
from pathlib import Path

def get_base_dir():
    return Path(__file__).resolve().parent.parent

BASE_DIR = get_base_dir()
DATA_DIR = BASE_DIR / "config"
TRACKER_FILE = DATA_DIR / "job_applications.json"

AUTO_APPLY_ALL_ELIGIBLE = os.environ.get("AUTO_APPLY_ALL_ELIGIBLE", "false").lower() == "true"
JOB_MIN_MATCH_SCORE = float(os.environ.get("JOB_MIN_MATCH_SCORE", "75.0"))

class JobTracker:
    def __init__(self):
        DATA_DIR.mkdir(exist_ok=True)
        if not TRACKER_FILE.exists():
            self._save_data([])

    def _load_data(self) -> list:
        try:
            return json.loads(TRACKER_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_data(self, data: list):
        TRACKER_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def is_duplicate(self, job_id: str, company: str, title: str) -> bool:
        apps = self._load_data()
        for app in apps:
            if app.get("job_id") == job_id or (app.get("company") == company and app.get("title") == title):
                return True
        return False

    def add_application(self, job_data: dict, status: str = "APPLIED"):
        apps = self._load_data()
        entry = {
            "job_id": job_data.get("job_id"),
            "title": job_data.get("title"),
            "company": job_data.get("company"),
            "match_score": job_data.get("match_score", 0.0),
            "applied_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": status,
            "requires_otp": job_data.get("requires_otp", False)
        }
        apps.append(entry)
        self._save_data(apps)
        return entry

    def list_applications(self) -> list:
        return self._load_data()


tracker = JobTracker()


def calculate_match_score(job: dict, user_profile: dict) -> float:
    """Calculates resume match score based on required skills and user skills."""
    required_skills = set(job.get("skills", []))
    user_skills = set(user_profile.get("skills", []))
    if not required_skills:
        return 80.0

    overlap = required_skills.intersection(user_skills)
    score = (len(overlap) / len(required_skills)) * 100.0
    return round(score, 1)


def check_eligibility(job: dict, user_profile: dict) -> tuple[bool, str]:
    """
    Strict eligibility rules check.
    Returns (is_eligible, reason)
    """
    min_exp = job.get("min_experience_years", 0)
    user_exp = user_profile.get("experience_years", 0)
    if user_exp < min_exp:
        return False, f"Ineligible: Experience required {min_exp} years, user has {user_exp} years."

    req_location = job.get("location", "").lower()
    user_location = user_profile.get("location", "").lower()
    if req_location and "remote" not in req_location and req_location not in user_location:
        return False, f"Ineligible: Location mismatch ({req_location} vs {user_location})."

    return True, "Eligible"


def search_jobs(query: str, platform: str = "LinkedIn") -> list[dict]:
    """Mock/Simulated search for relevant job openings."""
    print(f"[JobAgent] Searching jobs for '{query}' on {platform}...")
    sample_jobs = [
        {
            "job_id": f"job_{int(time.time())}_1",
            "title": f"Senior {query} Engineer",
            "company": "TechCorp",
            "location": "Remote",
            "min_experience_years": 3,
            "skills": ["Python", "PyQt6", "AI", "REST API"],
            "requires_otp": False
        },
        {
            "job_id": f"job_{int(time.time())}_2",
            "title": f"Junior {query} Developer",
            "company": "SoftInc",
            "location": "Remote",
            "min_experience_years": 1,
            "skills": ["Python", "SQL"],
            "requires_otp": True
        }
    ]
    return sample_jobs


def apply_job(job: dict, user_profile: dict, otp_code: str | None = None) -> dict:
    """
    Applies to a job adhering strictly to security & safety rules:
    - Never bypass OTP if required
    - Check duplicate application
    - Check eligibility rules
    - Check match score >= JOB_MIN_MATCH_SCORE
    """
    company = job.get("company", "Unknown")
    title = job.get("title", "Unknown")
    job_id = job.get("job_id", "")

    # Rule 1: Duplicate check
    if tracker.is_duplicate(job_id, company, title):
        return {"success": False, "status": "DUPLICATE", "message": f"Already applied to {title} at {company}."}

    # Rule 2: Eligibility check
    eligible, reason = check_eligibility(job, user_profile)
    if not eligible:
        return {"success": False, "status": "INELIGIBLE", "message": reason}

    # Rule 3: Resume match score check
    match_score = calculate_match_score(job, user_profile)
    job["match_score"] = match_score
    if match_score < JOB_MIN_MATCH_SCORE:
        return {
            "success": False,
            "status": "BELOW_THRESHOLD",
            "message": f"Match score {match_score}% is below required minimum {JOB_MIN_MATCH_SCORE}%."
        }

    # Rule 4: OTP Authorization requirement
    if job.get("requires_otp") and not otp_code:
        return {
            "success": False,
            "status": "OTP_REQUIRED",
            "message": "OTP authorization is required to submit this application. NEVER bypass OTP."
        }

    # Submit application and record in tracker
    entry = tracker.add_application(job, status="APPLIED")
    print(f"[JobAgent] ✅ Successfully applied to {title} at {company} (Match: {match_score}%)")
    return {
        "success": True,
        "status": "APPLIED",
        "message": f"Application submitted to {company} for {title}.",
        "tracker_entry": entry
    }


def job_agent_action(parameters: dict, user_profile: dict | None = None) -> str:
    """
    Main job agent entry point.
    """
    if user_profile is None:
        user_profile = {
            "skills": ["Python", "PyQt6", "AI", "REST API", "SQL"],
            "experience_years": 4,
            "location": "Remote"
        }

    action = (parameters or {}).get("action", "search").lower().strip()
    query = (parameters or {}).get("query", "Software Engineer")
    otp_code = (parameters or {}).get("otp_code")

    if action == "search":
        jobs = search_jobs(query)
        out_lines = [f"Found {len(jobs)} jobs for '{query}':"]
        for j in jobs:
            score = calculate_match_score(j, user_profile)
            eligible, _ = check_eligibility(j, user_profile)
            out_lines.append(f"- [{j['job_id']}] {j['title']} at {j['company']} (Match: {score}%, Eligible: {eligible})")
        return "\n".join(out_lines)

    elif action == "apply":
        jobs = search_jobs(query)
        if not jobs:
            return f"No jobs found for query '{query}'."
        target_job = jobs[0]
        res = apply_job(target_job, user_profile, otp_code=otp_code)
        return res.get("message", "Job action finished.")

    elif action == "list_applications":
        apps = tracker.list_applications()
        if not apps:
            return "No job applications found in tracker."
        out_lines = ["Job Application History:"]
        for a in apps:
            out_lines.append(f"- {a['title']} at {a['company']} [{a['status']}] on {a['applied_at']}")
        return "\n".join(out_lines)

    return f"Job agent action '{action}' completed."
