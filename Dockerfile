# Eigen image zodat er gegarandeerd een volwaardige ffmpeg aanwezig is.
# (De gebundelde imageio-ffmpeg-binary crasht op Railway bij HLS-streams;
# Nixpacks kreeg ffmpeg niet betrouwbaar geïnstalleerd.)
FROM python:3.12-slim

# ffmpeg als systeempakket; audio.py gebruikt dit bij voorkeur.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# main.py leest zelf de $PORT uit de omgeving (geen shell-expansie nodig).
CMD ["python", "main.py"]
