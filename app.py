"""
Virtual Try-On Studio — build 9 (free session engine)

Two ways to run the try-on:
  1) SESSION ENGINE (recommended, free & unlimited): run catvton_engine.ipynb on a free
     Colab/Kaggle GPU; it prints a https://xxxx.gradio.live link. Paste that link into
     the sidebar. We control that engine's code, so it has a clean /tryon API.
  2) PUBLIC SPACE (fallback): the shared zhengchong/CatVTON Space. Unreliable — its API
     path has a known server-side bug we can't fix from here.

Preset mannequin: add a photo named model.jpg (or .jpeg/.png/.webp) to the repo root and
it becomes the built-in model — she only uploads clothes. A toggle allows a different
photo per look.

Outfits: add several garments, each with a type (upper/lower/overall). They're applied
one pass at a time, each result feeding the next, so the top stays on when bottoms go on.
"""

import io
import os
import random
import tempfile

import streamlit as st
from PIL import Image, ImageOps
from gradio_client import Client, handle_file

APP_VERSION = "build 9 · 2026-06-11"

PUBLIC_SPACES = [
    "zhengchong/CatVTON",
    "Nymbo/CatVTON",
]
TYPES = ["upper", "lower", "overall"]
TYPE_LABEL = {"upper": "Top", "lower": "Bottoms", "overall": "Dress / one-piece"}
PRESET_CANDIDATES = ["model.jpg", "model.jpeg", "model.png", "model.webp",
                     "model.JPG", "model.JPEG", "model.PNG", "model.WEBP"]

st.set_page_config(page_title="Virtual Try-On Studio", page_icon="👗", layout="centered")


# ----------------------------- image helpers -----------------------------
def corrected_rgb(file_or_path):
    """Open an upload or path, honor the EXIF rotation tag, return an upright RGB image."""
    try:
        file_or_path.seek(0)
    except Exception:
        pass
    img = Image.open(file_or_path)
    img = ImageOps.exif_transpose(img)  # fixes sideways phone photos
    return img.convert("RGB")


def to_jpeg_bytes(file_or_path, max_dim: int = 1024) -> bytes:
    img = corrected_rgb(file_or_path)
    img.thumbnail((max_dim, max_dim))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def bytes_to_temp(b: bytes, suffix=".jpg") -> str:
    fd, p = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    with open(p, "wb") as f:
        f.write(b)
    return p


def to_rgb_jpeg_temp(path: str) -> str:
    """Re-encode any image to a clean RGB JPEG (keeps the layering chain format-safe)."""
    img = Image.open(path).convert("RGB")
    fd, p = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    img.save(p, "JPEG", quality=95)
    return p


def make_blank_mask(person_path: str) -> str:
    """Blank layer for the public Space's editor input (legacy fallback path only)."""
    with Image.open(person_path) as im:
        w, h = im.size
    fd, p = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    Image.new("RGB", (w, h), (0, 0, 0)).save(p)
    return p


def find_preset():
    for p in PRESET_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


# ----------------------------- engine clients -----------------------------
def read_token() -> str:
    try:
        return st.secrets["HF_TOKEN"]
    except Exception:
        return os.environ.get("HF_TOKEN", "")


@st.cache_resource(show_spinner=False)
def get_client(target: str, token: str):
    """target = a gradio.live session URL or a HF Space id."""
    try:
        return Client(target, hf_token=token or None)
    except TypeError:
        return Client(target, token=token or None)


def _looks_missing(e) -> bool:
    s = str(e).lower()
    return any(k in s for k in ["cannot find a function", "not a valid", "no api endpoint", "valid endpoint"])


def _is_shape_error(e) -> bool:
    s = str(e).lower()
    return any(k in s for k in [
        "rgba", "index out of range", "indices must", "subscriptable",
        "argument", "missing", "expected", "nonetype", "not enough values",
    ])


def run_session_engine(client, person_path, garment_ref, cloth_type, steps, cfg, seed):
    """Our own notebook engine: plain inputs, clean /tryon endpoint."""
    args = (handle_file(person_path), handle_file(garment_ref), cloth_type,
            int(steps), float(cfg), int(seed))
    last = None
    for name in ["/tryon", "/predict"]:
        try:
            return client.predict(*args, api_name=name)
        except Exception as e:
            last = e
            if not _looks_missing(e):
                raise
    raise last


