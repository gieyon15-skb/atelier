"""
Virtual Try-On Studio — free edition (CatVTON)
Puts garments onto a photo of a person using the CatVTON model, hosted free on
Hugging Face. CatVTON supports a garment TYPE (upper / lower / overall), so it
handles tops, bottoms, AND dresses — unlike upper-body-only models.

Full outfits: add several garments, each with a type, and the app applies them
ONE PASS AT A TIME, feeding each result into the next. Each pass only repaints
its own region, so the top stays put when the bottoms go on.

It runs on a free, shared ZeroGPU Space, so each pass can queue or wait for the
Space to wake up — and an outfit is several passes. If you want it always-on and
fast, swap in a paid API (ask and I'll wire it). Run locally:  streamlit run app.py
"""

import io
import os
import tempfile

import streamlit as st
from PIL import Image, ImageOps
from gradio_client import Client, handle_file

APP_VERSION = "build 7 · 2026-06-11"

# Public CatVTON Spaces with the garment-type API. Second is a duplicate fallback.
SPACES = [
    "zhengchong/CatVTON",
    "Nymbo/CatVTON",
]
TYPES = ["upper", "lower", "overall"]
TYPE_LABEL = {"upper": "Top", "lower": "Bottoms", "overall": "Dress / one-piece"}

st.set_page_config(page_title="Virtual Try-On Studio", page_icon="👗", layout="centered")


# ----------------------------- helpers -----------------------------
def read_token() -> str:
    try:
        return st.secrets["HF_TOKEN"]
    except Exception:
        return os.environ.get("HF_TOKEN", "")


def upload_to_bytes(uploaded, max_dim: int = 1024) -> bytes:
    img = Image.open(uploaded)
    img = ImageOps.exif_transpose(img)  # honor the phone's rotation tag (fixes sideways photos)
    img = img.convert("RGB")
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


def make_blank_mask(person_path: str) -> str:
    """A blank (non-RGBA) layer so CatVTON's editor input is valid and it falls back to auto-masking."""
    with Image.open(person_path) as im:
        w, h = im.size
    fd, p = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    Image.new("RGB", (w, h), (0, 0, 0)).save(p)  # RGB, never RGBA -> safe to re-save as JPEG
    return p


def to_rgb_jpeg_temp(path: str) -> str:
    """Re-encode any image to a clean RGB JPEG. Keeps the layering chain free of RGBA."""
    img = Image.open(path).convert("RGB")
    fd, p = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    img.save(p, "JPEG", quality=95)
    return p


@st.cache_resource(show_spinner=False)
def get_client(space_id: str, token: str):
    try:
        return Client(space_id, hf_token=token or None)
    except TypeError:
        return Client(space_id, token=token or None)


def _looks_missing(e) -> bool:
    s = str(e).lower()
    return any(k in s for k in ["cannot find a function", "not a valid", "no api endpoint", "valid endpoint"])


def _is_shape_error(e) -> bool:
    """Input-shape/format problems that mean we should try a different person-input form."""
    s = str(e).lower()
    return any(k in s for k in [
        "rgba", "index out of range", "indices must", "subscriptable",
        "argument", "missing", "expected", "nonetype", "not enough values",
    ])


def _attempt(client, args):
    last = None
    for name in ["/submit_function", "/submit", "/predict", "/tryon"]:
        try:
            return client.predict(*args, api_name=name)
        except Exception as e:
            last = e
            if not _looks_missing(e):
                raise               # endpoint found; real/shape error -> bubble up
    for idx in [1, 0, 2, 3]:        # last-ditch: unnamed endpoint by index
        try:
            return client.predict(*args, fn_index=idx)
        except Exception as e:
            last = e
    raise last


def run_catvton(client, person_path, garment_ref, cloth_type, steps, cfg, seed):
    """
    CatVTON arg order: [person, cloth, cloth_type, steps, guidance_scale, seed, show_type].
    'result only' returns just the try-on image (needed for layering). The endpoint has no
    fixed api_name, so we try names then index. We send the person as an editor input with
    EMPTY layers first (the proven pattern that avoids the RGBA-layer error), and fall back
    to a blank mask layer only if the Space requires one.
    """
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
            return _attempt(client, args)
        except Exception as e:
            last = e
            if i < len(forms) - 1 and _is_shape_error(e):
                continue            # try the next person-input form
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

token = read_token()
if token:
    st.sidebar.success("Hugging Face token loaded.")
