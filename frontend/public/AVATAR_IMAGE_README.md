# Receptionist avatar photo

The photoreal avatar (`src/components/Avatar.tsx`) loads a portrait image and
overlays lip-sync + blinking + head-sway animation on top of it.

## Where to put the image

The component tries these URLs in order and uses the first that loads:

1. `/receptionist.png`   → put the file at `frontend/public/receptionist.png`
2. `/receptionist.jpg`   → put the file at `frontend/public/receptionist.jpg`
3. `/static/receptionist.png` → served by the backend from `backend/static/receptionist.png`
4. `/static/receptionist.jpg` → served by the backend from `backend/static/receptionist.jpg`
5. `VITE_AVATAR_IMAGE_URL` env var (optional explicit URL)

So you can either:

- **Frontend (simplest for dev):** drop `receptionist.png` into `frontend/public/`.
- **Backend static (what you're doing):** put `receptionist.png` (or `.jpg`) into
  `backend/static/`. The dev server proxies `/static` to the backend, so it
  works in both `npm run dev` and production.

## Image guidelines (for best lip-sync alignment)

- Front-facing face, roughly centered, looking at the camera.
- The overlay coordinates in `index.css` (`.avatar-eyelid*`, `.avatar-mouth-*`)
  are tuned for a face where the eyes are ~40% down and the mouth ~56% down.
  If your photo is framed very differently, nudge those `top`/`left`
  percentages in `index.css`.
