import os
import json
from datetime import datetime

import streamlit as st
import pandas as pd

# ---------------------------
# App Config
# ---------------------------
st.set_page_config(page_title="Future Career Predictor", layout="wide")
st.title("🔮 Future Career Predictor")
st.caption("Tell the AI what you're into. Get personalized career ideas — with steps you can take this semester. Built for high school students in Halifax, NC.")

# ---------------------------
# OpenAI Client Setup
# ---------------------------
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

OPENAI_API_KEY = None
if hasattr(st, "secrets") and "OPENAI_API_KEY" in st.secrets:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
elif os.getenv("OPENAI_API_KEY"):
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = None
if OpenAI and OPENAI_API_KEY:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception:
        client = None

if client is None:
    st.warning(
        "⚠️ OpenAI API key not found or client init failed. Add it via `st.secrets['OPENAI_API_KEY']` or the `OPENAI_API_KEY` env var to enable AI suggestions."
    )

# ---------------------------
# Helper: Light salary bands (illustrative)
# ---------------------------
SALARY_HINTS = {
    "software": "$55k–$95k entry (US)",
    "data": "$50k–$85k entry (US)",
    "health": "$35k–$70k entry (US)",
    "skilled": "$35k–$65k entry (US)",
    "creative": "$30k–$60k entry (US)",
    "business": "$40k–$70k entry (US)",
    "public": "$35k–$60k entry (US)",
}

# ---------------------------
# Sidebar — Inputs
# ---------------------------
st.sidebar.header("Tell us about you ✍️")
col_a, col_b = st.sidebar.columns(2)
with col_a:
    grade = st.selectbox("Grade", ["9th", "10th", "11th", "12th", "Other"], index=0)
with col_b:
    post_school = st.selectbox("After HS, I prefer…", ["4-year college", "2-year college", "Trade/Apprenticeship", "Go straight to work", "Undecided"]) 

hobbies = st.sidebar.text_area("Hobbies & interests", placeholder="Basketball, music production, gaming, cars, fashion, helping people…")
subjects = st.sidebar.text_area("Favorite subjects", placeholder="Math, biology, art, history…")
strengths = st.sidebar.text_area("Strengths / skills", placeholder="Team leader, creative, good with hands, troubleshooting, writing…")
work_style = st.sidebar.multiselect(
    "Work style",
    ["Hands-on", "Creative", "People-facing", "Outdoors", "Tech-heavy", "Numbers/Analysis", "Helping others", "Entrepreneurial"],
    default=["People-facing", "Tech-heavy"],
)
values = st.sidebar.multiselect(
    "What matters most",
    ["Good pay", "Job stability", "Flexible schedule", "Helping community", "Learning new things", "Creative freedom"],
    default=["Good pay", "Learning new things"],
)
location = st.sidebar.selectbox("Where do you want to work?", ["Local (Halifax / Roanoke Rapids)", "North Carolina", "Remote / Anywhere", "Big city"], index=0)
num_ideas = st.sidebar.slider("How many ideas?", min_value=3, max_value=8, value=5)

st.sidebar.caption("We don't store personal info. Use nicknames if you want.")

# ---------------------------
# Prompt Builder (FIX: escape braces for .format)
# ---------------------------
SYSTEM_PROMPT = (
    "You are a practical, upbeat career advisor for US high school students in Halifax, North Carolina. "
    "Give concrete, encouraging suggestions with next steps they can do within weeks, not years. "
    "Be specific and concise. Use plain English. Avoid long paragraphs."
)

USER_PROMPT_TPL = (
    "Student profile:\n"
    "- Grade: {grade}\n"
    "- Post-school preference: {post_school}\n"
    "- Hobbies: {hobbies}\n"
    "- Favorite subjects: {subjects}\n"
    "- Strengths: {strengths}\n"
    "- Work style: {work_style}\n"
    "- Values: {values}\n"
    "- Location: {location}\n\n"
    "Return STRICT JSON with this schema: \n"
    "{{\n"
    "  \"ideas\": [\n"
    "    {{\n"
    "      \"title\": \"str\",\n"
    "      \"why_fit\": \"str\",\n"
    "      \"starter_steps\": [\"str\", \"str\", \"str\"],\n"
    "      \"skills_to_learn\": [\"str\", \"str\", \"str\"],\n"
    "      \"local_or_free_resources\": [\"str\", \"str\"],\n"
    "      \"related_roles\": [\"str\", \"str\"],\n"
    "      \"salary_hint\": \"str\"\n"
    "    }}\n"
    "  ]\n"
    "}}\n\n"
    "Rules:\n"
    "- ideas length = {num_ideas}.\n"
    "- Choose roles that match preferences (college vs trade vs work).\n"
    "- Include at least one idea doable without a 4-year degree.\n"
    "- Use Halifax/NC/online resources where possible.\n"
    "- salary_hint: use one of these buckets (approx): {salary_buckets}.\n"
)