else:
    token = st.sidebar.text_input(
        "Hugging Face token", type="password",
        help="Free. huggingface.co → Settings → Access Tokens → New token (read scope). "
             "For a deployed app, store it in Streamlit secrets.",
    )

space_id = st.sidebar.selectbox(
    "Try-on Space", SPACES, index=0,
    help="If the first is busy or asleep, try the other, or duplicate it to your own account (README).",
)
randomize = st.sidebar.checkbox("Randomize each result", value=True)
seed_val = st.sidebar.number_input("Seed", value=42, step=1, min_value=0, disabled=randomize)
steps = st.sidebar.slider("Inference steps", 20, 50, 35, help="Higher = a bit more detail, but slower.")
cfg = st.sidebar.slider("CFG strength", 1.0, 7.5, 2.5, 0.5, help="Higher follows the garment more strongly.")
st.sidebar.caption(
    "Free shared ZeroGPU Space. Each garment is one pass, so a full outfit takes a few passes — "
    "if one stalls, wait and retry. If a result looks blank, the NSFW filter may have tripped; "
    "toggle Randomize or change the seed and retry."
)


# ----------------------------- main -----------------------------
st.title("👗 Virtual Try-On Studio")
st.write("Free try-on with **CatVTON** — does tops, bottoms, and dresses, and layers a full outfit.")
st.caption(f"🏷️ {APP_VERSION}")

# 1) Person
st.subheader("1 · Person")
person_file = st.file_uploader(
    "Full-body, front-facing photo (plain background works best)",
    type=["jpg", "jpeg", "png", "webp"], key="person",
)
if person_file:
    st.image(person_file, use_container_width=True)

# 2) Build the outfit
st.subheader("2 · Build the outfit")
st.caption("Add each piece with its type. Order = the order they're put on (add tops before bottoms).")

with st.form("add_garment", clear_on_submit=True):
    g_type = st.radio("Type", TYPES, format_func=lambda t: TYPE_LABEL[t], horizontal=True)
    g_source = st.radio("Source", ["Upload", "Image URL"], horizontal=True)
    g_file = st.file_uploader("Garment photo (flat-lay works best)", type=["jpg", "jpeg", "png", "webp"])
    g_url = st.text_input("…or paste a product image URL")
    if st.form_submit_button("➕ Add to outfit"):
        if g_source == "Upload" and g_file is not None:
            st.session_state.outfit.append(
                {"type": g_type, "is_url": False, "ref": None,
                 "bytes": upload_to_bytes(g_file), "name": g_file.name}
            )
        elif g_source == "Image URL" and g_url.strip():
            st.session_state.outfit.append(
                {"type": g_type, "is_url": True, "ref": g_url.strip(), "bytes": None, "name": g_url.strip()[:40]}
            )
        else:
            st.warning("Add a photo or a URL before adding to the outfit.")

# current outfit
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
go = st.button("✨ Try on the outfit", type="primary", use_container_width=True,
               disabled=(not token or not person_file or not st.session_state.outfit))
if not token:
    st.info("Add your free Hugging Face token in the sidebar to begin.")

# ----------------------------- run -----------------------------
if go:
    try:
        seed = -1 if randomize else int(seed_val)
        person_bytes = upload_to_bytes(person_file)
        current_person = bytes_to_temp(person_bytes)
        client = get_client(space_id, token)

        with st.status("Styling the outfit…", expanded=True) as status:
            for i, g in enumerate(st.session_state.outfit):
                status.write(f"Putting on piece {i + 1}/{len(st.session_state.outfit)} — {TYPE_LABEL[g['type']]}…")
                garment_ref = g["ref"] if g["is_url"] else bytes_to_temp(g["bytes"])
                result = run_catvton(client, current_person, garment_ref, g["type"], steps, cfg, seed)
                current_person = to_rgb_jpeg_temp(extract_image_path(result))   # normalize + feed forward
            status.update(label="Outfit complete.", state="complete")

        st.image(current_person, caption="Final look", use_container_width=True)
        try:
            with open(current_person, "rb") as f:
                img_bytes = f.read()
            st.download_button("Download image", img_bytes, file_name="look.jpg", mime="image/jpeg")
            st.session_state.gallery.insert(0, img_bytes)
        except Exception:
            pass

    except Exception as e:
        st.error(
            "A pass didn't go through. The free Space may be asleep, busy, or out of GPU quota — "
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
