"""
Virtual Try-On Studio — free edition (IDM-VTON)
Puts a garment onto a photo of a person using the IDM-VTON model, hosted free on
Hugging Face. The Space does the work, so there's no GPU to run and no paid API.

Why IDM-VTON and not Kolors? The Kolors Space turned its public API off
(api_open=False). IDM-VTON keeps its /tryon endpoint open, so it's actually
callable. It's still a shared, free ZeroGPU Space, so it can sleep or queue — if
the public one is flaky, duplicate it to your own account (see README) and point
SPACES at "your_username/IDM-VTON".

Run locally:  streamlit run app.py
"""

import os
import random
import tempfile

import streamlit as st
from PIL import Image
from gradio_client import Client, handle_file

# Public IDM-VTON Spaces with an OPEN /tryon API.
# The second is a maintained duplicate by a Gradio team member (used in HF's own docs).
SPACES = [
    "yisol/IDM-VTON",
    "freddyaboulton/IDM-VTON",
]
MAX_SEED = 999999

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


def run_tryon(client, person_path, garment_ref, seed, steps):
    """
    Call IDM-VTON's /tryon. Positional args (so we don't depend on parameter names):
        [person(ImageEditor dict), garment, garment_desc, auto_mask, auto_crop, steps, seed]
    Returns the endpoint's raw output (output[0] is the try-on image).
    """
    person_editor = {"background": handle_file(person_path), "layers": [], "composite": None}
    return client.predict(
        person_editor,
        handle_file(garment_ref),
        "",            # garment description (optional)
        True,          # auto-generate the clothing mask
        False,         # auto crop & resize
        int(steps),    # denoise steps
        int(seed),     # seed
        api_name="/tryon",
    )


def extract_image_path(result):
    """IDM-VTON returns (tryon_image, masked_image). Pull out the first image path."""
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
    help="If the first one is busy or sleeping, switch to the other. For full reliability, "
         "duplicate the Space to your own account (see README) and add it here.",
)
randomize = st.sidebar.checkbox("Randomize each result", value=True)
seed = st.sidebar.number_input("Seed", value=0, step=1, min_value=0, max_value=MAX_SEED, disabled=randomize)
steps = st.sidebar.slider("Detail (denoise steps)", min_value=20, max_value=40, value=30,
                          help="Higher = a bit more detail but slower.")
st.sidebar.caption(
    "This runs on a free, shared ZeroGPU Space. If it's busy or asleep, wait a moment and retry, "
    "switch Space above, or duplicate it to your own account."
)


# ----------------------------- main -----------------------------
st.title("👗 Virtual Try-On Studio")
st.write("Free try-on powered by IDM-VTON on Hugging Face — no GPU, no paid API.")

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
                use_seed = random.randint(0, MAX_SEED) if randomize else int(seed)

            with st.spinner("Generating try-on… the first run can take a minute if the Space is waking up."):
                client = get_client(space_id, token)
                result = run_tryon(client, person_path, garment_ref, use_seed, steps)
                out_path = extract_image_path(result)

            st.success(f"Done. (seed {use_seed})")
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
                "That didn't go through. The free Space may be asleep, busy, or out of GPU quota — "
                "wait a moment and retry, switch Space in the sidebar, or duplicate it to your own account."
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
