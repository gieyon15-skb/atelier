# Virtual Try-On Studio — free edition (IDM-VTON)

Puts a garment onto a photo of a person using the **IDM-VTON** model, hosted free
on Hugging Face. Your app just sends two images to the Space and shows the result
— no GPU, no paid API.

### Why IDM-VTON instead of Kolors?

The Kolors Space **turned its public API off** (`api_open=False`, `show_api=False`),
so it can't be called from code anymore — that's the "cannot find a function
`/tryon`" error. IDM-VTON keeps its `/tryon` endpoint **open**, so it actually
works. It's still a shared, free **ZeroGPU** Space, so it can sleep or queue. See
"Reliability" below for the fix.

---

## 1. Get a free Hugging Face token

1. Sign up at **https://huggingface.co**.
2. **Settings → Access Tokens → New token** (a **read** token is enough).
3. Copy it (starts with `hf_`). No card, no per-image charge.

---

## 2. Run it on your laptop (optional)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Paste your token in the sidebar, or create `.streamlit/secrets.toml`:

```toml
HF_TOKEN = "hf_your_token_here"
```

---

## 3. Put it on GitHub

1. Create a repo (e.g. `tryon-studio`).
2. Add `app.py`, `requirements.txt`, `.gitignore`, `README.md` — drag them into
   **Add file → Upload files**, or push with git:

```bash
git init
git add app.py requirements.txt .gitignore README.md
git commit -m "Virtual try-on studio (IDM-VTON)"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/tryon-studio.git
git push -u origin main
```

> `.gitignore` keeps your token file out of the repo.

---

## 4. Deploy it free (Streamlit Community Cloud)

1. **https://share.streamlit.io** → sign in with GitHub.
2. **Create app** → your repo → branch `main` → main file `app.py` → **Deploy**.
3. **Settings → Secrets** → paste:

   ```toml
   HF_TOKEN = "hf_your_token_here"
   ```

   Save. Sidebar will read "Hugging Face token loaded."
4. Open the URL. On a phone she can paste a product image URL straight from a
   store page into **Garment → Image URL**.

---

## Reliability (important for the free route)

The public IDM-VTON Space is shared, so it sleeps, queues, and has a daily GPU
quota. If it's flaky, **duplicate it to your own account** and run it on your own
free ZeroGPU quota — much more dependable:

```bash
pip install huggingface_hub
huggingface-cli login          # paste your token
huggingface-cli repo duplicate yisol/IDM-VTON YOUR_USERNAME/IDM-VTON --type space
```

Then open your new Space once so it builds, and add `"YOUR_USERNAME/IDM-VTON"` to
the `SPACES` list at the top of `app.py` (and pick it in the sidebar).

**If you'd rather it just always work** without babysitting, swap to a paid API —
fal.ai runs the Kolors try-on model at about **$0.07 per image** with a clean
`human_image_url` / `garment_image_url` call. Only the `run_tryon` function in
`app.py` would change; ask and I'll wire it in.

---

## Tips

- **Best inputs:** a clear, front-facing, **full-body** photo, and a flat-lay /
  product photo of the garment.
- **Saved looks** show in a session gallery with a Download button and reset when
  the app restarts. Add a database later if you want them permanent.
- **Detail slider** = denoise steps; higher is a touch sharper but slower.

Space: https://huggingface.co/spaces/yisol/IDM-VTON
