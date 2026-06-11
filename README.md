# Virtual Try-On Studio — free edition

Puts a garment onto a photo of a person using the **Kolors Virtual Try-On**
model, hosted free on Hugging Face. Your app just sends two images to the Space
and shows the result — no GPU, no paid API.

> It runs on a **free, shared** Space, so expect occasional queues, rate limits,
> or a Space that's asleep and needs a moment to wake up. Great for personal use;
> not built for heavy traffic. If you later want something always-on and fast,
> swap in a paid API (FASHN, Replicate) — only the `run_tryon` call changes.

---

## 1. Get a free Hugging Face token

1. Sign up at **https://huggingface.co**.
2. Go to **Settings → Access Tokens → New token**. A **read** token is enough.
3. Copy it (starts with `hf_...`).

No credit card, no per-image charge.

---

## 2. Run it on your laptop (optional, to test)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Either paste your token into the sidebar, or create `.streamlit/secrets.toml`:

```toml
HF_TOKEN = "hf_your_token_here"
```

Open the local URL, add a person photo + a garment, hit **Try it on**.

---

## 3. Put it on GitHub

1. Create a new repository (e.g. `tryon-studio`).
2. Add `app.py`, `requirements.txt`, `.gitignore`, `README.md` — drag them into
   **Add file → Upload files** on the repo page, or push with git:

```bash
git init
git add app.py requirements.txt .gitignore README.md
git commit -m "Virtual try-on studio (Kolors)"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/tryon-studio.git
git push -u origin main
```

> Don't commit your token. `.gitignore` keeps `secrets.toml` out.

---

## 4. Deploy it free (Streamlit Community Cloud)

1. Go to **https://share.streamlit.io** and sign in with GitHub.
2. **Create app** → pick your repo → branch `main` → main file `app.py` →
   **Deploy**.
3. In the app's **Settings → Secrets**, paste:

   ```toml
   HF_TOKEN = "hf_your_token_here"
   ```

   Save. It reboots and the sidebar shows "Hugging Face token loaded."
4. Open the URL. On your phone, she can paste a product image's URL straight
   from a store page into the **Garment → Image URL** field.

---

## Notes & tips

- **Best inputs:** a clear, front-facing, **full-body** photo of the person, and
  a flat-lay / product photo of the garment.
- **If it's busy or asleep:** wait a few seconds and retry, or switch to a mirror
  Space in the sidebar dropdown.
- **Saved looks** show in a session gallery with a Download button and reset when
  the app restarts. Add a database later if you want them permanent.
- **If the try-on call ever errors with an argument/schema problem:** the Space is
  community-run and its inputs can change. Open the Space, scroll to the footer,
  click **Use via API** (or run `Client(space).view_api()`) to see the current
  inputs, and adjust the single `client.predict(...)` call in `run_tryon`.

Space: https://huggingface.co/spaces/Kwai-Kolors/Kolors-Virtual-Try-On