def _attempt_public(client, args):
    last = None
    for name in ["/submit_function", "/submit", "/predict", "/tryon"]:
        try:
            return client.predict(*args, api_name=name)
        except Exception as e:
            last = e
            if not _looks_missing(e):
                raise
    for idx in [1, 0, 2, 3]:
        try:
            return client.predict(*args, fn_index=idx)
        except Exception as e:
            last = e
    raise last


def run_public_space(client, person_path, garment_ref, cloth_type, steps, cfg, seed):
    """Legacy path for the shared Space (its editor-style API has a known server bug)."""
    forms = [
        lambda: {"background": handle_file(person_path), "layers": [], "composite": None},
        lambda: {
            "background": handle_file(person_path),
            "layers": [handle_file(make_blank_mask(person_path))],
            "composite": handle_file(person_path),
        },
    ]
    last = None
    for i, make_person in enumerate(forms):
        args = (make_person(), handle_file(garment_ref), cloth_type,
                int(steps), float(cfg), int(seed), "result only")
        try:
            return _attempt_public(client, args)
        except Exception as e:
            last = e
            if i < len(forms) - 1 and _is_shape_error(e):
                continue
            raise
    raise last


def extract_image_path(result):
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
if "outfit" not in st.session_state:
    st.session_state.outfit = []     # [{type, is_url, ref, bytes, name}]
if "gallery" not in st.session_state:
    st.session_state.gallery = []    # result image bytes


# ----------------------------- sidebar -----------------------------
st.sidebar.title("Setup")
st.sidebar.caption(f"🏷️ {APP_VERSION}")

st.sidebar.subheader("Engine")
session_url = st.sidebar.text_input(
    "Session link (from the notebook)",
    placeholder="https://xxxxx.gradio.live",
    help="Run catvton_engine.ipynb on Colab/Kaggle (free GPU). It prints this link at the "
         "bottom. While the notebook runs, try-ons are unlimited and free.",
).strip()
use_session = session_url.lower().startswith("http")

token = read_token()
space_id = None
if use_session:
    st.sidebar.success("Using your free session engine ✔")
else:
    st.sidebar.warning(
        "No session link. Falling back to the public Space — unreliable (known server bug). "
        "For the free, working route, run the notebook and paste its link above."
    )
    space_id = st.sidebar.selectbox("Public Space (fallback)", PUBLIC_SPACES, index=0)
    if token:
        st.sidebar.success("Hugging Face token loaded.")
    else:
        token = st.sidebar.text_input(
            "Hugging Face token", type="password",
            help="Only needed for the public-Space fallback. Free at huggingface.co → "
                 "Settings → Access Tokens.",
        )

randomize = st.sidebar.checkbox("Randomize each result", value=True)
seed_val = st.sidebar.number_input("Seed", value=42, step=1, min_value=0, disabled=randomize)
steps = st.sidebar.slider("Inference steps", 15, 60, 40, help="Higher = a bit more detail, slower.")
cfg = st.sidebar.slider("CFG strength", 1.0, 7.5, 2.5, 0.5,
                        help="2.5 is the sweet spot. Much higher can look stiff or oversaturated.")
st.sidebar.caption(
    "Each garment is one pass, so a full outfit takes a few passes. Odd or blurred result? "
    "The model's safety filter may have tripped — reroll with Randomize on."
)


# ----------------------------- main -----------------------------
st.title("👗 Virtual Try-On Studio")
st.write("Free try-on with **CatVTON** — tops, bottoms, and dresses, layered into full outfits.")
st.caption(f"🏷️ {APP_VERSION}")

# 1) Person
st.subheader("1 · Person")
preset_path = find_preset()
person_source = None  # ("preset", path) or ("upload", file)

if preset_path:
    use_other = st.toggle("Use a different photo this time", value=False)
    if not use_other:
        st.image(corrected_rgb(preset_path), use_container_width=True, caption="Your model")
        person_source = ("preset", preset_path)

if person_source is None:
    person_file = st.file_uploader(
        "Full-body, front-facing photo (plain background works best)",
        type=["jpg", "jpeg", "png", "webp"], key="person",
    )
    if person_file:
        st.image(corrected_rgb(person_file), use_container_width=True)
        person_source = ("upload", person_file)
    if not preset_path:
        st.caption("Tip: add a photo named **model.jpg** to the app's GitHub repo and it "
                   "becomes the built-in model — then only clothes need uploading.")