# ---------------------------
# Generate Button
# ---------------------------
col1, col2 = st.columns([2, 1])
with col1:
    st.subheader("Your Profile → AI Suggestions")
    st.write("Fill out the sidebar, then click **Generate my careers**.")
with col2:
    gen = st.button("🚀 Generate my careers", use_container_width=True)

if "ideas" not in st.session_state:
    st.session_state["ideas"] = []

# ---------------------------
# Call OpenAI
# ---------------------------
raw_response = None
if gen:
    user_prompt = USER_PROMPT_TPL.format(
        grade=grade,
        post_school=post_school,
        hobbies=hobbies,
        subjects=subjects,
        strengths=strengths,
        work_style=", ".join(work_style),
        values=", ".join(values),
        location=location,
        num_ideas=num_ideas,
        salary_buckets=", ".join(SALARY_HINTS.values()),
    )

    if client is None:
        st.error("OpenAI client not initialized. Add your API key to run AI generation.")
    else:
        try:
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
            )
            raw_response = completion.choices[0].message.content
        except Exception as e:
            st.error(f"OpenAI error: {e}")

# ---------------------------
# Parse + Render
# ---------------------------
ideas = []
if raw_response:
    txt = raw_response.strip()
    if txt.startswith("```"):
        txt = txt.split("\n", 1)[1]
        if txt.endswith("```"):
            txt = txt.rsplit("\n", 1)[0]
    try:
        data = json.loads(txt)
        ideas = data.get("ideas", [])
    except Exception:
        try:
            start = txt.find("{")
            end = txt.rfind("}")
            if start != -1 and end != -1 and end > start:
                data = json.loads(txt[start:end+1])
                ideas = data.get("ideas", [])
        except Exception:
            st.warning("Couldn't parse AI response as JSON. Showing raw text below.")
            st.code(raw_response)

if ideas:
    st.session_state["ideas"] = ideas

# ---------------------------
# UI — Results
# ---------------------------
if ideas:
    st.success(f"Here are {len(ideas)} career ideas based on your interests:")

    for idx, item in enumerate(ideas, 1):
        with st.container(border=True):
            st.markdown(f"### {idx}. {item.get('title', 'Career Idea')}")
            st.write(item.get("why_fit", ""))

            cols = st.columns(3)
            with cols[0]:
                st.markdown("**Starter steps (this semester):**")
                for step in item.get("starter_steps", [])[:5]:
                    st.write(f"- {step}")
            with cols[1]:
                st.markdown("**Skills to learn:**")
                for s in item.get("skills_to_learn", [])[:5]:
                    st.write(f"- {s}")
            with cols[2]:
                st.markdown("**Local / free resources:**")
                for r in item.get("local_or_free_resources", [])[:5]:
                    st.write(f"- {r}")

            extra = st.columns(2)
            with extra[0]:
                rr = ", ".join(item.get("related_roles", [])[:4])
                st.caption(f"Related roles: {rr}")
            with extra[1]:
                st.caption(f"Pay snapshot: {item.get('salary_hint', '')} (illustrative)")

            with st.expander("✨ Bonus: Resume bullet & interview practice"):
                example_bullet = (
                    f"Built a project related to {item.get('title','the role')} using free online resources; "
                    "collaborated with 2 classmates; presented results and documented impact."
                )
                st.write("**Sample resume bullet:**")
                st.write(f"- {example_bullet}")

                st.write("**Practice interview questions:**")
                st.write("1. What made you interested in this path?\n2. Tell me about a time you solved a problem with limited resources.\n3. How would you keep learning new skills after graduation?")

# ---------------------------
# Export / Save
# ---------------------------
st.divider()
st.subheader("Save or share your ideas")

if st.session_state.get("ideas"):
    flat_rows = []
    for it in st.session_state["ideas"]:
        flat_rows.append({
            "title": it.get("title",""),
            "why_fit": it.get("why_fit",""),
            "starter_steps": " | ".join(it.get("starter_steps", [])),
            "skills_to_learn": " | ".join(it.get("skills_to_learn", [])),
            "resources": " | ".join(it.get("local_or_free_resources", [])),
            "related_roles": " | ".join(it.get("related_roles", [])),
            "salary_hint": it.get("salary_hint",""),
        })
    df = pd.DataFrame(flat_rows)
    csv_bytes = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "⬇️ Download as CSV",
        data=csv_bytes,
        file_name=f"career_ideas_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        use_container_width=True,
    )
else:
    st.info("Generate ideas first, then you can download them as a CSV.")

# ---------------------------
# Footer
# ---------------------------
st.caption("Pay snapshots are rough and for inspiration only. Always research real, current data (NCWorks, BLS, or employer postings).")
