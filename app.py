"""
Virtual Try-On Studio — free edition
Puts a garment onto a photo of a person using the Kolors Virtual Try-On model,
hosted free on Hugging Face. The Space does the work, so there's no GPU to run
and no paid API. It's a shared free Space, so expect the odd queue or a Space
that's asleep and needs a moment to wake up.

Run locally:  streamlit run app.py
"""

import os
import tempfile

import streamlit as st
from PIL import Image
from gradio_client import Client, handle_file

# Public Kolors try-on Spaces. The first is the official one (can be busy);
# the rest are community mirrors to fall back on if it's overloaded or down.
SPACES = [
    "Kwai-Kolors/Kolors-Virtual-Try-On",
    "AhmedAlmaghz/Kolors-Virtual-Try-On",
]

st.set_page_config(page_title="Virtual Try-On Studio", page_icon="👗", layout="centered")


# ----------------------------- helpers -----------------------------
def read_token() -> str:
    try:
        return st.secrets["HF_TOKEN"]
    except Exception:
        return os.environ.get("HF_TOKEN", "")


def save_upload(uploaded, max_dim: int = 1024) -> str:
    """Resize an uploaded image and write it to a temp file. Returns the path."""
    img = Image.open(uploaded).convert("RGB")
    img.thumbnail((max_dim, max_dim))
    fd, path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    img.save(path, "JPEG", quality=90)
    return path


@st.cache_resource(show_spinner=False)
def get_client(space_id: str, token: str):
    """Connect to the Space. gradio_client renamed this arg across versions, so try both."""
    try:
        return Client(space_id, hf_token=token or None)
    except TypeError:
        return Client(space_id, token=token or None)


def run_tryon(client, person_path, garment_ref, seed, randomize):
    """
    Call the Space's /tryon endpoint with positional args (so we don't depend on
    parameter names). The person input is an image editor in this Space, so we try
    the editor-dict form first, then a plain image as a fallback.
    """
    person_forms = [
        {"background": handle_file(person_path), "layers": [], "composite": None},
        handle_file(person_path),
    ]
    last_err = None
    for person_arg in person_forms:
        try:
            return client.predict(
                person_arg,
                handle_file(garment_ref),
                int(seed),
                bool(randomize),
                api_name="/tryon",
            )
        except Exception as e:  # try the next input shape
            last_err = e
    raise last_err


def extract_image_path(result):
    """The endpoint returns a local file path (or a tuple of them). Pull out the image."""
    def as_path(x):
        if isinstance(x, dict):
            return x.get("path") or x.get("url") or x.get("name")
        return x

    if isinstance(result, (list, tuple)):
        for item in result:
            p = as_path(item)
            if isinstance(p, str) and p.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                return p
        for item in result:
            p = as_path(item)
            if isinstance(p, str):
                return p
    return as_path(result)


# ----------------------------- state -----------------------------
if "gallery" not in st.session_state:
    st.session_state.gallery = []  # result image bytes from this session


# ----------------------------- sidebar -----------------------------
st.sidebar.title("Setup")

token = read_token()
if token:
    st.sidebar.success("Hugging Face token loaded.")
else:
    token = st.sidebar.text_input(
        "Hugging Face token",
        type="password",
        help="Free. huggingface.co → Settings → Access Tokens → New token (read scope is enough). "
             "For a deployed app, store it in Streamlit secrets instead.",
    )

space_id = st.sidebar.selectbox(
    "Try-on Space", SPACES, index=0,
    help="If the first one is busy or sleeping, switch to a mirror.",
)
randomize = st.sidebar.checkbox("Randomize each result", value=True)
seed = st.sidebar.number_input("Seed", value=0, step=1, disabled=randomize)
st.sidebar.caption(
    "This runs on a free, shared Space. If it's busy or asleep, wait a moment and retry, "
    "or switch Space above."
)


# ----------------------------- main -----------------------------
st.title("👗 Virtual Try-On Studio")
st.write("Free try-on powered by the Kolors model on Hugging Face — no GPU, no paid API.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1 · Person")
    person_file = st.file_uploader(
        "Full-body photo of the person", type=["jpg", "jpeg", "png", "webp"], key="person"
    )
    if person_file:
        st.image(person_file, use_container_width=True)

with col2:
    st.subheader("2 · Garment")
    source = st.radio("Source", ["Upload", "Image URL"], horizontal=True, key="gsource")
    garment_file, garment_url = None, ""
    if source == "Upload":
        garment_file = st.file_uploader(
            "Garment photo (flat-lay works best)", type=["jpg", "jpeg", "png", "webp"], key="garment"
        )
        if garment_file:
            st.image(garment_file, use_container_width=True)
    else:
        garment_url = st.text_input("Paste a product image URL (e.g. from a store page)")
        if garment_url:
            st.image(garment_url, use_container_width=True)

st.write("")
go = st.button("✨ Try it on", type="primary", use_container_width=True, disabled=not token)

if not token:
    st.info("Add your free Hugging Face token in the sidebar to begin.")

if go:
    if not person_file:
        st.error("Add a photo of the person first.")
    elif source == "Upload" and not garment_file:
        st.error("Add a garment photo first.")
    elif source == "Image URL" and not garment_url:
        st.error("Paste a garment image URL first.")
    else:
        try:
            with st.spinner("Preparing images…"):
                person_path = save_upload(person_file)
                garment_ref = garment_url if source == "Image URL" else save_upload(garment_file)

            with st.spinner("Generating try-on… the first run can take a minute if the Space is waking up."):
                client = get_client(space_id, token)
                result = run_tryon(client, person_path, garment_ref, seed, randomize)
                out_path = extract_image_path(result)

            st.success("Done.")
            st.image(out_path, caption="Try-on result", use_container_width=True)

            try:
                with open(out_path, "rb") as f:
                    img_bytes = f.read()
                st.download_button("Download image", img_bytes, file_name="tryon.png", mime="image/png")
                st.session_state.gallery.insert(0, img_bytes)
            except Exception:
                pass

        except Exception as e:
            st.error(
                "That didn't go through. The free Space may be asleep, busy, or rate-limited — "
                "wait a moment and retry, or switch to a mirror Space in the sidebar."
            )
            st.caption(f"Details: {e}")


# ----------------------------- gallery -----------------------------
if st.session_state.gallery:
    st.divider()
    st.subheader("Your looks this session")
    cols = st.columns(3)
    for i, img in enumerate(st.session_state.gallery):
        with cols[i % 3]:
            st.image(img, use_container_width=True)
    st.caption("These reset when the app restarts — use Download to keep the ones you like.")