# 2) Build the outfit
st.subheader("2 · Build the outfit")
st.caption("Add each piece with its type. Order = the order they're put on (tops before bottoms).")

with st.form("add_garment", clear_on_submit=True):
    g_type = st.radio("Type", TYPES, format_func=lambda t: TYPE_LABEL[t], horizontal=True)
    g_source = st.radio("Source", ["Upload", "Image URL"], horizontal=True)
    g_file = st.file_uploader("Garment photo (flat-lay works best)", type=["jpg", "jpeg", "png", "webp"])
    g_url = st.text_input("…or paste a product image URL")
    if st.form_submit_button("➕ Add to outfit"):
        if g_source == "Upload" and g_file is not None:
            st.session_state.outfit.append(
                {"type": g_type, "is_url": False, "ref": None,
                 "bytes": to_jpeg_bytes(g_file), "name": g_file.name}
            )
        elif g_source == "Image URL" and g_url.strip():
            st.session_state.outfit.append(
                {"type": g_type, "is_url": True, "ref": g_url.strip(),
                 "bytes": None, "name": g_url.strip()[:40]}
            )
        else:
            st.warning("Add a photo or a URL before adding to the outfit.")

if st.session_state.outfit:
    st.write("**Outfit so far:**")
    for i, g in enumerate(st.session_state.outfit):
        c1, c2, c3 = st.columns([1, 4, 1])
        with c1:
            if g["bytes"]:
                st.image(g["bytes"], use_container_width=True)
            elif g["is_url"]:
                st.image(g["ref"], use_container_width=True)
        with c2:
            st.write(f"**{i + 1}. {TYPE_LABEL[g['type']]}**")
            st.caption(g["name"])
        with c3:
            if st.button("✕", key=f"rm{i}"):
                st.session_state.outfit.pop(i)
                st.rerun()
    if st.button("Clear outfit"):
        st.session_state.outfit = []
        st.rerun()
else:
    st.info("No garments added yet.")

st.write("")
ready = bool(person_source) and bool(st.session_state.outfit) and (use_session or bool(token))
go = st.button("✨ Try on the outfit", type="primary", use_container_width=True, disabled=not ready)

if not use_session and not token:
    st.info("Paste a session link (recommended) or add a Hugging Face token for the public fallback.")

# ----------------------------- run -----------------------------
if go:
    try:
        use_seed = random.randint(0, 999999) if randomize else int(seed_val)
        if person_source[0] == "preset":
            person_bytes = to_jpeg_bytes(person_source[1])
        else:
            person_bytes = to_jpeg_bytes(person_source[1])
        current_person = bytes_to_temp(person_bytes)

        target = session_url if use_session else space_id
        client = get_client(target, "" if use_session else token)
        engine = run_session_engine if use_session else run_public_space

        with st.status("Styling the outfit…", expanded=True) as status:
            for i, g in enumerate(st.session_state.outfit):
                status.write(f"Putting on piece {i + 1}/{len(st.session_state.outfit)} — {TYPE_LABEL[g['type']]}…")
                garment_ref = g["ref"] if g["is_url"] else bytes_to_temp(g["bytes"])
                result = engine(client, current_person, garment_ref, g["type"], steps, cfg, use_seed)
                current_person = to_rgb_jpeg_temp(extract_image_path(result))
            status.update(label="Outfit complete.", state="complete")

        st.image(current_person, caption=f"Final look (seed {use_seed})", use_container_width=True)
        try:
            with open(current_person, "rb") as f:
                img_bytes = f.read()
            st.download_button("Download image", img_bytes, file_name="look.jpg", mime="image/jpeg")
            st.session_state.gallery.insert(0, img_bytes)
        except Exception:
            pass

    except Exception as e:
        if use_session:
            st.error(
                "A pass didn't go through. Check the notebook tab: is it still running, and does the "
                "link in the sidebar match the latest one it printed? (Links die when the session ends — "
                "re-run the last cell to get a fresh one.)"
            )
        else:
            st.error(
                "A pass didn't go through. The public Space is unreliable (known server bug) — the "
                "dependable free route is the notebook session link."
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
