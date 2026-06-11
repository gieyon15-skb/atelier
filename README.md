# Virtual Try-On Studio — free edition (CatVTON)

Puts garments onto a photo of a person using the **CatVTON** model, free on
Hugging Face. CatVTON takes a garment **type** (`upper` / `lower` / `overall`),
so it handles **tops, bottoms, and dresses** — not just upper-body.

**Full outfits:** add several garments, each with a type, and the app applies them
**one pass at a time, feeding each result into the next**. Each pass only repaints
its own region, so the top stays on when the bottoms go on. A dress is a single
`overall` pass.

> It runs on a free, shared **ZeroGPU** Space, so each pass can queue or wait for
> the Space to wake up — and an outfit is several passes. It works; it’s just not
> instant. For always-on speed, swap to a paid API (ask and I’ll wire `run_catvton`).

-----

## 1. Get a free Hugging Face token

1. Sign up at **<https://huggingface.co>**.
1. **Settings → Access Tokens → New token** (a **read** token is enough).
1. Copy it (starts with `hf_`). No card, no per-image charge.

-----

## 2. Run locally (optional)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Paste your token in the sidebar, or create `.streamlit/secrets.toml`:

```toml
HF_TOKEN = "hf_your_token_here"
```

-----

## 3. Put it on GitHub

```bash
git init
git add app.py requirements.txt .gitignore README.md
git commit -m "Virtual try-on studio (CatVTON, full outfits)"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/tryon-studio.git
git push -u origin main
```

`.gitignore` keeps your token out of the repo.

-----

## 4. Deploy free (Streamlit Community Cloud)

1. **<https://share.streamlit.io>** → sign in with GitHub.
1. **Create app** → your repo → branch `main` → main file `app.py` → **Deploy**.
1. **Settings → Secrets** → paste:
   
   ```toml
   HF_TOKEN = "hf_your_token_here"
   ```
   
   Save. Sidebar will read “Hugging Face token loaded.”

-----

## How to use

1. Upload a **full-body, front-facing** photo of the person.
1. Under **Build the outfit**, add each piece: choose its **type** (Top / Bottoms /
   Dress), then upload a photo or paste a product image URL, and **Add to outfit**.
   Add tops before bottoms.
1. Hit **Try on the outfit**. It runs each piece in turn and shows the final look.

-----

## Reliability & quirks

- **Each garment is one GPU pass.** A 2-piece outfit is 2 passes, so it takes a
  few minutes on the shared Space. If a pass stalls, wait and retry or switch Space.
- **Blank/odd result?** CatVTON’s NSFW SafetyChecker sometimes trips on normal
  images — toggle **Randomize** or change the **Seed** and run again.
- **Want it dependable and still free?** Duplicate the Space to your own account and
  run on your own ZeroGPU quota:
  
  ```bash
  pip install huggingface_hub
  huggingface-cli login
  huggingface-cli repo duplicate zhengchong/CatVTON YOUR_USERNAME/CatVTON --type space
  ```
  
  Open your Space once so it builds, then add `"YOUR_USERNAME/CatVTON"` to the
  `SPACES` list in `app.py`.
- **If a pass errors with an argument/endpoint problem:** the Space is community-run
  and can change. Send me the exact error and I’ll match the one call in `run_catvton`.

Space: <https://huggingface.co/spaces/zhengchong/CatVTON>
Model license: CC BY-NC-SA 4.0 (non-commercial).